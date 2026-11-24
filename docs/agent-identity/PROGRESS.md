# Implementation progress — living document

Updated as work proceeds. The plan is [09-implementation-plan.md](09-implementation-plan.md);
this is what has actually happened.

**Last updated:** 2026-11-23
**Branch:** `spiffe-spire`
**Test tenant:** `<user>` — the other two tenants are untouched controls

## Cluster

```
API           https://api.<cluster>.example.com:6443
apps domain   <apps-domain>
Keycloak      sso.<apps-domain>   (RHBK 26.4.18)
chart tag     rh1-2027-lb1285-0.0.2  (pinned on every Application)
OpenShell     chart 0.0.92 · gateway :0.0.92 · CLI 0.0.88
sandbox image quay.io/rh-aiservices-bu/waterplant-hermes:0.2.7
```

> Clusters here get destroyed and rebuilt. If the API URL above does not answer, everything in the
> **Cluster artifacts** table below is gone with it and the table should be reset, not debugged.

**Anonymisation convention — follow it in every file here.** The repo already states this rule in
`qa-automation/healthcheck-spec.yaml`: *"never name a cluster or a tenant … by the time anyone reads
this the cluster is gone, the name resolves to nothing, and it reads as a fact that can be checked
when it cannot. Durable identifiers — git revisions, chart and image versions, resource names — are
kept."* These documents violated it until 2026-11-23 and have been scrubbed.

| Use | Not |
|---|---|
| `<user>`, `<user2>`, `<user3>` | real tenant ids |
| `<apps-domain>`, `sso.<apps-domain>`, `api.<cluster>.example.com` | real hostnames |
| `<uuid>`, `<operator-uuid>` | realm/client/user UUIDs |
| `<lab secret>`, `<realm admin password>`, `<operator password>` | the literal values |
| chart tags, image tags and digests, versions, file paths, line numbers | — these are durable, keep them |

Lab credentials stay literal in `values.yaml`, where they are functional and already carry comments
explaining why they are not secrets. They are placeholders **in prose only**.

## Status

| Stage | State | Notes |
|---|---|---|
| 0 · Sandbox up | **done** | verified end to end; console answers a plant query from the sandbox |
| 1 · Keycloak realm deltas | **done** | exchange verified working on RHBK 26.4.18 |
| 2 · Sandboxed agent uses exchanged token | **done** | durable — the in-sandbox refresher loop now exchanges every 300s |
| 3 · Enforce the intersection | **done** | all four cases verified on the real traffic path |
| 4 · Into git, on a branch | **partly done** | chart changes landed alongside each stage; three things remain — see below |
| 5 · Install ZTWIM | not started | |
| 6 · SVID to a workload | not started | |
| 7 · Upgrade OpenShell | **blocked** | needs a sandbox-image rebuild, and rebuilds currently lose `skip_auth` |
| 8 · SVID as client auth | not started | **route chosen: JWT-SVID via Federated Client Auth.** Needs `--features=client-auth-federated,spiffe` on the RHDP-owned Keycloak CR |
| 9 · Provenance | not started | needs images from you |

## Waiting on you

**Nothing blocking.**

`quay.io/rlundber/waterplant-hermes:test2` is pushed, verified and in use. Before merge, the image
must move to the `rh-aiservices-bu` org and `tenant-openshell/values.yaml` `sandbox.image` updated —
flagged with a `TEMPORARY, THIS BRANCH ONLY` comment there.

**Nothing to `git push` yet.** 12 workshop files (+384/-1) and one sister-repo file (+60), all
uncommitted. Say when.

**Two standing rules this episode produced, worth keeping:**

- **Never overwrite an image tag — always a new one.** Sandbox pods run `imagePullPolicy:
  IfNotPresent` (the vendored chart leaves `sandboxImagePullPolicy` empty, and Kubernetes defaults
  to `Always` only for `:latest`). A node that has pulled a tag keeps serving the old layers while
  `sandbox list` still says `Ready` — so a fix looks like it did not work when it was never pulled.
- **Verify a rebuild kept `skip_auth` before bumping:**
  `podman run --rm <image> sh -c 'grep -rl skip_auth /usr /app /opt'`

## Cluster artifacts

Everything created or changed on the cluster, with the settings used, so it can be audited or
reverted without reading the log below. **Nothing here is GitOps-managed unless the row says so.**

### Created

| # | Artifact | Where | Settings | GitOps? | How to remove |
|---|---|---|---|---|---|
| C1 | OpenShell gateway registration `openshell-gw` | bridge `cli` container, `/home/cli/.config` | endpoint `https://<user>-openshell.<user>-agentops.svc.cluster.local:8080`, type `local`, auth `mtls` | no | `openshell gateway delete openshell-gw` (container-local; lost on pod restart) |
| C2 | Sandbox `hermie` (k8s: `default--hermie`) | `<user>-agentops` | image `quay.io/rh-aiservices-bu/waterplant-hermes:0.2.7`, cpu `2`, memory `4Gi`, `--no-tty`, `--provider maas` | **no** — created imperatively, nothing reconciles it | `openshell sandbox delete hermie` |
| C3 | Exposed service `openai` on `hermie` | OpenShell gateway | sandbox port `8080` → relayed as `default--hermie--openai.openshell.localhost` | no | `openshell service unexpose hermie openai` |
| C4 | Sandbox network rule `mcp_gateway` | `hermie` policy v2 | `mcp-gateway-data-science-gateway-class.<user>-agentops.svc.cluster.local:8080:full:rest:enforce`; binaries `/usr/bin/python3`, `/usr/bin/python3.12`, `/usr/local/bin/hermes` | no | `openshell policy update hermie --remove-rule mcp_gateway --wait` |
| C5 | Sandbox network rule `keycloak_token` | `hermie` policy v3 | `sso.<apps-domain>:443:full:rest:enforce`; binaries `/usr/bin/python3`, `/usr/bin/python3.12` | no | `--remove-rule keycloak_token` |
| C6 | Sandbox network rule `model_endpoint` | `hermie` policy v4 | `maas-rhdp.apps.maas.redhatworkshops.io:443:full:rest:enforce`; binaries python3, python3.12, hermes | no | `--remove-rule model_endpoint` |
| C7 | Sandbox network rule `mlflow_tracing` | `hermie` policy v5 | `hermes-mlflow-relay.<user>-agentops.svc.cluster.local:8788:full:rest:enforce`; binaries python3, python3.12, hermes | no | `--remove-rule mlflow_tracing` |
| C8 | Protocol mapper `aud-hermes-agent` | realm `waterplant-<user>`, client `mcp-gateway` | `oidc-audience-mapper`, `included.client.audience: hermes-agent`, `access.token.claim: true` | no — realm import is one-shot (`--override=false`) | `DELETE /admin/realms/<realm>/clients/<id>/protocol-mappers/models/<mapperId>` |
| C9 | Protocol mapper `preferred-username` | same client | `oidc-usermodel-property-mapper`, `user.attribute: username`, `claim.name: preferred_username` | no | as above |
| C10 | **Client `hermes-agent`** | realm `waterplant-<user>` | `publicClient: false`, **`serviceAccountsEnabled: false`**, `directAccessGrantsEnabled: false`, `standardFlowEnabled: false`, `fullScopeAllowed: true`, `defaultClientScopes: [roles, groups]`, `attributes.standard.token.exchange.enabled: "true"`, secret `<lab secret>` | no | `DELETE /admin/realms/<realm>/clients/<id>` |
| C11 | Protocol mapper `aud-mcp-gateway-resource` | client `hermes-agent` | `oidc-audience-mapper`, `included.custom.audience: http://mcp-gateway-data-science-gateway-class.<user>-agentops.svc.cluster.local:8080/mcp` | no | as C8 |
| C12 | Protocol mapper `preferred-username` | client `hermes-agent` | same config as C9 — added so the exchanged token names a readable actor, not just a UUID | no | as C8 |

| C13 | `/sandbox/lab-share/` | inside sandbox `hermie` | holds the patched refresher **and** a copy of `plugins/` (SHARE drives the `hermes_otel` copy too — see the log below) | no | delete the dir and remove the `hermes-env.sh` block |
| C14 | Patched `mcp-token-refresh.py` | `/sandbox/lab-share/` | byte-identical to the repo copy; exchanges when `MCP_EXCHANGE_CLIENT_ID` is set, fails closed otherwise | no | as C13 |
| C15 | exchange env appended to `hermes-env.sh` | `/sandbox/hermes/hermes-env.sh` | `MCP_EXCHANGE_CLIENT_ID=hermes-agent`, `MCP_EXCHANGE_CLIENT_SECRET=<lab secret>`. **No `SHARE` override** — the `:test2` image carries the exchange itself | no — uploaded into the sandbox, **not** the bridge ConfigMap (that one selfHeals) | strip the block and re-run `start-hermes` |
| C16 | **second predicate on `mcp-authz-policy`** | `<user>-agentops` | `has(auth.identity.azp) && auth.identity.azp == 'hermes-agent'`, appended to `tool-access-check.patternMatching.patterns` | the AuthPolicy is GitOps-managed but `<user>-policy` has selfHeal **off**, so the live patch persists | `oc patch ... --type=json -p '[{"op":"remove","path":"/spec/rules/authorization/tool-access-check/patternMatching/patterns/1"}]'`, or `argocd app sync <user>-policy` |

Active sandbox policy version: **5**.
Realm internal ids (this cluster only): `mcp-gateway` = `<uuid>`,
`hermes-agent` = `<uuid>`, user `operator` =
`<operator-uuid>`.

### Modified

| # | Artifact | Where | Change | GitOps? | How to revert |
|---|---|---|---|---|---|
| M1 | `deployment/water-plant-ui` env `AGENT_URL` | `<user>-agentops` | `http://hermes-plain…:8787` → `http://hermes-agent.<user>-agentops.svc:8787` | **yes**, but in the platform Application's `ignoreDifferences`, so the edit persists | `oc set env deployment/water-plant-ui -n <user>-agentops AGENT_URL=http://hermes-plain.<user>-agentops.svc:8787` |

### Deleted

_(none)_

## Source changes (git) tracking the cluster

Kept in step deliberately, so nothing found by hand is lost. **Not yet pushed.**

| File | Change | Matches cluster artifact |
|---|---|---|
| `automation/gitops/tenant-platform/templates/mcp-gateway.yaml` | two protocol mappers on `mcp-gateway`; the `hermes-agent` client with its two mappers; all gated on `keycloak.agentIdentity.enabled` | C8, C9, C10, C11, C12 |
| `automation/gitops/tenant-platform/values.yaml` | new `keycloak.agentIdentity` block — `enabled`, `clientId`, `clientSecret` | — |
| `automation/gitops/tenant-platform/files/apply-realm-identity.sh` | idempotent REST replay of the same delta, for tenants that already exist (a realm import applies once, so the chart alone never reaches them) | C8–C12 |
| `automation/gitops/tenant-platform/files/mcp-token-refresh.py` | +60: RFC 8693 exchange after the password grant, env-gated on `MCP_EXCHANGE_CLIENT_ID`, **fails closed** | C14 |
| `automation/gitops/tenant-openshell/files/mcp-token-refresh.py` | kept byte-identical (repo invariant) | C14 |
| `tenant-platform/templates/agent-hermes.yaml`, `agent-hermes-plain.yaml` | +8 each: the exchange env on the `&tokenEnv` anchor, so both the `seed-token` init container and the `mcp-token-refresh` sidecar get it | — |
| `tenant-openshell/templates/bridge.yaml` | +6: the same env on the supervisor container | — |
| `tenant-openshell/files/bridge-supervisor.sh` | +2: exports it into the sandbox through `prepare()`'s `hermes-env.sh` heredoc | C15 |
| `tenant-openshell/values.yaml` | +10: its own `keycloak.agentIdentity` block | — |
| `bootstrap-tenant/templates/applications.yaml`, `openshell.yaml`, `values.yaml` | +47: forwards `agentIdentity` to **both** tenant charts from one place | — |

**Totals: 12 files, 365 insertions, 0 deletions**, plus `apply-realm-identity.sh`. Nothing existing
removed or rewritten.

Verified with `helm template`: the rendered realm import matches the live realm field for field —
`publicClient`, `serviceAccountsEnabled`, `directAccessGrantsEnabled`, `standardFlowEnabled`,
`fullScopeAllowed`, `defaultClientScopes`, the exchange attribute, and all four mappers.

## Log

### 2026-11-23 — Stage 0 begins

Pre-flight facts read from the live tenant (authoritative over the chart, in case `0.0.2` moved
anything):

| | |
|---|---|
| `SANDBOX_NAME` | `hermie` |
| `IMAGE_REF` | `quay.io/rh-aiservices-bu/waterplant-hermes:0.2.7` |
| `SANDBOX_CPU` / `SANDBOX_MEMORY` | `2` / `4Gi` |
| `GATEWAY_URL` | `https://<user>-openshell.<user>-agentops.svc.cluster.local:8080` |
| `MCP_GATEWAY_URL` | `http://mcp-gateway-data-science-gateway-class.<user>-agentops.svc.cluster.local:8080/mcp` |
| `MODEL_BASE_URL` | `https://maas-rhdp.apps.maas.redhatworkshops.io/v1` |
| MLflow relay | `hermes-mlflow-relay.<user>-agentops.svc.cluster.local:8788` |
| docs site | `waterplant-docs:8080` |

Starting state: no sandbox exists, console `AGENT_URL` points at `hermes-plain`, supervisor log
reads *"waiting for the participant to start Hermes in sandbox hermie and expose it"*.

### 2026-11-23 — Stage 0 complete

All six steps of module 2 replayed on `<user>`. Sequence and outcomes:

1. Gateway registered and selected — `✓ TLS certificates present`, auth `mtls`.
2. Sandbox created — `Ready` in ~30s (supervisor image 30 MB, Hermes image 1.8 GB).
3. `/hermes` uploaded to `/sandbox`, 12 files.
4. First `start-hermes` — **failed as designed**, reproducing the module-2 teaching moment:
   `could not fetch an MCP token … the sandbox policy does not let python3 reach Keycloak`.
5. Four network rules applied, policy versions 2→5.
6. `start-hermes` again — MCP token acquired, 18 roles across 3 clients.
7. `service expose hermie 8080 openai`; the bridge logged `adopted sandbox hermie`.
8. Console `AGENT_URL` repointed; rollout completed.

**The "before" artifact, reproduced on this cluster and on the sandboxed path specifically:**

```
/sandbox/.hermes/mcp-tokens/gateway.json
CLAIMS: [azp, exp, groups, iat, iss, jti, resource_access, scope, sid, typ]
  azp: mcp-gateway    sub: ABSENT    aud: ABSENT
  resource_access: 18 roles across 3 clients
```

Identical to the finding recorded in [00-verification-findings.md](00-verification-findings.md) on
the previous (destroyed) cluster. The claim holds for the sandboxed runtime, not just `hermes-plain`.

**End-to-end verification.** `POST /api/chat` with *"What's the status of pump 4?"* returned:

> Pump 4 is running at 100% speed with a discharge pressure of 3.43 bar, bearing temperature of
> 64.7 °C, and vibration at 6.53 mm/s… wear estimate of 0.55.

Vibration 6.53 mm/s against a 4.5 limit and wear 0.55 match the seeded fault documented in
`tenant-platform/values.yaml`, so the tool path is genuinely working rather than the model
confabulating. A trace field was present in the response, and `/api/config` reports
`identityPropagated: false` — the console correctly declaring the gap this work exists to close.

**One loose end, not blocking.** `hermes_otel` logs
`⚠ mlflow unreachable at hermes-mlflow-relay…:8788 (name does not resolve)` at startup even with
the `mlflow_tracing` rule active. The rule permits the endpoint; this looks like DNS resolution
inside the sandbox at plugin-init time rather than a policy denial — no `DENIED` event names the
relay. Traces may still be dropped. Parked: it affects module 2's trace step, not the identity
work, and Stage 3 verifies against Authorino's log rather than MLflow.

### 2026-11-23 — Stage 1 complete: **the exchange works on RHBK 26.4.18**

This was the decisive test, and it passed. Sequence:

**1. Two mappers on `mcp-gateway`.** Both `HTTP 201`. The operator's password-grant token changed
immediately:

```
before:  [azp, exp, groups, iat, iss, jti, resource_access, scope, sid, typ]
after:   [aud, azp, exp, groups, iat, iss, jti, preferred_username, resource_access, scope, sid, typ]
           ^^^                                   ^^^^^^^^^^^^^^^^^^
  aud: hermes-agent        preferred_username: operator        18 roles intact
```

That is stage 2 of the three-stage diagram, and **the first time a human is named in that token**.
Note Keycloak emitted `aud: hermes-agent` even though the client did not exist yet — the mapper
writes the configured string without resolving it.

**2. Client `hermes-agent` created** with the settings in C10. `serviceAccountsEnabled: false`
confirmed on read-back, which is what keeps its secret defensible.

**3. The exchange.**

```
POST /realms/waterplant-<user>/protocol/openid-connect/token
  grant_type=urn:ietf:params:oauth:grant-type:token-exchange
  client_id=hermes-agent  client_secret=…
  subject_token=<operator token>
  subject_token_type=urn:ietf:params:oauth:token-type:access_token
```

Result — `issued_token_type: urn:ietf:params:oauth:token-type:access_token`:

```
sub:                <operator-uuid>   (= operator's user id, confirmed)
preferred_username: operator
azp:                hermes-agent
aud:                http://mcp-gateway-data-science-gateway-class.…:8080/mcp
jti:                present
resource_access:    18 roles — telemetry 6, maintenance 5, control 7
```

**That is stage 3 of the diagram, exactly as designed.** One signed token now asserts: the operator
is the principal, `hermes-agent` is the software acting for them, scoped to the gateway resource,
carrying precisely the operator's permissions and no more.

### Two findings that improve on the design

**`sub` is present on the exchanged token**, even though the password-grant token has none. The
exchange adds it, and it matches the operator's user id. The design assumed we would have to settle
for `preferred_username` because the realm import replaced away the `basic` scope — we get both.
`04-keycloak-upgrade-path.md` and `06-provenance.md` should be amended: the actor's subject can be a
real `sub`, with `preferred_username` as the readable form rather than the only form.

**`preferred_username` had to be added to `hermes-agent` too.** The first exchange returned it as
`ABSENT` — mappers live per client, and the exchanged token is issued *by* `hermes-agent`, so it
only carries that client's mappers plus the shared scopes. Added as C12; the re-exchange then
carried both `sub` and `preferred_username`. Worth noting in the chart work: any claim the actor
chain depends on must exist on **both** clients.

### Not yet proven

The exchange works at the token endpoint. Nothing has yet presented an exchanged token *to the
gateway* — that is Stage 2 — and no policy yet requires the agent identity, so this changes no
behaviour for anyone. The live sandboxed agent is still using its ordinary password-grant token.

### 2026-11-23 — Corrections after review

**Two mistakes of mine, both caught in review rather than by me.**

**1. "The exchanged token is issued by hermes-agent" was wrong.** Keycloak issues it — Keycloak is
the `iss`. The token is issued **to/for** the client `hermes-agent`, which is why `azp` names that
client and why only that client's protocol mappers applied. SPIRE is not involved anywhere in the
current work and is not installed. Clarified in the new
[10-tool-call-walkthrough.md](10-tool-call-walkthrough.md), which also draws the SPIRE boundary
explicitly: the SVID never reaches the gateway and is never the tool-call credential.

**2. The Stage 8 ranking was backwards on fidelity.** I ranked "Authorino validates the SVID
directly" as the leading option on grounds of *likelihood of working*, without flagging that it
**diverges from Uber**. Uber's SVID goes to their STS, never to their gateway, so their enforcement
point sees one credential with attestation folded in. The route that matches is **mTLS with an
X509-SVID to Keycloak**, where Keycloak plays the STS role. Stage 8 now leads with that, and names
the axis the earlier draft hid: *likely to work* versus *faithful to the reference model*. Root
cause of the divergence: Uber built their own STS and could make it accept SPIFFE; Keycloak was not
designed to.

Amended: [09](09-implementation-plan.md) Stage 8, [03](03-uber-mapping.md), and
[10](10-tool-call-walkthrough.md).

**Process change: diagrams are now rendered, not eyeballed.** A `Note over` in a sequence diagram
contained a semicolon, which Mermaid treats as a statement separator, and the diagram failed to
parse for the reader. All 17 diagrams across the doc set now render clean through
`@mermaid-js/mermaid-cli` 11.17.1, and that check runs before any diagram is published. The parens
and square brackets I was also suspicious of turned out to be fine — worth knowing, so as not to
churn them later.

### 2026-11-23 — Why Route B was promoted, and why that was wrong

Asked to account for how the two-token route became the leading option when the one-token route is
both closer to Uber and arguably better. Traced it, and it was my reasoning error, not a data one.

**The sequence.**

1. `05-spiffe-and-ztwim.md`, written before the source list, ranked:
   *Option 1 — `tls_client_auth` with an X509-SVID (**probably the better fit**)*;
   *Option 2 — `private_key_jwt` with a JWT-SVID*; then
   *Fallbacks: 1. two-listener cryptographic AND, 2. keep the secret.*
   So mTLS led and "Authorino validates" was a **fallback**.
2. The source list produced Keycloak issue #41907: a JWT-SVID cannot be used as a client assertion
   on stock Keycloak — `jti` is required and SPIRE does not issue it, and `iss`/`sub` must equal the
   client id.
3. I rewrote Stage 8 and **promoted the fallback to leading**, demoting mTLS.

**The error.** Finding (2) kills **option 2 only**. It says nothing whatever about mTLS, because
mTLS involves no claim reconciliation — there is no assertion, no `jti`, no `iss`/`sub` to match.
I generalised *"Keycloak cannot consume a **JWT**-SVID"* into *"Keycloak cannot consume an SVID"*,
and that generalisation is false. The justification I wrote for the promotion — "Keycloak's problems
are all about reconciling an SVID with a client identity" — is true of option 2 and not of option 1,
so it did not support the reordering it was used for.

Compounding it: I ranked on *likelihood of working*, let the unverified mTLS ingress-termination
risk push option 1 down, and never surfaced fidelity as a separate axis — so the trade-off was made
silently rather than offered.

**Corrected.** Stage 8 now leads with mTLS, names both axes explicitly, and
[10](10-tool-call-walkthrough.md) carries the two diagrams and the practical difference (one
credential at the AuthPolicy versus two). Also recorded there: Route B *also* needs the OpenShell
upgrade, since the SVID has to reach the agent's outbound call and only OpenShell's provider
machinery can put it there — which removes the "easier" argument that drove the promotion.

**Also corrected in the same pass:** "the broker" was used throughout without ever being defined.
It is a *role* — whatever mints the token and writes `gateway.json` — played today by
`mcp-token-refresh.py`, which on the sandboxed path runs **inside the sandbox**, baked into the
image. Now stated in [10](10-tool-call-walkthrough.md).

**And a correction to an idea of my own:** putting the broker in the bridge pod keeps the SVID out
of the sandbox, but the bridge is a *different workload*, so the SVID would attest **the bridge,
not the agent**. Uber attests the workload that acts; OpenShell attests the pod containing the
actor; the bridge idea attests the pod that mints. Three different claims. OpenShell's supervisor
model is the closest practical match to Uber and is the vendor-supported path — which is an argument
for doing the upgrade rather than routing around it.

### 2026-11-23 — Correction: JWT-SVID client auth is supported, and I had it wrong

Asked to re-check whether Keycloak #41907 had been fixed. It had — and more importantly it was
never the blocker I reported it as.

**What I got wrong, and how.** #41907 was closed as a **duplicate** of #42634 "Federated client
authentication". I read the closure and the maintainer line *"Milestone 1 is a dead-end, we should
move straight to milestone 2"* as a rejection of the whole idea. It was the opposite: a decision to
implement it a different way. **I never opened the duplicate target.** Milestone 2 shipped.

This is the second time in this work I stopped at the first finding instead of following the
thread — the first was generalising "Keycloak cannot consume a JWT-SVID" from a result that only
concerned one binding. Same failure mode, so worth naming rather than just fixing.

**What is actually true, verified on this cluster rather than from a blog:**

```
$ kc.sh build --help-all   # on keycloak-0, RHBK 26.4.18
  ... client-auth-federated[:v1] ... spiffe[:v1] ...
      kubernetes-service-accounts[:v1], token-exchange-external-internal[:v2],
      admin-fine-grained-authz[:v1,v2] ...

$ oc get keycloak keycloak -n keycloak -o jsonpath='{.spec.features}'
  (empty)
```

- Federated Client Authentication arrived in Keycloak **26.4.0**; supported in 26.6.0 for OIDC and
  K8s service accounts, with **SPIFFE still preview** because `draft-ietf-oauth-spiffe-client-auth`
  is a draft.
- **Both features exist in our build.** They are simply not enabled.
- Issue #43394 — SPIFFE auth NPE'd when the SVID carried `iss` — was **fixed in 26.4.1**. We run
  26.4.18, so we are past it. That bug would certainly have hit us, since SPIRE SVIDs do carry `iss`.

**Consequence.** Stage 8 is reordered again, and this time the leading route is the one originally
suggested: **JWT-SVID via Federated Client Authentication**. It is Uber's shape (SVID → Keycloak as
STS → one token at the gateway), it is what OpenShell already emits, it is layer 7 so no ingress
surgery, and the only blocker is enabling `--features=client-auth-federated,spiffe` on the
RHDP-owned Keycloak CR — a request to make, not a capability that is missing.

mTLS/X509 drops to the no-flag fallback; Authorino-validates drops to last resort.

**Standing lesson for the rest of this work:** a closed issue is not a closed question. Check the
duplicate target, check the shipped version, and check the feature list on the actual server before
reporting something as unavailable.

### 2026-11-23 — Stage 2 complete: the sandboxed agent presents the exchanged token

Took two passes, because the first one was not durable.

**Pass 1 — proof, but transient.** Did the exchange *outside* the sandbox (from an admin shell) and
wrote the result straight into `/sandbox/.hermes/mcp-tokens/gateway.json`. The sandboxed agent
immediately answered a plant query with correct live telemetry, **with no restart** — confirming
`MCPOAuthManager.invalidate_if_disk_changed` behaves as documented.

Then checked what else writes that file, and found the problem:

```
$ ps -eo args   # inside the sandbox
  python3 /usr/local/share/hermes-lab/mcp-token-refresh.py --loop 300
```

`refresh_once()` is called **unconditionally every cycle** — there is no "only if expiring soon"
guard — so the in-sandbox refresher would have overwritten the exchanged token with a plain
password-grant one within five minutes. Under Stage 3 enforcement that would have broken the agent
a few minutes after every test, intermittently, which is exactly the kind of fault that costs hours.
Worth catching before enforcement, not after.

**Pass 2 — make the in-sandbox refresher the exchanging one.** Patched the refresher in the repo
*first*, then pushed that exact file into the sandbox, so source and cluster stay in step.

The `SHARE` mechanism, verified on the running image rather than assumed:

```
start-hermes:19  SETUP=/sandbox/hermes
             20  SHARE=/usr/local/share/hermes-lab
             27  . "$SETUP/hermes-env.sh"        <-- can override SHARE
             39  cp -r "$SHARE/plugins/hermes_otel" ...
             60  python3 "$SHARE/mcp-token-refresh.py"
             65  ... "$SHARE/mcp-token-refresh.py" --loop $TOKEN_REFRESH_SECONDS
```

So the override redirects the refresher **and** the `hermes_otel` plugin copy. That was assumption
A8 in [08-open-questions.md](08-open-questions.md); it is now a confirmed requirement — the override
directory must carry `plugins/` or tracing silently stops. It does, and `hermes_otel` is still
present in `/sandbox/.hermes/plugins/` afterwards.

**Result.**

```
$ ps -eo args            python3 /sandbox/lab-share/mcp-token-refresh.py --loop 300
$ tail mcp-token-refresh.log
    exchanged operator token for one acting as hermes-agent
    token written to /sandbox/.hermes/mcp-tokens/gateway.json (expires_in=1800s, 30min)
$ decode gateway.json     azp: hermes-agent   user: operator   roles: 18
```

End-to-end: *"Which pumps are running and what is the reservoir level?"* →
*"Pumps 1, 2, and 4 are running. Pump 3 is stopped. The reservoir level is at 63.45% of capacity."*
Multiple tool calls, correct state. The only `DENIED` events are to `openrouter.ai` — unrelated
background noise, and correct default-deny behaviour.

### A posture finding worth carrying into Stage 8

The sandbox **already holds the operator's password**. `hermes-env.sh` contains `MCP_USERNAME`,
`MCP_PASSWORD` and `API_SERVER_KEY`, so a compromised agent could already mint operator tokens at
will. Adding `MCP_EXCHANGE_CLIENT_SECRET` is therefore not a new class of exposure — but it is not
an improvement either, and it is worth being explicit that this POC does not change that posture.

What *would*: doing the exchange outside the sandbox entirely, as pass 1 did. Then the sandbox holds
only a 30-minute token and can mint nothing. That is the same argument as the bridge-held SVID in
[10](10-tool-call-walkthrough.md), with the same caveat — the bridge is a different workload, so it
attests the minter rather than the actor. Stage 8 should decide this deliberately rather than
inheriting pass 2's shape by default.

### Incident: wrong cluster

Midway through, `oc` was pointed at a different cluster (`api.a different cluster`) and every
Stage 0/1 artifact appeared to be gone. It was not — the context had simply changed. Switched back
with `oc config use-context` and re-verified all of it intact: sandbox up, `AGENT_URL` repointed,
the `hermes-agent` client, all four mappers, and the exchange still returning `azp=hermes-agent`
with 18 roles.

**Lesson, now a standing check:** confirm `oc whoami --show-server` matches the API URL in the
cluster-facts block before touching anything, rather than inferring a rebuild from missing objects.

### 2026-11-23 — Gap found and closed: the script was wired to nothing

Asked whether the refresher patch was actually in the source tree. It was — but the check exposed a
real gap I had missed, and "local" was sloppy phrasing on my part for "not pushed".

**The gap.** `mcp-token-refresh.py` was patched in both copies, but the exchange is **env-gated on
`MCP_EXCHANGE_CLIENT_ID`** and *nothing set it*:

```
$ grep -rl MCP_EXCHANGE_CLIENT_ID automation/gitops/
  automation/gitops/tenant-openshell/files/mcp-token-refresh.py
  automation/gitops/tenant-platform/files/mcp-token-refresh.py      # ...and that was all
```

A freshly provisioned tenant would have taken the new script and **silently never exchanged** —
the worst failure shape available, because everything looks healthy and the token quietly stays
`azp=mcp-gateway`. It worked on `<user>` only because I had set the variables by hand in the
sandbox's `hermes-env.sh`.

**Closed in five places**, following the existing `MCP_PASSWORD` wiring exactly:

| Where | What |
|---|---|
| `agent-hermes.yaml`, `agent-hermes-plain.yaml` | added to the `&tokenEnv` YAML anchor — one edit covers the init container *and* the sidecar in each |
| `bridge.yaml` | supervisor container env |
| `bridge-supervisor.sh` | exported into the sandbox via the `hermes-env.sh` heredoc |
| `tenant-openshell/values.yaml` | its own `keycloak.agentIdentity` block |
| `bootstrap-tenant` | forwards to **both** tenant charts from a single source |

That last one is not tidiness. `tenant-platform` *creates* the client in the realm and
`tenant-openshell` *hands its secret* to the refresher, so if the two defaults ever drift the
exchange fails `401` with nothing naming the cause. Forwarding both from `bootstrap-tenant` makes
drift impossible — the same reasoning the repo already applies to `namespaceSuffix` and
`gatewayName`.

**Verified by rendering, not by reading:**

```
tenant-platform    → 4 containers wired  (hermes-plain + hermes-agent, each sidecar + init)
tenant-openshell   → bridge/supervisor wired; heredoc exports it into the sandbox
bootstrap-tenant   → agentIdentity forwarded to platform AND openshell; policy/guardrails get none
```

**A verification bug worth recording too.** My first render check reported "0 containers wired" and
I nearly went looking for a chart bug. The cause was `helm template … | tee /tmp/x.yaml | head -2`
— `head` closes the pipe, `tee` takes SIGPIPE, and the file is truncated. The chart was fine; the
check was broken. Redirect to a file and inspect it separately.

### 2026-11-23 — Second wiring gap: the sandbox image has a third copy

Asked whether the sister repo needed anything yet. It did, and finding out exposed a gap of the
same class as the env-wiring one.

**There are three copies of `mcp-token-refresh.py`, not two:**

| Copy | Used by |
|---|---|
| `workshop/.../tenant-platform/files/` | the `hermes-plain` / `hermes-agent` sidecar + init container |
| `workshop/.../tenant-openshell/files/` | mounted into the bridge at `/config` |
| **`agentops-rh1-lab/hermes-openshell/`** | **COPY'd into the sandbox image** (`Containerfile:103` → `/usr/local/share/hermes-lab/`) — the one the sandbox actually runs |

Before this change all three were equivalent. After patching only the two workshop copies they had
diverged, and the `SHARE` override existed purely to route around the stale third one. Its `M` in
git was pure CRLF noise — `--ignore-all-space` showed no real changes.

**Two consequences I had not stated.**

*The Stage 2 setup would not have survived module 4.* That module has participants
`openshell sandbox delete hermie` and recreate (module-04 lines 121, 131), which wipes
`/sandbox/lab-share` and the hand-edited `hermes-env.sh`. The exchange would have silently stopped
partway through the lab.

*`bridge-supervisor.sh` publishes eleven files into `/hermes` and the refresher was not one of
them.* [09](09-implementation-plan.md) Stage 4 said to publish it **and** add the env; I had done
only the env — the same half-done shape as the previous gap.

**Closed both ways:**

- **Chart (works today, no rebuild):** `bridge-supervisor.sh` now does
  `publish /config/mcp-token-refresh.py mcp-token-refresh.py`, and the `hermes-env.sh` heredoc
  creates `/sandbox/lab-share`, copies the uploaded refresher and the image's `plugins/` into it,
  and points `SHARE` there. Because it rides the participant's own `/hermes` upload it **survives
  sandbox recreation**. The block carries a comment saying to delete it once the image is rebuilt.
- **Sister repo (durable):** patched `hermes-openshell/mcp-token-refresh.py` with the identical
  block. All three copies are equivalent again. Needs an image build — listed under **Waiting on
  you**.

**Lesson, and it is the same one twice:** patching a file is not the same as making it run. Both
gaps were "the code is in the tree but nothing reaches it". Worth checking, for each change: who
reads this file, and is every copy of it reached?

### 2026-11-23 — `:test1` verified: exchange works, image regresses `skip_auth`

Image confirmed before bumping anything (public, `sha256:392c5c50...`, 612 MB compressed). Bumped
`sandbox.image`, then deleted and recreated the sandbox — which also exercises module 4's
delete-and-recreate flow.

**What worked — the thing we were testing:**

```
ps:   python3 /usr/local/share/hermes-lab/mcp-token-refresh.py --loop 300   <- the IMAGE copy
log:  exchanged operator token for one acting as hermes-agent
tok:  azp: hermes-agent | user: operator | roles: 18
```

The baked-in refresher does the exchange from **env vars alone**, with no `SHARE` override. The
durable path is proven; the chart workaround is only needed while the image is stale.

**What broke — unrelated to our change.** The console got
`{"error":{"message":"Invalid API key",...}}`. My first read was that MaaS was rejecting an
outbound key; it was not. It was **Hermes' own API server rejecting an inbound loopback call**, and
the image turned out not to implement `skip_auth` at all. Details and the fix are under
**Waiting on you**.

Worth noting how close that was to a wrong diagnosis: the error is OpenAI-shaped and says "Invalid
API key", which reads like a model-credential problem. The placeholder (`openshell:resolve:env:v3`)
and the provider attachment both checked out, and only the Hermes log named the real caller —
`remote='127.0.0.1' path='/v1/chat/completions'`. Inbound, not outbound.

**Restored.** `sandbox.image` reverted to `0.2.7` with a warning comment, sandbox recreated on
0.2.7 with the `SHARE` override, four network rules re-applied, bridge re-adopted, and the console
verified answering with correct telemetry (pump 4 at 6.52 mm/s, wear 0.554) on an
`azp=hermes-agent` token. Back to the end of Stage 2.

### 2026-11-23 — `:test2` verified end to end, workaround deleted

`test2` (`sha256:01b5f7b7b0edc4dd216ee82`, 1.7 MB larger than `test1`) restores the patch:

```
api_server.py:781   self._skip_auth: bool = extra.get("skip_auth", os.getenv("API_SERVER_SKIP_AUTH",""))
api_server.py:979   elif self._skip_auth and not auth_header and request.remote in ("127.0.0.1","::1"):
api_server.py:983       return None  # Auth OK (trusted loopback ingress, skip_auth=true)
refresher           MCP_EXCHANGE_CLIENT_ID present
```

Checked locally with `podman run` before touching the cluster, which cost one pull instead of a
full sandbox rebuild cycle.

**Deployed and verified with no `SHARE` override at all:**

```
ps    python3 /usr/local/share/hermes-lab/mcp-token-refresh.py --loop 300   <- the IMAGE copy
log   exchanged operator token for one acting as hermes-agent
tok   azp: hermes-agent | user: operator | roles: 18
e2e   "Pump 4 ... Vibration: 6.51 mm/s RMS ... Wear estimate: 0.554"
```

So the sandboxed agent presents a token naming both principals, from the image, with only two env
vars supplied — which is exactly what `bridge-supervisor.sh` now sets.

**Workaround removed.** The `SHARE` override and the `publish /config/mcp-token-refresh.py` line are
deleted. I had first made the override self-disabling (a `grep` on the image's refresher), but on
the call that nobody is running an older image that is unnecessary machinery, so it is gone. What
remains in the supervisor is two lines:

```sh
export MCP_EXCHANGE_CLIENT_ID='${MCP_EXCHANGE_CLIENT_ID}'
export MCP_EXCHANGE_CLIENT_SECRET='${MCP_EXCHANGE_CLIENT_SECRET}'
```

`tenant-openshell` renders with zero `lab-share` references and seven `MCP_EXCHANGE` lines.

**A false alarm worth recording.** `bash -n` on the supervisor reported
``syntax error near unexpected token `$'{\r''``. That is the repo-wide CRLF, not a defect I
introduced, and it passes once CR is stripped. Check shell scripts in this repo with
`tr -d '\r' < f | bash -n` or the result is misleading.

### 2026-11-23 — Stage 3 complete: the intersection is enforced

**The probe strategy in the plan was wrong, and the cluster said so immediately.**

[09](09-implementation-plan.md) Stage 3 said to drive the internal `mcps` listener directly, which
would "sidestep the limitation recorded at E2E-M3-03, where the broker answers 400 before Authorino
is consulted". In practice it runs *straight into* it:

```
no auth, WITH    x-mcp-toolname  -> 400  no session ID found
no auth, WITHOUT x-mcp-toolname  -> 401
```

Authorino is in the path — the 401 proves it — but with a tool name present the upstream MCP server
rejects on its missing session *before* an authz verdict is observable. A synthesised `tools/call`
has no session because it never did `initialize`. Four probe variants all returned 400, including
one with a garbage bearer and one naming a tool nobody holds, so the probe was measuring nothing.

Two wrong turns on the way there, both mine: `urllib` would not let me override `Host`, so the
request matched the **`mcp`** listener and the broker rather than `mcps`; and an `eval`-based curl
wrapper mangled its own `-H` quoting. Fixed by using curl directly, which is how the 401/400 split
above was finally seen.

**Tested through the real traffic path instead** — the agent making genuine tool calls, which is
what the enforcement is for. All four cases:

| case | result |
|---|---|
| exchanged token, operator holds the role | answers normally with correct telemetry |
| **raw operator token, holding all 18 roles** | **"I don't have sufficient permissions"** |
| exchanged token, role revoked in Keycloak | refused; agent falls back to another tool |
| `azp` required to be a value nothing holds | refused |

Row 2 is the result Stage 3 exists to produce: **a token carrying the operator's complete permission
set is refused because it is not the agent.** Holding the permission is no longer sufficient. Row 3
is the converse — being the agent is not sufficient either — which is also a regression check that
**module 3's revoke exercise still behaves exactly as before**.

One pleasant surprise: the denial surfaced as *"I don't have sufficient permissions to retrieve the
status of pump 4"*, not the misleading *"network issue or service outage"* that
`mcp-gateway-policy.yaml` warns a 403 produces. Worth confirming whether that improved generally or
is specific to this shape of denial before relying on it in lab content.

**Into source, gated.** `tenant-policy` gains `mcpGateway.agentIdentityEnforced` (**default off**)
and `keycloak.agentIdentity.clientId` — only the id, never a secret, since this chart checks a claim
and never authenticates. `bootstrap-tenant` forwards it only when `keycloak.agentIdentity.enabled`,
so it cannot be switched on without the exchange that makes it satisfiable; that combination would
refuse every tool call. Rendered both ways: `false` → 0 `azp` predicates, `true` → 1.

### A self-inflicted scare worth recording

While restoring the revoked role I wrote `UID=$UID_` into a temp env file. **`UID` is readonly in
bash**, the assignment failed, `$CID` came out empty, and the resulting malformed URL made it look
as though the operator had been stripped to a single telemetry role. It had not — a direct
per-client listing showed 5 + 5 + 7 = 17, exactly one role short as intended. Restored to 6 + 5 + 7
= 18 and re-verified end to end.

The lesson is the ordinary one: when a read looks alarming, re-read with a different command before
reacting. A panicked "repair" against that bad reading would have done real damage.

### 2026-11-23 — Anonymised

Scrubbed cluster hostnames, tenant ids, realm UUIDs and the agent client secret from every document
in this directory, plus one chart comment that named a tenant
(`tenant-policy/templates/mcp-gateway-policy.yaml`). Verified no residual identifiers and that all
19 Mermaid diagrams still render — placeholders use angle brackets, which would be parsed as HTML
inside a diagram label, so that was worth checking rather than assuming.

The convention is above. It is the repo's own, from `healthcheck-spec.yaml`; I simply had not been
applying it.

### What actually remains in Stage 4

Beyond pushing the branch, three things — and the first is the one that matters:

**1. Nothing has ever been tested from cold.** Every stage so far was applied by hand to a tenant
that already existed. The chart wiring — `bootstrap-tenant` forwarding `agentIdentity` to both
tenant charts, the realm import creating the client, `tenant-openshell` putting the env into
`hermes-env.sh`, the refresher reading it — has only been verified by `helm template`. Rendering
proves the YAML is right, not that the chain works. The test: repoint one untouched control tenant's
Applications at the branch, sync, and confirm a cold start produces `azp=hermes-agent`.

   One wrinkle that makes this less than a true cold test: **a realm import applies once**
   (`--override=false`), so repointing an *existing* tenant will not create the `hermes-agent`
   client. That path needs `apply-realm-identity.sh`. A genuinely cold test needs a newly
   provisioned tenant.

**2. `apply-realm-identity.sh` has never been run.** It was written during Stage 1 from the REST
calls I had just made by hand, and it is the only mechanism for existing tenants — but it is
completely unexercised. One of the two control tenants is the obvious place to run it.

**3. Regression check.** Run the existing `E2E-M3-01/04/05` behaviour checks unchanged. Module 3's
revoke exercise was verified by hand during Stage 3 and still behaves correctly, but the suite has
not been run.

Not Stage 4, but must happen before merge: `sandbox.image` points at a personal-org build
(`TEMPORARY, THIS BRANCH ONLY` in `tenant-openshell/values.yaml`) and has to move to
`rh-aiservices-bu`.
