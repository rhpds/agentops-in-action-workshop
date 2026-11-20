# 08 — Open questions and ranked risks

Everything in these documents that is **not** backed by
[00-verification-findings.md](00-verification-findings.md). Each row names the command that settles
it.

## Open assumptions

| # | Assumption | How to verify | If it fails |
|---|---|---|---|
| A1 | Keycloak V2 exchange needs the requesting client in the subject token's `aud`, and an `oidc-audience-mapper` satisfies it | Add the mapper, password-grant, exchange. Without it expect `400 invalid_request` / "Client is not within the token audience" | Highest-value 10-minute test in the plan. No workaround — it is a protocol requirement |
| A2 | The exchanged token retains `resource_access` for all three bearer-only clients | Decode the exchanged token; expect 18 roles across 3 clients | `hermes-agent` is missing the `roles` default client scope or `fullScopeAllowed` |
| A3 | A `sub` or `preferred_username` mapper can be added to this realm | `GET /admin/realms/<realm>/client-scopes` after adding, then decode | Use `preferred_username` only; the CEL in [06](06-provenance.md) already degrades gracefully |
| A4 | The Kuadrant **wasm-shim** propagates Authorino `response.success.headers` upstream | Confirmed the shim (not native ext_authz) is in the path: `EnvoyFilter/kuadrant-mcp-gateway`. Test with an `echo.mcp.local` HTTPRoute on the `mcps` listener pointing at a header-echo pod — the policy applies automatically because it targets the listener. Needs no image | Fall back to route B in [06](06-provenance.md): the MCP servers read the token via `mcp.server.request_state` |
| A5 | The MCP broker forwards an unknown header between the `mcp` and `mcps` hops | Send `x-agent-identity: test` on a real tool call; look for it in Authorino's debug log for the `mcps` evaluation | Only needed for the two-listener fallback in [05](05-spiffe-and-ztwim.md); kills that option specifically |
| A6 | Keycloak accepts a SPIFFE credential as client auth — `tls_client_auth` (X509-SVID) or `private_key_jwt` (JWT-SVID) | Phase 7 spike. Test mTLS first | Two fallbacks in [05](05-spiffe-and-ztwim.md); neither blocks phases 1–6 |
| A7 | MLflow 3 exposes a SetTraceTag endpoint reachable with the console's existing token and RBAC | POST a tag to a real trace, re-search it. The console's Role already has `create`/`update` on `experiments.mlflow.kubeflow.org` | Note the documented **300s denial cache** if testing before RBAC exists — a retry inside that window still fails |
| A8 | Changing `SHARE` in `hermes-env.sh` redirects both the refresher and the `hermes_otel` plugin copy | `start-hermes.sh` assigns `SHARE` then sources `hermes-env.sh`. Confirm tracing still works after the override — the plugin copy uses the same variable | Rebuild the sandbox image instead (user builds and pushes) |
| A9 | A hand-applied realm delta survives `tenant-platform` self-heal | Consistent with the repo's own note that self-heal re-applies the CR, not realm contents, and the import Job is `Complete` with `--override=false`. Confirm by syncing the platform Application and re-reading the client | Apply the delta from a Job instead of by hand |
| A10 | Enforcing `azp` does not break `.well-known`, `initialize` or `tools/list` | Those carry no `x-mcp-toolname`, so they hit the `anonymous` rule and the `when` guards. Confirm with a `tools/list` after enforcement | Widen the `when` guards |

## Risks, ranked

**R1 — Fail-closed brokers in a lab with a flaky model endpoint.** *(highest)*
Enforcing `azp` turns any broker or Keycloak hiccup into "the agent has no tools", and the repo
already documents that Hermes misreports a 403 as "a network issue or service outage". With 30
tenants against a MaaS endpoint that returned 52 HTTP 429s across 15 runs of one sequential client,
a transient failure during an exercise is plausible. **Mitigation:** keep
`mcpGateway.agentIdentityEnforced` default-off until proven on all three tenants; keep the broker's
loop tolerant (retry next cycle, never exit) as it is today; and accept that failing closed is still
correct — a silent fall back to the raw operator token would de-identify the agent exactly when the
policy started requiring identity.

**R2 — Keycloak will not accept a SPIFFE credential.** *(high, unresolved)*
`private_key_jwt` expects the assertion's `iss` **and** `sub` to equal `client_id`; a SPIRE JWT-SVID
has `sub` = the SPIFFE ID and `iss` absent or the SPIRE issuer. `tls_client_auth` may fit better but
needs client-certificate termination on an ingress we do not own. **Mitigation:** the secret-based
client in Phase 1 de-risks the entire identity story; SPIFFE is an upgrade, not a prerequisite.

**R3 — Realm deltas diverge from git.** *(medium)*
Because of `--override=false`, live tenants and the chart are updated by different routes, so POC
state and git state can silently drift. **Mitigation:** commit the REST calls as an idempotent,
reviewable script under `tenant-platform/files/`, run by nothing, with the chart as source of truth.

**R4 — An OpenShell upgrade becomes load-bearing.** *(medium)*
If SPIFFE in the *sandbox* is judged necessary rather than nice, 0.0.92 → ~0.1.9 touches the
component modules 2, 4 and 5 are built on, plus the CLI/gateway version pairing. **Mitigation:** the
`hermes-plain`-first path in [05](05-spiffe-and-ztwim.md) means this is never on the critical path.

**R5 — Three image rebuilds before provenance is visible.** *(medium)*
Phases 5 and 6 need `plant-api`, three `*-mcp` images, and `waterplant-ui`, all built by hand.
**Mitigation:** phases 1–4 deliver the whole authorization story with no builds, so the valuable
half is independent of the handoff.

**R6 — Authorino CEL expressiveness.** *(low)*
Both facts are in one verified token, `patternMatching.patterns` AND-s its predicates, multiple
`authorization` rules also AND, and CEL over `auth.identity.*` is already in production use in this
very policy. Residual risk is mechanical: missing-claim errors (use `has()`), and `auth.identity`
being empty under the `anonymous` rule.

**R7 — ZTWIM install blast radius.** *(low)*
A new cluster-scoped operator with a CSI driver and a node DaemonSet, on a shared lab cluster.
Confined to Phase 7, behind a spike, pinned at a specific CSV with Manual approval.

## Corrected claims — recorded so they do not reappear

| Earlier claim | Reality |
|---|---|
| "The agent borrows the operator's identity" | Weaker than that: the token has **no subject at all**. `azp` is the shared public client |
| "`AGENT_API_KEY` resolves empty — a possible open front door" | **False.** It is set, length 48. The cause was a redaction filter in the inspection command |
| "The relay stripping `Authorization` blocks provenance" | **No.** The console targets `hermes-plain` at baseline, so the relay is not in the path; and the design never needs a per-turn token on that hop |
| "The vendored OpenShell chart supports SPIFFE, so no upgrade is needed" | Half true. The chart has the socket-mount switch; the **provider profile schema has no dynamic-credential surface at all** |
| "Chart realm changes reach existing tenants" | **No.** `kc.sh import --override=false`, Job already `Complete` |
| "Provenance needs a custom header parsed in middleware" | There is also a native route — mcp 2.x exposes `authenticated_principal` / `get_access_token`. The header is still recommended, but for a design reason, not a technical one |

## Questions for the team, not for a command

1. **Does this become a workshop module, or stay platform work?** It changes what gets built. A
   module needs a participant-visible before/after and 15–20 minutes carved out of a full 120.
2. **Is a two-hop `sub`+`azp` chain good enough to teach?** It is honest and it demonstrates the
   principle. But a lab about agent identity that cannot show a real `act` claim may want to say so
   explicitly rather than leave a reader to notice.
3. **Should `attack-runner` get its own agent instance?** The cheap version fixes trace attribution.
   Only a second Hermes makes probe *tool calls* distinguishable at the gateway, and that costs a
   pod and a second stream of model calls per tenant.
4. **How much of the deliberate insecurity should identity close?** `plant-api` having no auth is a
   documented lab starting condition, not an oversight. Adding an audit trail records actors without
   adding enforcement — but it is worth confirming that is the intent before building it.
