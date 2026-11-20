# 07 — Proposed phasing

A build order, not a commitment. Each phase is independently verifiable on **one tenant**
(`user-9c5ls`) with `user-qkc86` left untouched as a control, and each has a stopping point where
the work so far is coherent on its own.

**Phases 1–3 need no image rebuild.** That is a consequence of the console targeting `hermes-plain`
at baseline, so the whole identity half can be built in charts and a Python script.

## Phase 0 — verification ✅ done

See [00-verification-findings.md](00-verification-findings.md). Strictly read-only. It changed two
things in the design: OpenShell cannot do SPIFFE-backed token grants on this build, and the MCP
servers have a native identity surface.

## Phase 1 — prove the exchange works at all

The cheapest test of the central claim, and the one that could invalidate everything after it.
Everything here is applied **by hand via the Keycloak admin REST API** — because of the
`--override=false` import Job, a chart change would not reach this tenant anyway.

1. **Audience mapper** on `mcp-gateway`'s dedicated scope: `oidc-audience-mapper`,
   `included.client.audience: hermes-agent`. Without it the exchange returns
   `400 "Client is not within the token audience"`.
2. **Subject mapper** on the same scope — the realm has no `basic` scope, so there is no `sub`
   today. `preferred_username` at minimum.
3. **Create `hermes-agent`**: `publicClient: false`, `serviceAccountsEnabled: false`,
   `directAccessGrantsEnabled: false`, `standardFlowEnabled: false`, `fullScopeAllowed: true`,
   `defaultClientScopes: [roles, groups]`, `attributes: {standard.token.exchange.enabled: "true"}`.
   `roles` is load-bearing — without it the exchanged token has no `resource_access`.
4. **Fixed audience mapper** on `hermes-agent` naming the gateway resource. Do **not** pass
   `audience=` on the exchange request itself.
5. **Exchange and decode.** Assert `azp == hermes-agent`, the subject is present, and all 18 tool
   roles survive in `resource_access`.

**Exit criterion:** a decoded exchanged token carrying both principals and the operator's unchanged
permissions. If step 5 fails irrecoverably, the fallback is a confidential `hermes-agent` with
`directAccessGrantsEnabled: true` doing a plain password grant — same `azp`/`sub` result, same
enforcement demo, but the agent client then holds the operator password. Keep that in reserve, not
as the plan.

## Phase 2 — enforce the intersection, in shadow mode first

The live agent must not break while this is being proven. Add the new rule **guarded on a header no
real traffic sends**:

```yaml
authorization:
  agent-identity-check:
    when:
      - predicate: "request.headers['x-identity-poc'] == '1'"
    patternMatching:
      patterns:
        - predicate: "has(auth.identity.azp) && auth.identity.azp == 'hermes-agent'"
```

Authorization rules are AND-ed, so the guard makes the rule apply to a probe and skip for Hermes.
Then drive the internal `mcps` listener directly — which also sidesteps the limitation recorded at
`qa-automation/healthcheck-spec.yaml` E2E-M3-03, where the broker answers 400 before Authorino is
consulted — and check the four cells of diagram 4:

| token | `x-identity-poc` | expected |
|---|---|---|
| operator (password grant) | absent | allow — today's behaviour, unchanged |
| operator (password grant) | `1` | **403** |
| exchanged | `1` | allow |
| exchanged, role revoked from operator | `1` | **403** |

Row 4 is what proves intersection rather than substitution.

**Probe with `telemetry-mcp` / `get_pump_status` only.** Read-only, mutates nothing. Never probe
with `stop_pump` or `emergency_shutdown` — if the policy allows, the pump actually stops.

## Phase 3 — switch the real agent over, and put it in git

- `tenant-platform/files/mcp-token-refresh.py` (and its byte-identical twin in
  `tenant-openshell/files/` — keep them identical; a `diff` check belongs in CI): add the exchange
  step, **env-gated** so that without `MCP_EXCHANGE_CLIENT_ID` it behaves exactly as today. **Fail
  closed** — log loudly, write nothing, never fall back to the raw operator token.
- `tenant-platform/templates/agent-hermes-plain.yaml` and `agent-hermes.yaml`: the new env on both
  the `seed-token` init container and the `mcp-token-refresh` sidecar. The `checksum/config`
  annotation already hashes the refresher, so the pod rolls on its own.
- `tenant-platform/templates/mcp-gateway.yaml`: the realm deltas from Phase 1, for future clusters.
  **Rewrite the `:199-202` comment** explaining why a confidential agent client is now acceptable —
  that comment is the design record future readers will trust.
- `tenant-policy/templates/mcp-gateway-policy.yaml`: promote the shadow rule, gated on a new value
  `mcpGateway.agentIdentityEnforced` (**default `false`**) so it can be turned off per tenant
  without a code change.
- `tenant-platform/values.yaml`, `tenant-policy/values.yaml`,
  `bootstrap-tenant/templates/applications.yaml`: declare and forward the new values.

Commit the Phase 1 REST calls as an idempotent script under `tenant-platform/files/` — not run by
anything — so the live delta is reviewable and replayable and the chart stays the source of truth.

**Verify:** the token file now decodes with `azp=hermes-agent`; one real console turn still works;
then run the existing `E2E-M3-01/04/05` behaviour checks unchanged as the regression net.

## Phase 4 — the sandbox, without rebuilding the Hermes image

`start-hermes` assigns `SHARE` **before** sourcing `/sandbox/hermes/hermes-env.sh`, and that file is
rendered by the bridge — which this repo controls. So `hermes-env.sh` can redirect `SHARE` to a
sandbox-local directory it populates with the updated refresher, keeping `sandbox.image` pinned at
`0.2.7`.

Call that what it is: a POC-grade override. The durable form is baking the broker into
`hermes-openshell/mcp-token-refresh.py` and rebuilding — **user builds and pushes**.

## Phase 5 — provenance into the MCP servers and plant-api

**Gated on the open question of whether the gateway propagates Authorino's success headers**
([08](08-open-questions.md)).

Sister repo:
- the three `client.py` files (byte-identical, keep them so): read `x-waterplant-actor`, forward it
- `plant-api`: `raised_by_verified` beside `raised_by`, an actor on control actions, `GET /audit`
- `mcp-maintenance`: send both the model's claim and the gateway's verified actor

**Image gate: user builds and pushes** `plant-api` and the three `*-mcp` images. Note `image.mcpTag`
is `latest` with `pullPolicy: Always`, so those need only a rollout restart; `plantApi.tag` is
pinned at `0.2.0` and **must not** be bumped before the push exists. Worth pinning `mcpTag` in the
same change — `latest` sits two keys below a comment arguing for pinning.

## Phase 6 — console: automatic operator identity and trace tags

No login, ever. A background asyncio task mirroring the broker: password grant for `operator`,
refresh on a loop, expose `token()` and `actor()`. Same env var names, so the two implementations
stay recognisably the same mechanism.

- `ui/src/waterplant_ui/identity.py` (new), wired in `app.py`
- `harness.py`: keep the static key for Hermes' own auth; **fix `identity_is_propagated()`**, which
  currently returns `PROTOCOL == "waterplant"` and claims propagation on a path where nothing
  propagates
- `traces.py`: `tag_trace()` with `waterplant.actor` / `source` / `jti`
- `probes/`: `waterplant.source=probe`, and the `attack-runner` actor on direct plant-api calls

**Image gate: user builds and pushes** `waterplant-ui`.

## Phase 7 — SPIFFE, behind a spike

Gate the whole phase on a 2-hour spike, because the central mechanism is unverified. Order matters:
**prove the SVID on `hermes-plain` first**, which isolates the Keycloak question from the OpenShell
question. Test `tls_client_auth` with an X509-SVID before `private_key_jwt` with a JWT-SVID — see
[05](05-spiffe-and-ztwim.md) for why, and for the two fallbacks.

Only after that: ZTWIM into `bootstrap-infra/templates/operators.yaml` at a pinned
`zero-trust-workload-identity-manager.v1.1.3`, the SPIRE stack, and a `ClusterSPIFFEID`.

Extending into the sandbox needs an OpenShell upgrade and is **not** part of this.

## Workshop content — deliberately last, and not yet planned

Nothing above touches `content/modules/ROOT/**` or `publishing-house/spec.yaml`. When the mechanism
is proven, the content question is a separate conversation with its own trade-off: the lab is
already 120 minutes across 7 modules, and module 3 at 15 minutes is the shortest and already opens
with *"we need to give the identity the right permissions"* — which is the natural hook.

## QA checks that will need extending — enumerated, not changed

- **`TEN-KC-01`** — currently only asserts the realm answers OIDC discovery. Add: the agent client
  exists, has the exchange attribute, and a round-trip yields `azp=hermes-agent`.
- **`E2E-M3-03`** — the one that breaks conceptually. It fetches an operator token and decodes
  `resource_access`, calling that token "the authorization boundary". After Phase 3 the boundary is
  the *exchanged* token, so it must exchange before decoding, and should assert the raw operator
  token is refused.
- **`TEN-MCP-02` / `TEN-GW-01`** — unchanged in substance, but "federation healthy while every tool
  call 403s on a missing `azp`" is a new failure mode worth its own check.
- **New:** broker wrote an exchanged token; Authorino injected an actor; a work order carries
  `raised_by_verified`; a trace carries `waterplant.actor`.

## Housekeeping to do before the first commit

The working tree is a **199-file CRLF rewrite** — 26,529 insertions and 26,529 deletions, every `+`
line identical to its `-` line plus `^M`. No `.gitattributes`, `core.autocrlf` unset. Harmless now,
but it would bury the first real diff. Fix with `core.autocrlf=input` (or `.gitattributes` with
`* text=auto eol=lf`) then `git checkout -- .`.

Unrelated and pre-existing, recorded at `qa-automation/healthcheck-spec.yaml:902-930`: the guide
tells participants to sign into Keycloak as `admin` with `{password}` when the realm admin password
is `redhat`, which blocks the whole module-3 Keycloak section. Worth raising with the author.
