# 13 — Every component in the tool request path

Written to answer one question that kept being re-litigated: *for each hop a tool call passes
through, what identity does it hold, and can it put that identity on a span?*

The short version, and the reason the answer took so long to find:

> **The components that hold the verified identity cannot emit a span. The components that emit
> spans do not hold the identity.** There is exactly one exception, and it is the whole design.

Everything below was measured on tenant `user-gngp7` on 2026-11-27 unless marked otherwise.

## The path

A tool call crosses the gateway's Envoy **twice**. That is the single most important structural
fact here and it is not obvious from any diagram in this repo:

```
browser
  └─▶ water-plant-ui              /api/chat
        └─▶ hermes agent          (OpenShell sandbox, pod default--hermie)
              └─▶ OpenShell egress proxy      ← mints + injects the bearer token
                    └─▶ Envoy HOP 1   listener `mcp`,  authority = gateway svc DNS, path /mcp
                          ├── wasm-shim ──▶ Authorino   (mcp-auth-policy: authn only)
                          ├── ext_proc  ──▶ sets x-mcp-* (server = "mcpBroker" on this hop)
                          └─▶ MCP broker        (mcp-gateway pod)
                                └─▶ Envoy HOP 2   listener `mcps`, authority = <server>.mcp.local
                                      ├── wasm-shim ──▶ Authorino  (mcp-authz-policy: authn +
                                      │                  tool role + azp; injects the actor)
                                      ├── ext_proc  ──▶ sets x-mcp-toolname / servername / method
                                      └─▶ MCP server
                                            └─▶ plant-api
```

**Only `tools/call` makes the second crossing.** `initialize`, `ping`, `tools/list` and the SSE
stream go **straight from the broker to the MCP server's ClusterIP Service**, bypassing the gateway
entirely — measured by registering a throwaway MCP server that logged every request it received
(`Host: hdr-echo.user-gngp7-agentops.svc.cluster.local:8080`, `User-Agent: mcp-broker`, no
`x-mcp-*` headers at all).

## The table

| # | Component | Identity it holds | Can it emit a span? | Verdict |
|---|---|---|---|---|
| 1 | **Console UI** `water-plant-ui` | Which pane the turn came from (chat vs probe engine). No token, no `jti`, no verified actor | Yes — already speaks the MLflow REST API | **Partial.** Authoritative for `source`; anything actor-shaped would be self-asserted |
| 2 | **Hermes agent** (sandbox `default--hermie`) | The conversation and the tool it intends to call. **Owns the MLflow trace** via `hermes-otel`. Does *not* see the bearer token | Yes — it owns the trace | **No.** Has the span, lacks the verified identity |
| 3 | **OpenShell egress proxy** | **The entire credential.** Performs the exchange and injects `Authorization`, so it holds `sub`, `azp`, `jti` | No emission hook; NVIDIA's code | **No.** Richest identity in the path, no way out of it |
| 4 | **Envoy — hop 1** (`mcp`) | Raw JWT header, path, authority; after the shim's call, Authorino's ok-response headers and dynamic metadata | **Yes — Envoy is a tracer**, with `custom_tags` | Viable, but hop 2 is strictly richer |
| 5 | **Kuadrant wasm-shim** (in Envoy, both hops) | Everything, in CEL: `auth.identity.sub / azp / jti`, plus every `x-mcp-*` header | Emits `kuadrant_filter`, `grpc`, `send_reply` — but the fields are **compile-time `info_span!` macros** (`action_set`, `hostname`, `request_id`, `action`, `otel.status_*`) | **No.** No hook of any kind to add an attribute. Verified in 0.14.x source; deployed version is 0.14.2 |
| 6 | **Authorino** (gRPC, called by the shim) | The full identity — it is the component that *resolves* it | Emits `AuthService/ServeHTTP` and `AuthService/Check`, carrying only `authorino.request_id` and `guid:x-request-id`. `spec.tracing.tags` become **static OTel resource attributes** | **No.** Knows everything, records none of it |
| 7 | **MCP ext_proc** (the broker's gRPC :50051) | The JSON-RPC body → derives `x-mcp-servername`, `x-mcp-toolname`, `x-mcp-method`. Decorates **both** hops | Vendor image (`mcp-gateway-rhel9`), no configurable spans | **No** |
| 8 | **MCP broker** (`mcp-gateway` pod) | The token, which it forwards onto hop 2; prefix→server routing | Vendor image | **No** |
| 9 | **Envoy — hop 2** (`mcps`) | **Everything at once:** the JWT, `x-mcp-toolname` / `servername` / `method`, **and** Authorino's injected `x-waterplant-actor` | **Yes** | ✅ **The answer** |
| 10 | **MCP server** | The injected header plus tool arguments | Yes, with code | **Rejected** — does not scale; we may not own every MCP server, and we would not want to patch each one |
| 11 | **plant-api** | Only what the MCP server chooses to pass on | Yes, with code | **Rejected** — same reason, one hop further |

## Why row 9 wins

Hop 2 is the only point where the verified actor, the tool name, the server name and a tracer all
coexist — and the only one that needs no application code anywhere in the path. Nothing about it is
per-server, so an MCP server registered tomorrow by someone else is covered the moment it appears.

Proven on the wire, not inferred. An EnvoyFilter in the tenant namespace added an access-log format
reading the headers; a real console turn then produced:

```
PROVPROBE authority=telemetry-mcp.mcp.local path=/mcp
          tool=get_reservoir_level server=user-gngp7-agentops/telemetry-mcp mcpmethod=tools/call
          actor={"chain":[{"role":"subject","sub":"operator"},
                          {"role":"agent","sub":"spiffe://agentops.lab/ns/user-gngp7-agentops/sa/user-gngp7-openshell-sandbox"}],
                 "jti":"ntrtte:2f818059-b10b-4303-b927-19ca27f3c9b8"}
          status=200
```

Three things that establishes at once:

1. **The wasm-shim really does inject Authorino's `response.success.headers` into the upstream
   request.** Previously argued from version-matched source; now observed.
2. **Filter-added request headers are visible to Envoy's stream-end formatter** — the same machinery
   `tracing.custom_tags.request_header` uses. So a span tag will populate identically.
3. **An EnvoyFilter in the tenant namespace is accepted and programmed**, with no change to the
   cluster-wide mesh config.

## `jti` identifies the token, not the call

Worth stating separately because the original design in [06](06-provenance.md) got it wrong.
OpenShell caches the exchanged token (`token_grant` `cache_ttl_seconds`), so every tool call inside
that TTL presents the same credential and therefore the same `jti`. Two console turns calling two
different tools:

| | call 1 | call 2 |
|---|---|---|
| `tool` | `get_reservoir_level` | `get_pump_status` |
| `jti` | `ntrtte:1f313fd7-…` | `ntrtte:1f313fd7-…` — **identical** |
| `reqid` | `3cd9015f-…` | `189ed9bb-…` — **differs** |

So `x-request-id`, generated by Envoy per request, is the per-call join key; `jti` scopes "which
minted credential acted", which is the right question when asking whether the agent
re-authenticated between two actions. Both are in the access-log format for that reason.

## Two routes that look right and are not

**`Telemetry` CR `customTags`.** Supports only `literal`, `environment` and `header` — no
`metadata` — and, decisively, a tracing provider must come from `meshConfig.extensionProviders`.
The live mesh config (`cm/istio-openshift-gateway`, namespace `openshift-ingress`) has **no
`extensionProviders` at all**, is labelled `managed-by: sail-library` / `istiod-1.28.10`, and there
is no `Istio` CR on the cluster — so there is no supported API to add one. Editing it would mean
hand-patching a Helm-managed ConfigMap shared by every gateway on the cluster. Envoy's own
`CustomTag` oneof (`literal | environment | request_header | metadata | value`) is richer than what
the `Telemetry` CR exposes, and an EnvoyFilter reaches all of it.

**The Kuadrant OpenTelemetry example.** Two independent reasons it cannot help, and the second is
the one that matters:

- [That page](https://docs.kuadrant.io/1.4.x/kuadrant-operator/examples/otel/#architecture) is the
  operator watching *itself*: Zap tee-core → OTLP logs, Prometheus bridge → metrics, operator traces
  → Collector → Loki/Tempo/Prometheus/Grafana. Authorino, Limitador, the wasm-shim and Envoy are all
  outside its scope. Implemented perfectly it yields *"AuthPolicy reconciled in 12 ms"*, never
  *"operator called get_reservoir_level"*.
- **The per-request tracing that does exist carries no identity** — rows 5 and 6 above. Both say a
  decision happened and whether it passed. Neither says who.

So Kuadrant → MLflow fails at the **payload**, not the transport. The sink was never the problem:
MLflow already ingests OTLP at `https://mlflow.…svc.cluster.local:8443/v1/traces`, which is what the
sandbox's own `mlflow_tracing` egress rule exists for.

## What remains

The header half is proven. The export half is specified but not yet exercised. From
`agent-hermes-plain.yaml:502-517`, MLflow's OTLP ingest wants:

```
endpoint: https://mlflow.redhat-ods-applications.svc.cluster.local:8443/v1/traces
headers:  x-mlflow-experiment-id, Authorization: Bearer <token>, X-MLflow-Workspace
TLS:      the CA mounted at /etc/mlflow-ca
```

Envoy's `envoy.tracers.opentelemetry` takes an `http_service` with `request_headers_to_add`, so all
three headers are expressible.

**Built and working, 2026-11-27.** Measured in this order:

| Question | Result |
|---|---|
| Does MLflow accept OTLP from a non-SDK producer? | **Yes.** A hand-crafted OTLP/HTTP JSON span POSTed to `/v1/traces` returned `200` and materialised as a trace, `state: OK`, `execution_duration` derived from the span's own timings |
| Do OTLP resource attributes survive? | **Yes** — `service.name` comes back as an MLflow **trace tag** |
| Is authentication required? | **Yes.** Unauthenticated returns `401 UNAUTHENTICATED: Missing Authorization header or X-Forwarded-Access-Token header` |
| Is there a long-lived token for Envoy? | **No.** Correcting an earlier claim here: there is no 8760h ServiceAccount token. `agent-hermes-plain.yaml:460` reads the pod's **projected** token, which rotates, and the namespace holds no `kubernetes.io/service-account-token` Secret |

That last row is the whole design problem. Every workload here authenticates to MLflow the same
way — re-read the projected token from disk on each request, because a cached copy "would start
401ing hours into a workshop" (`traces.py:92`). **Envoy cannot do that**: its OTLP exporter takes a
literal header baked into the xDS config — no file read, no refresh hook, no credential plugin.

So the fix is not to defeat rotation with a long-lived token in the EnvoyFilter. It is to put the
export behind *a process that can re-read a file* — the lab's existing pattern, applied a fourth
time. A per-tenant OpenTelemetry Collector
(`tenant-platform/templates/provenance-collector.yaml`) receives OTLP in-namespace over plaintext
and forwards to MLflow with `bearertokenauth`, whose upstream docs say "a file-backed token is
picked up as the file changes".

```
Envoy hop 2 ──OTLP/http, plaintext, in-namespace──▶ collector ──OTLP + rotating bearer + CA──▶ MLflow
```

**Proven end to end.** The span the collector received and exported:

```
waterplant.actor      {"chain":[{"role":"subject","sub":"operator"},
                                {"role":"agent","sub":"spiffe://agentops.lab/ns/user-gngp7-agentops/
                                                       sa/user-gngp7-openshell-sandbox"}],
                       "jti":"ntrtte:6ea29ec2-..."}
waterplant.tool       get_reservoir_level
waterplant.server     user-gngp7-agentops/telemetry-mcp
waterplant.mcp_method tools/call
guid:x-request-id     0319bd36-a8a4-9ceb-b210-9f154014b963
http.status_code      200     upstream_cluster  outbound|8080||telemetry-mcp...
```

Envoy and istio's own attributes come along free. In MLflow, each turn now produces one
`hermes-agent` trace and two `mcp-gateway-<user>` traces — one per gateway hop.

**Three traps worth knowing, each of which cost a deploy cycle:**

1. `otlphttp` **appends** `/v1/traces` to `endpoint`, and MLflow's ingest already lives at
   `/v1/traces` — so `endpoint` POSTs to `/v1/v1/traces`. Use `traces_endpoint` and spell the URL.
2. The collector's own `${env:VAR}` expansion runs **after** the YAML parse and re-infers the type,
   so an all-digits experiment id arrives as an int: `expected type 'configopaque.String', got
   unconvertible type 'int'`. The init container substitutes into quoted text instead.
3. The `debug` exporter writes its span dump at **INFO**, so with the default `warn` telemetry
   level it prints nothing — indistinguishable from "no spans are arriving". The chart forces
   `info` whenever `debugExporter` is on.

**Both hops are traced, and only one is worth keeping.** Hop 1 is the public `/mcp` listener,
where there is no tool name yet and the AuthPolicy injects no actor, so its span arrives with
`waterplant.tool=none` and `waterplant.actor=none`. Unfiltered that puts **two** traces in the
experiment per call, one of them empty, sorting indistinguishably beside the real one. The
collector's `filter` processor drops any span that is not an authorized tool call
(`provenance.toolCallsOnly`, default on). The cost, stated because it is real: unauthenticated
401s at the public listener disappear from MLflow too, since they never acquire a tool name. They
remain in the gateway access log.

## Why the gateway's spans cannot nest under the agent's trace

They stand beside the agent's trace in the same experiment rather than inside it, and this is
**not** fixable from our side. Measured:

| Evidence | Reading |
|---|---|
| Hop 1 request carries `tp=00-5b8f70a3…-01`, hop 2 carries `tp=00-2efcbb3f…-01` | Different trace ids — the two hops are unrelated traces |
| Hop 2's **root span has an empty Parent ID** | No usable inbound trace context was extracted, so Envoy started a new trace |

Envoy injects `traceparent` toward its upstream whenever tracing is on, so hop 1's Envoy *did*
hand the MCP broker a trace context. The broker then made the hop-2 request without it. So the
chain breaks **inside the MCP broker**, which is a vendor image
(`registry.redhat.io/rhcl-tech-preview/mcp-gateway-rhel9`).

That ordering matters: instrumenting the agent to emit `traceparent` would be necessary but **not
sufficient**. Even a perfectly propagating agent loses the context at the broker, and the broker
is exactly the hop that stands between the agent and the span carrying the actor. Nesting needs a
change we do not own.

Until then, correlate on **time plus tool name**: the agent's own trace records which tool it
called, and the gateway's span records who the platform verified for that same tool a moment
later. `jti` does not serve here — it identifies the token, which is shared across every call in
its cache TTL.
