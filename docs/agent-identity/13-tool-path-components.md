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

Nesting them at source is impossible here, and it took two separate measurements to be sure —
both breaks are real and independent.

**Break 1 — the agent emits no trace context.** No gateway trace has ever shared a trace id with
an agent trace. If `hermes-otel` propagated W3C context, hop 1's Envoy would adopt it and MLflow
(whose trace id *is* the OTel trace id) would have merged them automatically.

**Break 2 — the MCP broker forwards no unknown headers.** A marker header injected by Authorino
on hop 1 arrives **absent** on hop 2:

| hop | `x-waterplant-probe` |
|---|---|
| hop 1 `mcp-gateway…svc` | present |
| hop 2 `telemetry-mcp.mcp.local` | **stripped** |

Confirmed independently: hop 1 and hop 2 carry different `traceparent` trace ids, and hop 2's root
span has an empty Parent ID even though Envoy injects `traceparent` upstream whenever tracing is
on. So the broker received a context and dropped it.

Break 2 is the decisive one, because it sits between the agent and the only span that carries the
actor. Even a perfectly instrumented agent loses the context there. And the broker is a vendor
image (`registry.redhat.io/rhcl-tech-preview/mcp-gateway-rhel9`) with no telemetry knob —
`MCPGatewayExtension.spec` exposes none, and while the binary embeds the OTel SDK
(`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `W3C`) it contains **no `otelhttp`**, so it
has no HTTP instrumentation to propagate with.

## So the context is re-attached late instead

Normal distributed tracing works because **every** hop participates: it extracts `traceparent`,
emits its span under the same trace id, and injects an updated `traceparent` downstream. That is
the only thing that makes multi-application traces join. Here exactly one hop refuses, and it is
not ours to fix — so the same end state is reached by re-attaching the context afterwards.

This is possible because of one fact worth stating loudly: **MLflow's trace id IS the OTel trace
id** (`tr-` + the 32 hex chars). A span POSTed to `/v1/traces` carrying an existing trace's id is
filed *into that trace* — verified by watching a trace's span list grow after the POST.

Three things make it work, each needed by the next.

**1. Promote the provenance values to resource attributes.** MLflow turns an OTLP *resource*
attribute into a trace **tag**, but its API returns `trace_info` with no spans — so a span
attribute is invisible both in the trace list and to anything reading over REST. The collector's
`groupbyattrs` processor moves them up, and re-groups so two batched calls cannot share one actor.

**2. Find the agent's own span for that tool.** The documented API will not return spans, but the
endpoint the MLflow UI itself uses will:

```
GET /mlflow/ajax-api/2.0/mlflow/get-trace-artifact?request_id=<trace_id>
```

It returns the full tree with base64 `span_id` / `parent_span_id`. The agent's trace already has a
span per tool call, named by `hermes_otel` as `tool.mcp_gateway_<prefix>_<toolname>` — so the
gateway's record can be parented to the exact call it verifies, not merely to the trace.

**3. Re-emit the gateway span into the agent's trace.** `files/provenance-stitcher.py`, a sidecar
in the collector pod, matches each gateway trace to the agent turn whose
`[request_time, request_time + execution_duration]` window contains it, re-emits it with
`traceId` = the agent's and `parentSpanId` = that `tool.*` span, then deletes the gateway trace.

**Result**, measured:

```
tr-b060a089…  svc=hermes-agent  "Final nesting check: reservoir level and pump 4 status."
   - agent
     - llm.qwen3-235b-a22b
       - api.qwen3-235b-a22b
       - tool.mcp_gateway_telemetry_get_reservoir_level
         - gateway verified: get_reservoir_level      <-- actor, server, method
       - tool.mcp_gateway_telemetry_get_pump_status
         - gateway verified: get_pump_status
       - api.qwen3-235b-a22b
```

One trace per turn, a real parent/child edge, and the verified actor sitting under the call it
belongs to. `waterplant.actor` and `waterplant.verified_calls` are also written as trace **tags**,
because span attributes are not searchable from the trace list and tags are.

### The collector exports to the stitcher, not to MLflow

An earlier version let the collector write gateway spans to MLflow and had the stitcher fold and
delete them. It worked, but every tool call briefly produced a **loose trace** in the
participant's experiment. Measured:

| design | loose trace visible | provenance span attached |
|---|---|---|
| collector → MLflow, 45s settle / 30s poll | 8.1s → 20.3s | 20.3s |
| same, timings tightened | 6.1s → 12.2s | 12.2s |
| **collector → stitcher (current)** | **never** | **8.1s** |

The delays in the first two rows were entirely self-inflicted: a 5s collector `batch.timeout`,
then a `settleSeconds` wait invented to let the agent's trace appear. That wait bought nothing —
the matcher already handles a missing host by retrying, and measurement showed the agent's trace
was in MLflow **4.0s** after the turn started, *before* the gateway span had even been exported.

Routing the collector to the stitcher removes the loose trace entirely rather than shortening it,
and removes the poll interval from the path: the arrival of a span is the trigger. It also drops
the `delete-traces` calls and the MLflow search for gateway traces.

Two costs, both deliberate. A buffered span lives in memory, so a pod restart loses it from
MLflow — never from the gateway access log, which is the durable copy and the reason that log
stays. And a span whose turn never appears is emitted as its own trace after
`unmatchedTimeoutSeconds` rather than dropped, under `service.name: waterplant-unmatched`.

One trap: the `otlphttp` exporter **gzips by default**, so the receiver must decompress. Without
it every payload fails UTF-8 decoding and spans vanish with only a log line.

### Two separate problems: matching and attachment

Worth keeping apart, because conflating them caused confusion.

- **Attachment** — putting the span in the right place once you know which trace it belongs to.
  This is now exact: a real parent/child edge under the agent's own `tool.*` span.
- **Matching** — deciding *which* agent trace a gateway trace belongs to. This is still a
  time-window inference, and it is what `traceparent` would normally answer for free: in ordinary
  distributed tracing the request *carries* the answer. Ours cannot, because the broker strips it.

So the three steps above fixed attachment, not matching. Matching stays heuristic, and is sound
here only because one tenant runs one agent answering one turn at a time. The stitcher checks
window containment rather than nearest-trace, and leaves a gateway trace alone (logging
`unmatched`) rather than guessing — it is retried on the next cycle.

### Only `tools/call` counts — the session handshake wears the same tool name

Opening a session to an MCP server costs three gateway requests, and the broker stamps **all
three** with the same `x-mcp-toolname`:

```
mcpmethod=initialize                 status=200
mcpmethod=notifications/initialized  status=202
mcpmethod=tools/call                 status=200   <- the only real invocation
```

Filtering on the tool name alone therefore records one tool call three times. A single
"turn on pump 3" produced **six** verification spans across two tools. The collector's filter now
also requires `waterplant.mcp_method == "tools/call"` — the same predicate the AuthPolicy uses to
decide authorization, so the two agree by construction.

This only shows up on the *first* call to a given MCP server; a warm session produces one request,
which is why early testing missed it.

### Four traps, each of which cost a cycle

1. **`service.name` on the emitted span relabels the host trace.** MLflow derives a trace's tags
   from the resource of the spans it ingests, so sending the gateway's `service.name` renamed the
   agent's whole trace to `mcp-gateway-<user>`. The stitcher now echoes the host trace's own value.
2. **Timestamps must be the gateway span's real ones.** A span emitted with `now` stretched the
   host trace's `execution_duration` from `5.5s` to `10679s`, because MLflow recomputes it across
   all spans.
3. **A ConfigMap-only change does not restart the pod.** The mounted file updates but the running
   python keeps the code it started with, so an edit looks deployed and is not. The Deployment's
   `checksum/config` now hashes the stitcher source too.
4. **`get-trace-artifact` is an `ajax-api` endpoint**, i.e. what the UI uses rather than a
   documented API. The stitcher treats it as best-effort: if it fails the span is still attached,
   just at the trace root instead of under the tool call.

### Why a sidecar rather than the console

The console is a reasonable home — it already talks to MLflow and already resolves each turn's
trace. Two things decided it the other way. The sidecar needs **no image build**: the python image
is already pulled for the init container beside it, and the MLflow credential and CA are already
mounted in that pod. And it covers **all** traffic, not just turns that went through the console —
anything driving the agent still gets its provenance attached.

The matching logic would be identical either way, since neither component can know the gateway's
trace id in advance.

