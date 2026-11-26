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
| 4 · Into git, on a branch | **partly done** | committed (`a85b987`); realm script proven; **the plan's Verify step has not run** |
| 5 · Install ZTWIM | **done** | v1.1.3, 15/15 pods, trust domain `agentops.lab`, 95 entries registered |
| 6 · SVID to a workload | **done** | SVID issued and decoded; all three Stage 8 questions answered favourably |
| 7 · Upgrade OpenShell | **done** | chart 0.0.92 → 0.0.116, CLI v0.0.88 → v0.0.116, gateway now mounts the Workload API socket |
| 8 · SVID as client auth | **both routes de-risked** | route 1 needs a Keycloak feature flag we do not own; **route 3 is proven working** and needs nothing from Keycloak. Both still need the SVID on the agent's outbound call (Stage 7) |
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
| C17 | ZTWIM operator | cluster-scoped, ns `zero-trust-workload-identity-manager` | Namespace + OperatorGroup + pinned Subscription, `installPlanApproval: Manual`, `startingCSV: zero-trust-workload-identity-manager.v1.1.3`, channel `stable-v1`, source `redhat-operators`. InstallPlan approved by hand | **no** — applied directly, *not* via the `bootstrap` Application (that is pinned to the released tag and owns shared infra for every tenant) | delete the CRs, then the Subscription and CSV, then the namespace |
| C18 | SPIRE instance | cluster-scoped | five singleton CRs all named `cluster`: `ZeroTrustWorkloadIdentityManager` (trustDomain `agentops.lab`, clusterName `agentops`, bundle `spire-bundle`), `SpireServer` (sqlite3, 2Gi PVC, X509 1h / JWT 5m), `SpireAgent` (k8sPSAT node attestor), `SpiffeCSIDriver` (`csi.spiffe.io`), `SpireOIDCDiscoveryProvider` (managedRoute, 1 replica) | no | `oc delete -f` the five CRs |
| C20 | Keycloak features enabled | `keycloak` CR, ns `keycloak` | `spec.features.enabled: [spiffe, client-auth-federated]`. Both were present in the RHBK 26.4.18 build but in `disabledFeatures`. Restarts Keycloak | **no** — RHDP-provisioned CR, patched directly | `oc patch keycloak keycloak -n keycloak --type merge -p '{"spec":{"features":null}}'` |
| C21 | `<user>-openshell` Application repointed | `openshift-gitops` | `targetRevision: rh1-2027-lb1285-0.0.2` → `spiffe-spire` | yes — this *is* the Argo object | patch `targetRevision` back to the tag |
| C19 | OIDC discovery Route | ns `zero-trust-workload-identity-manager` | host `spire-oidc.<apps-domain>`, created by the operator from `jwtIssuer` | no — operator-managed | removed with the `SpireOIDCDiscoveryProvider` CR |
| C16 | **second predicate on `mcp-authz-policy`** | `<user>-agentops` | `has(auth.identity.azp) && auth.identity.azp == 'hermes-agent'`, appended to `tool-access-check.patternMatching.patterns` | the AuthPolicy is GitOps-managed but `<user>-policy` has selfHeal **off**, so the live patch persists | `oc patch ... --type=json -p '[{"op":"remove","path":"/spec/rules/authorization/tool-access-check/patternMatching/patterns/1"}]'`, or `argocd app sync <user>-policy` |
| C22 | Identity provider `spiffe` | realm `waterplant-<user>` | `providerId: spiffe`, `enabled: true`, `config.issuer: spiffe://agentops.lab`, `config.bundleEndpoint: https://spire-oidc.<apps-domain>/keys`. The trust domain goes in **`issuer`** — `trustDomain` is rejected 400 | no — realm import is one-shot | `DELETE /admin/realms/<realm>/identity-provider/instances/spiffe` |
| C23 | Auth flow `clients-federated` | realm `waterplant-<user>` | a copy of the built-in `clients` flow plus a fifth execution, `federated-jwt`, `ALTERNATIVE`. Bound as the realm's `clientAuthenticationFlow` | no | `PUT /admin/realms/<realm>` with `clientAuthenticationFlow: clients`, then `DELETE .../authentication/flows/<id>` |
| C24 | `jwt.credential.*` on `hermes-agent` | realm `waterplant-<user>` | `jwt.credential.issuer: spiffe`, `jwt.credential.sub: spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell` (the OpenShell gateway). **Staged and inert** — `clientAuthenticatorType` is back to `client-secret` | no | remove the two attributes |

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

| `tenant-platform/templates/mcp-gateway.yaml` | +40 more: the `spiffe` identity provider on the realm, and the client's two `jwt.credential.*` attributes — both gated on `keycloak.agentIdentity.federated.enabled` | C22, C24 |
| `tenant-platform/values.yaml` | +30 more: `keycloak.agentIdentity.federated` — `enabled`, `trustDomain`, `idpAlias`, `bundleEndpoint`, `subjectSpiffeId` | — |
| `tenant-platform/files/apply-realm-identity.sh` | +100: section 3, gated on `FEDERATED_SPIFFE_ID` — creates the IdP, copies and extends the `clients` flow, rebinds it, and switches the client to `federated-jwt` | C22, C23, C24 |
| `bootstrap-tenant/templates/applications.yaml`, `values.yaml` | +40 more: forwards the `federated` block to `tenant-platform` | — |

**Totals (through Stage 8 route 1): 12 files, ~575 insertions, 0 deletions**, plus `apply-realm-identity.sh`. Nothing existing
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

Beyond pushing the branch, three things — and the first is the one that matters.
**Item 2 is now done (2026-11-24); items 1 and 3 are not.**

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

### 2026-11-24 — `apply-realm-identity.sh` proven (Stage 4, item 2)

**What this was, and what it was not.** This exercised Stage 4's *action* "commit the Stage 1 REST
calls as an idempotent script". It is **not** Stage 4's *Verify* step — no Application has been
repointed at the branch, nothing has been synced, no cold start has been done, and the E2E suite
has not run. Those remain outstanding.

**Branch state confirmed first.** Everything is in `a85b987`, including the `agentIdentity`
forwarding in `bootstrap-tenant/templates/{applications,openshell}.yaml` — those two still show as
modified in `git status`, but `--ignore-all-space` confirms the residue is CRLF only and `git show
HEAD:` has the same 14 and 7 occurrences as the worktree. Worth checking rather than assuming,
since a half-committed forwarding would have made the branch quietly incomplete.

**The run.** Against `<user3>`, verified pristine beforehand (no `hermes-agent` client, no mappers
on `mcp-gateway`):

```
realm waterplant-<user3>
  mapper aud-hermes-agent:          created
  mapper preferred-username:        created
  client hermes-agent:              created
  mapper aud-mcp-gateway-resource:  created
  mapper preferred-username:        created
```

Exchange on that tenant, identical to the hand-applied Stage 1:

```
azp: hermes-agent | sub: present | preferred_username: operator
aud: http://mcp-gateway-…<user3>-agentops…:8080/mcp | roles: 18 across 3 clients
```

**Idempotency holds.** A second run reported `already present` five times, left 2 and 2 mappers,
and exactly one `hermes-agent` client. That matters because it is the recovery path for a tenant in
an unknown state.

**Control tenants, corrected.** The plan assumed two untouched controls. `<user3>`'s realm now
carries the delta, so **only `<user2>` is a clean control.** The delta is additive and should be
inert for a tenant that has not opted in — its agent still does a plain password grant, and nothing
there enforces `azp` — but see the unfinished check below.

**Unfinished: is the delta genuinely inert?** It does change live tokens in that realm — every
operator token now carries `aud: hermes-agent` and `preferred_username`. I claimed that is harmless
because Authorino does not enforce `aud`. That is reasoning, not measurement, and this work has
already produced two cases where reasoning of exactly that shape was wrong. The check is two
commands — confirm `<user3>`'s agent still answers, and that its token is still the plain operator
one — but the `oc` session expired (`Unauthorized`) before I could run them. **Do this before
trusting the script against a tenant anyone depends on.**

### 2026-11-24 — Stage 5 complete: ZTWIM installed, SPIRE issuing

**Not applied through Argo, deliberately.** `bootstrap-infra` is owned by the `bootstrap`
Application pinned to the released tag, and it carries shared infrastructure for every tenant.
Repointing it at the branch to install one operator would re-sync all of it. The objects were
applied directly instead and the chart is the durable record — the same split used throughout this
work.

**Install.** Namespace, OperatorGroup and a pinned Subscription, following `operators.yaml`'s
convention exactly. The InstallPlan was worth inspecting before approving, because the approver
refuses plans containing undeclared CSVs:

```
InstallPlan install-xxxxx   approved: False   phase: RequiresApproval
  CSVs: ['zero-trust-workload-identity-manager.v1.1.3']
```

Exactly the pinned CSV and nothing else, which confirms the values entry needs no `dependencies`.
Approved; CSV `Succeeded` within ~30s; all 8 CRDs appeared.

**Two things went wrong, one of them mine.**

*The OIDC Route was rejected, and the cause was my hostname derivation.* I derived the issuer as
`spire-spiffe-oidc-discovery-provider-<namespace>.<domain>`, which puts a **73-character label** in
front of the domain. DNS labels cap at **63**:

```
RouteAvailable: False  ManagedRouteCreationFailed
  spec.host: Invalid value: "spire-spiffe-oidc-discovery-provider-zero-trust-workload-identit…
```

The operator uses `jwtIssuer`'s host verbatim as the Route host, so a long namespace makes that
derivation unusable. Now `spire-oidc.<domain>` by default, overridable via `spire.oidc.host`.

Worth noting it failed **loudly** — `RouteAvailable: False`, `Ready: False` — which is better than
my own template comment predicted ("a mismatch does not fail loudly"). But the deployment and
service were healthy throughout, so a glance at pods would have said everything was fine while the
endpoint the whole Stage 8 design depends on did not exist.

*The agents briefly failed to mount `spire-bundle`.* A startup race: the agents are created before
the server publishes its trust bundle ConfigMap. It self-resolved on kubelet retry — 6 not-ready →
4 → 0 over about a minute. Not a defect, but worth knowing so it is not mistaken for one.

**Verified working.**

```
pods                15/15 ready   (server, 6 agents, 6 CSI drivers, OIDC provider, controller)
trust domain        agentops.lab
discovery           https://spire-oidc.<apps-domain>/.well-known/openid-configuration  -> 200
  issuer            https://spire-oidc.<apps-domain>
  jwks_uri          .../keys
  algs              RS256, ES256, ES384
JWKS                1 key, RSA/RS256, kid present
SpireServer.jwtIssuer == SpireOIDCDiscoveryProvider.jwtIssuer    (they must match)
```

**SPIRE is already issuing identities**, not merely installed. The operator's default
`ClusterSPIFFEID` reports:

```
entriesToSet: 95   entryFailures: 0   podsSelected: 95   namespacesSelected: 93
spiffeIDTemplate: spiffe://{{ .TrustDomain }}/ns/{{ .PodMeta.Namespace }}/sa/{{ .PodSpec… }}
```

**This changes Stage 6.** The plan assumed we would author a `ClusterSPIFFEID` to select the agent
workload. The default one already selects every pod in 93 namespaces, including the lab tenants —
so the bridge and `hermes-plain` almost certainly have registration entries already. Stage 6 may
reduce to mounting a `csi.spiffe.io` volume and reading what is handed over. Confirm before writing
a selector we do not need; a narrower `ClusterSPIFFEID` may still be wanted for clarity about
*which* workload is entitled to the agent identity, which is the Agent Registry role in
[03](03-uber-mapping.md).

### 2026-11-24 — Stage 6 complete: an SVID, decoded

**No `ClusterSPIFFEID` was needed.** The plan assumed one would have to be authored to select the
agent workload. The operator's default already selects every pod in every namespace except its own:

```
namespaceSelector: kubernetes.io/metadata.name NotIn [zero-trust-workload-identity-manager]
podSelector:       <none>
spiffeIDTemplate:  spiffe://{{ .TrustDomain }}/ns/{{ .PodMeta.Namespace }}/sa/{{ .PodSpec.ServiceAccountName }}
```

So every lab workload already had a registration entry. Stage 6 reduced to mounting a
`csi.spiffe.io` volume and reading what was handed over.

**Method.** A throwaway pod in the tenant namespace, running the `spire-agent` image, using the
**bridge's own ServiceAccount** so the SPIFFE ID it receives is exactly what the real broker would
receive. Deliberately not the bridge or `hermes-plain` themselves: both are GitOps-managed with
selfHeal on, so a hand-added volume would be reverted. Deleted afterwards.

**X509-SVID:**

```
SPIFFE ID:   spiffe://agentops.lab/ns/<user>-agentops/sa/hermes-openshell-bridge
Valid:       1h   (matches spire.server.defaultX509Validity)
CA valid:    24h  (matches spire.server.caValidity)
```

**JWT-SVID, requested with `aud` = the Keycloak realm issuer:**

```
header  {"alg":"RS256","kid":"cFxBePEc…","typ":"JWT"}
aud     ["https://sso.<apps-domain>/realms/waterplant-<user>"]
iss     https://spire-oidc.<apps-domain>
sub     spiffe://agentops.lab/ns/<user>-agentops/sa/hermes-openshell-bridge
exp-iat 300s   (matches spire.server.defaultJWTValidity)
```

### The three questions, answered

| Question | Answer | Consequence |
|---|---|---|
| Is `iss` present, and what is it? | **Yes** — the SPIRE OIDC discovery provider | This is the exact claim behind Keycloak [#43394](https://github.com/keycloak/keycloak/issues/43394), the NPE when an SVID carries `iss`. **Fixed in 26.4.1; we run 26.4.18.** We would have hit it on an older patch release |
| Is `sub` the SPIFFE ID? | **Yes** | Matches what federated client authentication expects: `sub` = `spiffe://<trust-domain>/<client>` |
| Can `aud` be set to the realm issuer? | **Yes**, per-request | Matches the `aud` = realm issuer URL requirement |

All four of Keycloak's documented requirements for a SPIFFE client assertion are therefore
satisfiable by what SPIRE actually emits here: `sub`, `aud`, a future `exp`, and an `iss` that the
fixed code ignores.

**And the chain closes.** The SVID's `kid` (`cFxBePEc…`) is the single key published at
`https://spire-oidc.<apps-domain>/keys` — so anything that can read that JWKS can verify this
token, with no SPIFFE awareness at all. That is the property both Stage 8 routes depend on:
Keycloak federated client auth, and Authorino validating the SVID directly.

**What is still unproven for Stage 8.** Only one thing, and it is not technical: the
`client-auth-federated` and `spiffe` features are present in the RHBK build but **not enabled**
(`features: null` on an RHDP-owned CR). Everything on our side of that flag now checks out.

### 2026-11-24 — Authorino validates a SPIFFE SVID directly (Stage 8, route 3 proven)

Stage 7 is blocked on an image rebuild and Stage 8's preferred route needs a Keycloak feature flag
that is not ours to set — so the useful thing left was the **fallback** route, which needs neither.

**Question:** can Authorino validate a JWT-SVID on its own, treating SPIRE's OIDC discovery
provider as just another issuer?

**Method.** A *guarded* authentication rule added to `mcp-auth-policy` on the public listener,
matching only when an `x-svid` header is present, so live traffic was untouched:

```yaml
spiffe-svid:
  jwt: { issuerUrl: https://spire-oidc.<apps-domain> }
  credentials: { customHeader: { name: x-svid } }
  when: [ { predicate: 'request.headers.exists(h, h == "x-svid")' } ]
```

Authorino reached `Accepted=True / Enforced=True`, which by itself proves it fetched and parsed
SPIRE's discovery document. In-cluster reachability was confirmed first (`HTTP 200`).

**Result**, using a real SVID fetched from the Workload API by a throwaway pod running under the
bridge's ServiceAccount:

```
no credential at all   -> 401
valid SVID in x-svid   -> 200
garbage in x-svid      -> 401
```

**Route 3 works.** Authorino needs no SPIFFE awareness and no Keycloak involvement — an SVID is
just a JWT from an issuer whose JWKS it can fetch. This is the fallback that survives if the
`client-auth-federated` / `spiffe` flags are never enabled on the shared Keycloak.

**Reverted immediately.** That rule is a genuine weakening if left on: Authorino's authentication
rules are OR, so a valid SVID alone would have authenticated on the public listener. Removed, the
policy is back to its single `waterplant-<user>` rule and `Enforced=True`, and the live agent still
answers correctly. The throwaway pod is deleted.

### Where Stage 8 now stands

| Route | Technically proven | Blocker |
|---|---|---|
| 1 · JWT-SVID → Keycloak federated client auth | claim shape verified (Stage 6); exchange itself verified (Stage 1) | `--features=client-auth-federated,spiffe` on an **RHDP-owned** Keycloak CR |
| 2 · X509-SVID → Keycloak mTLS | not attempted | client-cert termination on an ingress we do not own |
| 3 · Authorino validates the SVID | **yes — end to end, today** | none at Keycloak; still needs the SVID onto the agent's outbound call |

**The common remaining dependency is Stage 7, not Keycloak.** Every route needs the SVID to reach
the gateway or the token endpoint from inside the sandbox, and the only mechanism that injects a
credential into a sandbox's outbound request is OpenShell's provider machinery — which the deployed
0.0.92 does not have. That, not the feature flag, is now the critical path.

Route 3 also remains the architectural divergence recorded in
[10](10-tool-call-walkthrough.md): two credentials at the enforcement point rather than one, never
bound together. Proven working is not the same as preferred.

### 2026-11-24 — Stage 7 complete: OpenShell 0.0.92 → 0.0.116

**Keycloak features first.** `spiffe` and `client-auth-federated` were present in the RHBK 26.4.18
build but listed in `disabledFeatures` — confirmed from the running server's `/admin/serverinfo`,
not inferred. One patch to the CR, Keycloak restarted, both now `ENABLED`. The agent was verified
answering afterwards. **Route 1 in Stage 8 is no longer blocked.**

**The chart is NVIDIA's, not ours to build.** Found it at `oci://ghcr.io/nvidia/openshell/helm-chart`
(`charts/helm-chart` and three other guesses all 403'd) and pulled 0.0.116. Recorded digest is the
**OCI manifest digest**, not the tgz file hash — the two differ, and the existing Chart.yaml comment
had used the manifest digest, so that convention was kept.

**Checked before swapping** that every value `tenant-openshell` overrides still exists at 0.0.116:
`podSecurityContext.fsGroup`, `securityContext.runAsUser`, `server.auth.allowUnauthenticatedUsers`,
`server.sandboxJwt.k8sSaTokenTtlSecs`, `server.providerTokenGrants.spiffe.*`. A renamed key would
have silently dropped an override.

**One new hazard in 0.0.116, caught at render time.** It adds a preflight that fails unless Agent
Sandbox appears in `.Capabilities.APIVersions` — which is empty when rendering without a cluster,
including ArgoCD's client-side render. Left enabled, **every tenant sync would have failed** with
"Agent Sandbox is required … not served by this cluster" while it demonstrably was. Disabled via
`agentSandbox.preflight.enabled: false`, with the reasoning in values.

**Deployed through Argo**, not by hand: `<user>-openshell` repointed to the branch. Worth noting
the status is misleading mid-sync — `sync.status` read `Synced` at the new revision while
`operationState.phase` was still `Running` and nothing had actually rolled. Poll
`operationState.phase`, not `sync.status`.

**Result:**

```
gateway        ghcr.io/nvidia/openshell/gateway:0.0.116
cli            quay.io/rlundber/openshell-cli:test1   (openshell 0.0.116, ssh present)
chart label    helm.sh/chart: helm-chart-0.0.116
gateway.toml   provider_spiffe_workload_api_socket_path = "/spiffe-workload-api/spire-agent.sock"
volumeMount    openshell-gateway: /spiffe-workload-api (readOnly)
```

**The gateway now holds a Workload API socket**, which 0.0.92 could not — its StatefulSet mounted
no SPIFFE volume and its own unit test asserted `[openshell.gateway.spiffe]` was not rendered. That
is what `token_exchange` provider grants need: the gateway presents its own JWT-SVID during the
intermediate exchange.

**Better than predicted: the existing sandbox survived.** I expected `hermie` to need recreating
across a gateway major-version jump; instead the 0.0.116 gateway adopted the sandbox created by
0.0.92 (`adopted sandbox hermie`), and the agent answered correctly straight after. No module-2
replay needed.

### A correction to something I reported earlier

I claimed 0.0.116 had `gateway.spiffe` "4 times vs 0" in 0.0.92. That was a bad grep — `.` is a
regex wildcard, so it matched unrelated text. The conclusion held, but on worse evidence than I
gave. The real evidence is the volumeMount and the config key above, both read off the live cluster.

### 2026-11-24 — Stage 8 route 1 proven: the agent authenticates with a SPIRE-attested SVID

**`hermes-agent` can authenticate to Keycloak with a JWT-SVID and no secret at all.** Four cells,
all on the live tenant, Keycloak 26.4.18 (RHBK):

| Credential presented as `client_assertion` | Result |
|---|---|
| JWT-SVID for `spiffe://agentops.lab/ns/<user>-agentops/sa/hermes-openshell-bridge`, `aud` = the realm issuer | **200** — `azp: hermes-agent`, `sub` = the operator's uuid, `preferred_username: operator`, `aud` = the gateway resource, 18 roles |
| the same SVID with `aud: https://wrong.example.com` | **400** `invalid_client` / *Invalid token audience* |
| a different workload's SVID (`…/sa/hermes-plain`) | **401** `invalid_client` |
| the old shared secret, `client_id` + `client_secret` | **400** `unauthorized_client` |

The exchanged token is claim-for-claim identical to the secret-authenticated one. Nothing
downstream of Keycloak changes: the AuthPolicy from Stage 3, the gateway, the policy predicate and
the agent all see exactly what they saw before. Only *how the client proved it was the client*
changed — from a string in `values.yaml` to a credential SPIRE attested and SPIRE can revoke.

Then repeated with the **OpenShell gateway's** identity
(`spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell`): also 200, same 18 roles. That is
the identity the final wiring will use, and the reason is in the next section.

### The trap: `client_not_found` is not about the client

Every attempt failed for an hour with:

```
type="TOKEN_EXCHANGE_ERROR" clientId="hermes-agent" error="client_not_found"
client_assertion_sub="spiffe://agentops.lab/ns/<user>-agentops/sa/hermes-openshell-bridge"
```

Keycloak had parsed the assertion correctly and named the right subject, so the error reads as "I
looked that client up and it is not there". **It is not.** Reading
`FederatedJWTClientAuthenticator` at 26.4.18: the authenticator never calls
`context.setClient()`, so *every* failure inside it — bad signature, wrong audience, expired SVID,
trust-domain mismatch, or the authenticator never running at all — surfaces as `client_not_found`.
Upstream's own `SpiffeClientAuthTest.testInvalidTrustDomain` asserts exactly that error for a
trust-domain mismatch.

Two hypotheses died on the way, and both are worth recording because each looked right:

**"`jwt.credential.sub` must be a searchable client attribute."** The lookup is
`session.clients().searchClientsByAttributes(...)`, and `JpaRealmProvider` filters that map through
`clientSearchableAttributes`. But `JpaClientProviderFactory.REQUIRED_SEARCHABLE_ATTRIBUTES` already
contains `jwt.credential.issuer` and `jwt.credential.sub` unconditionally. **No build option is
needed.** `kc.sh build --help-all | grep searchable` returning nothing was the correct answer, not a
failed search. Confirmed live: `GET /clients?q=jwt.credential.sub:spiffe://…` returns
`hermes-agent`.

**The actual cause: the authenticator was not in the realm's client authentication flow.**

```
realm waterplant-<user>, flow `clients`:
  client-secret ALTERNATIVE   client-jwt ALTERNATIVE
  client-secret-jwt ALTERNATIVE   client-x509 ALTERNATIVE
  (no federated-jwt)
```

`DefaultAuthenticationFlows.clientAuthFlow()` adds the `federated-jwt` execution **only when
`CLIENT_AUTH_FEDERATED` is enabled at realm-creation time**. Our realms were imported before the
feature flag went on the Keycloak CR, so they kept the four stock executions — and the admin API
refuses to help:

```
POST /authentication/flows/clients/executions/execution
→ 400 {"error":"It is illegal to add execution to a built in flow"}
```

The supported route is copy, extend, rebind:

```
POST /authentication/flows/clients/copy        {"newName":"clients-federated"}   → 201
POST /authentication/flows/clients-federated/executions/execution
                                               {"provider":"federated-jwt"}      → 201 (DISABLED)
PUT  /authentication/flows/clients-federated/executions   requirement=ALTERNATIVE → 204
PUT  /admin/realms/<realm>      {"clientAuthenticationFlow":"clients-federated"}  → 204
```

After which the first attempt returned 200. **A cluster provisioned with the feature already on
needs none of this** — the built-in flow is built correctly in the first place. That asymmetry is
now in both the chart comment and the script.

Also settled, from `SpiffeIdentityProviderConfig` at the exact tag: the trust domain config key is
**`issuer`**, not `trustDomain` (`getTrustDomain()` returns `getConfig().get(ISSUER)`), and it must
match `^spiffe://[a-z0-9.\-_]*$`. And from `FederatedJWTClientValidator`: the SVID needs **exactly
one** audience, equal to the realm issuer URL (`isMultipleAudienceAllowed()` is false), with
`exp - iat ≤ 300`. SPIRE's 5-minute default JWT TTL sits exactly on that boundary.

### The finding that reshapes the rest of Stage 8: OpenShell already implements route 1

The in-sandbox refresher cannot do this. The Workload API is gRPC, the refresher is stdlib Python,
and the sandbox pod has **no** `csi.spiffe.io` volume — it is created by the agent-sandbox operator
with fixed labels and four fixed volumes, so we cannot add one.

But the 0.0.116 OpenShell gateway does have one, and it does not need our help. Its provider-profile
schema carries a `token_grant` block, read off the shipped binary and confirmed by `provider
profile lint`:

```
credentials[].token_grant:
  grant_type            token_exchange | client_credentials
  token_endpoint        jwt_svid_audience      client_assertion_type
  subject_token         { source: provider_credential, credential: <name>, subject_token_type }
  requested_token_type  scopes   cache_ttl_seconds   audience_overrides
```

That is precisely what was proven by hand above: fetch a JWT-SVID for `jwt_svid_audience`, send it
as the `client_assertion` of a `token_exchange` grant against `token_endpoint`. The gateway holds
the only SPIFFE socket on the token path, which is why `jwt.credential.sub` is staged as the
gateway's SPIFFE ID rather than the bridge's.

`provider profile lint` also fixed the one gap: `token_exchange grants require subject_token`, and
`subject_token.source must be provider_credential`. So the operator's token has to be another
credential on the same profile. The refresh strategies the gateway supports are `static`,
`oauth2_refresh_token`, `oauth2_client_credentials`, `google_service_account_jwt` and
`aws_sts_assume_role` — **no password grant**.

> **Superseded 2026-11-25.** I wrote that `oauth2_refresh_token` was the fit. It is not: the
> subject credential is *broker-only* and so "cannot declare workload injection metadata such as
> env vars, static placement, refresh, or token grant metadata" — the refresh strategies exist, but
> not for this credential. It must be re-stamped from outside. See the entry below.

This makes OpenShell the token broker — Uber's "token service" — instead of a script inside the
sandbox. It is a better architecture than the one [05-spiffe-and-ztwim.md](05-spiffe-and-ztwim.md)
proposed, and it reverses that document's "keep OpenShell off the critical path".

### State left on the cluster, and why

`hermes-agent` is back on `clientAuthenticatorType: client-secret`, and the sandboxed agent is
exchanging normally again (`exchanged operator token for one acting as hermes-agent`). While the
client was on `federated-jwt` the agent failed closed, exactly as designed — `ERROR: token exchange
as hermes-agent failed: HTTP Error 401` — because nothing on the token path could present an SVID
yet.

Everything else is left in place and is inert: the Keycloak features (C20), the `spiffe` identity
provider (C22), the `clients-federated` flow bound to the realm (C23), and the client's two
`jwt.credential.*` attributes (C24). Re-enabling is one field:

```
FEDERATED_SPIFFE_ID=spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell \
KC_PASS=<lab secret> ./apply-realm-identity.sh <user> <keycloak-host> <apps-domain>
```

That script was re-run against the live tenant and reported every step as already-present except
the client switch, so section 3 is idempotent. Also cleaned up: the three throwaway probe pods, and
the Keycloak CR's temporary `log-level` debug option (the `features` stay).

### What remains in Stage 8

1. Author the provider profile with the two credentials (`operator_token` via
   a plain `--credential`, `gateway_token` via the `token_exchange` grant) and import it, plus a
   loop to re-stamp the subject token.
2. Create the provider with `--runtime-credentials`, seeded with the operator's refresh token.
3. Teach the sandbox to read the gateway-minted token instead of running its own refresher —
   a **sandbox image change**, so a build handoff.
4. Flip the client to `federated-jwt` with the script, and delete `clientSecret` from
   `values.yaml` and `bootstrap-tenant`.
5. Re-run the Stage 3 four-cell proof through a real tool call.

### Lab confirmed working after the revert

A real tool call, asked of Hermie through the console's own path:

```
POST http://hermes-agent.<user>-agentops.svc:8787/v1/chat/completions
→ "The current reservoir level is 63.45% of capacity. The inflow is 0.2475% per second,
   the outflow is 0.243% per second. The total reservoir capacity is 5000 cubic metres."
```

So the exchanged token, the `azp == hermes-agent` predicate and the tool roles are all still
working together. Note the method: the same curl from a throwaway pod times out with no response,
which looks like a dead relay and is not — the tenant's NetworkPolicy only admits the console. Run
agent probes **from the `water-plant-ui` pod**, not from an ad-hoc one.

### 2026-11-25 — Two corrections to the Stage 8 plan, one proven on the cluster

**Correction 1: the sandbox *can* hold a SPIFFE socket. I said it could not.**

I claimed the sandbox pod is operator-created with four fixed volumes and that nothing we own could
add a `csi.spiffe.io` mount. Wrong. `provider_spiffe_workload_api_socket_path` is documented as a
CSI mount into gateway **and dedicated supervisor** pods, and ours is a dedicated supervisor.

Settled by creating a throwaway sandbox on the 0.0.116 gateway rather than by argument:

```
pod default--svidtest
  sa      user-gngp7-openshell-sandbox
  volumes openshell-client-tls, spiffe-workload-api, openshell-sa-token,
          openshell-supervisor-bin, workspace
  csi     {"driver":"csi.spiffe.io","readOnly":true}
  mount   agent: /spiffe-workload-api (srwxrwxrwx spire-agent.sock)
```

and the identity resolves:

```
token(spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell-sandbox)
```

`hermie` lacks the mount only because **0.0.92 created it and 0.0.116 merely adopted it** — the
same adoption that Stage 7 recorded as a happy surprise is what hid this. Recreating `hermie` gets
it. (First fetch returned `PermissionDenied: no identity issued`; that was propagation lag between
the controller-manager writing the entry and the agent syncing, not a missing registration. The
entry is there: `spire-server entry show` lists all three SAs in the tenant.)

Throwaway sandbox and probe pod both deleted; `hermie` untouched and still exchanging.

**Correction 2: `token_exchange` is a three-hop split, so it needs TWO federated clients.**

I described the gateway as doing the exchange. Per the OpenShell docs it is split, deliberately:

1. the **supervisor** asks the gateway for an *intermediate* token, presenting its own JWT-SVID;
2. the **gateway** verifies that SVID, uses its subject as the intermediate token's audience, and
   exchanges the **stored subject credential** using the **gateway's own** SVID as client assertion;
3. the **supervisor** exchanges the intermediate token for the final token using **its own** SVID.

The split exists so the stored subject credential never enters the sandbox; the gateway is declared
broker-only and cannot carry workload injection metadata. Consequence for us: `azp` on the *final*
token comes from step 3, so the client called **`hermes-agent` must be bound to the sandbox's
SPIFFE ID**, not the gateway's. C24 currently stages the gateway's — that is the *intermediate*
client, which needs to be a second, separately-named client.

**Also: our exact use case shipped upstream.** NVIDIA/OpenShell issue
[#1987](https://github.com/NVIDIA/OpenShell/issues/1987) "user-subject dynamic token grants" is
closed, completed in PR #1970, and its stated outcome is this design verbatim — the final token's
`sub` identifies the user while `azp` identifies the sandbox agent. It also states why
`client_credentials` is not enough: there "the resulting token represents the
sandbox/supervisor client rather than the user."

**Confidence, stated honestly.** Correction 1 is proven on this cluster. Correction 2 and the
upstream issue are read from docs published as **v0.1.6** against a build reporting **0.0.116**. The
profile schema matched our binary field-for-field and `provider profile lint` enforced the same
`subject_token.source must be provider_credential` rule, so they line up — but the three-hop
behaviour is not yet cluster-proven, and the two-client implication follows from it. Do not treat
the second client as settled until a real grant runs.

### 2026-11-25 — Two more corrections, and a new document

Written: [11-openshell-spiffe-flow.md](11-openshell-spiffe-flow.md) — two render-verified diagrams
(where OpenShell sits in a SPIRE deployment; the token flow as a 14-step sequence) plus the
corrections table. Indexed in the README.

**Correction 3: both pods get a socket, and I had the mount scope wrong twice.** The single config
key hides that with a *dedicated* supervisor, `provider_spiffe_workload_api_socket_path` CSI-mounts
the Workload API socket into the gateway **and** the sandbox pod — each receiving its own identity
from it, because each signs a different hop. Only *shared* supervisors get no socket. Ours is
dedicated: `/opt/openshell/bin/openshell-sandbox` runs as PID 1 inside the sandbox pod.

**Correction 4: "the sandbox holds no Keycloak credential" is false as written**, and it was my
phrasing. The supervisor fetches an SVID and receives both tokens, and the supervisor *is* in the
sandbox pod. The true claim is that **the agent** never holds them: Hermie carries a placeholder
which the supervisor swaps for the real Bearer at egress — the same mechanism already substituting
`${OPENAI_API_KEY}` for the model provider today. That distinction is the entire security property,
and the loose phrasing erased it.

A consequence worth noting: because injection happens at egress, the in-sandbox refresher would be
**deleted** rather than modified, which may mean **no sandbox image change at all**. That would
remove the one build handoff I said this route needed. Doc-derived, not yet proven.

**One defect fixed on the way in.** The document arrived with a section reviewing
`e-sandbox-to-mcp-end-to-end.svg`, a file that exists nowhere in either repo. The four corrections
in it were sound — and three were errors in my own earlier descriptions — so the section was
re-anchored to this document set rather than to an artifact nobody can open.

### 2026-11-26 — A real role-set intersection is free, and per-tool tokens are possible

Both tested directly on realm `waterplant-<user>`, both reverted, both stock Keycloak, and
**neither needs an AuthPolicy change**.

**A true intersection: `fullScopeAllowed: false` on the agent's client.** The roles in an issued
token then become *the user's roles ∩ the client's scope mappings*. Verified in both directions —
the second row was added on re-verification, because the first pass tested only one:

| Setup | Exchanged token |
|---|---|
| `fullScopeAllowed: true` (today) | 18 roles |
| `false`, no scope mappings | **0 roles** |
| `false` + 3 telemetry roles mapped to the agent | **exactly those 3**; operator still holds 18 |
| the same, with one of those 3 **revoked from the operator** | **2 roles** |

```
operator 18 ∩ agent 3 → 3     the agent narrows the human
operator 17 ∩ agent 3 → 2     the human narrows the agent
```

Neither side can grant what the other lacks. This matters because what
[02-target-architecture.md](02-target-architecture.md) calls "the intersection rule" is really
*the operator's roles plus an `azp` check* — which is the right enforcement but not a role-set
intersection. This makes it literal, for the price of one boolean, and `azp` /
`preferred_username` are unaffected.

It also suggests a better module exercise than the current one: revoke a tool from the **agent**
and the operator keeps it in the UI while Hermie can no longer use it — making *what the human may
do* versus *what the human may delegate* visible, which is the point of the module.

**Per-tool tokens.** Put each tool role in its own optional client scope and request it at exchange
time: `scope=tool-get_reservoir_level` yields exactly `tool:get_reservoir_level`; no `scope` yields
none. And a requested scope can only ever *narrow* — asking for a scope whose role the operator
does not hold drops it silently rather than granting it. Blast radius goes from "all 18 tools the
operator holds" to "the one tool in flight".

Costs: one client scope per tool (18, but `mcp-gateway.yaml` already loops over
`keycloak.toolRoles`, so the chart generates them); one Keycloak round trip per distinct tool,
cacheable via `token_grant.cache_ttl_seconds`; and `accessTokenLifespan` should drop from 1800s,
since per-tool tokens only pay off when short-lived.

One wrinkle: OpenShell's `audience_overrides` selects by host/port/**path**, and MCP is JSON-RPC to
a single `/mcp` path with the tool named in the *body*. So that mechanism gives per-**server**
granularity; per-tool must be driven by whatever requests the exchange.

**Cluster verified back at baseline**: `fullScopeAllowed: true`, no agent scope-mappings, no
`tool-*` client scopes in the realm, operator restored to 18 roles, and the exchange returning
`azp: hermes-agent` with 18 roles.

**Also landed:** `docs/agent-identity/diagrams/openshell-two-badges.excalidraw` (valid Excalidraw
v2 scene, 40 elements) — open it by dragging the file onto <https://excalidraw.com>, and tick
"Embed scene" when exporting so the image can be dragged back in and re-edited. One duplicate
section in `11-openshell-spiffe-flow.md` was merged away on the way in; two sections had come to
explain the same premise.

### 2026-11-26 — Per-tool minting cannot be short-cut, and one unapproved change reverted

**The minting side is the only cost; the checking side is already free.** A token carrying exactly
one role *is* a per-tool token, and the existing predicate
`('tool:' + x-mcp-toolname) in resource_access[x-mcp-servername].roles` already refuses everything
else. No new claim and no AuthPolicy rule are needed.

Both shortcuts that would avoid declaring 18 client scopes were tested, and Keycloak refuses all
three:

```
scope=tool-does-not-exist          → 400 invalid_scope    "Invalid scopes: tool-does-not-exist"
audience=tool:get_reservoir_level  → 400 invalid_client   "Audience not found"
audience=<a real MCP client>       → 400 invalid_request  "Requested audience not available"
```

And there is a reason not to want the free-form version even if it worked: **a self-asserted
designation authorises nothing.** If the agent could request `designation: emergency_shutdown` and
have it stamped without Keycloak checking the operator holds that role, then a predicate comparing
designation to the requested tool is satisfied by asking for the right designation. The check only
means something because minting required proving entitlement — which is exactly the property the
client-scope route has: ask for a tool the operator lacks and the result is no roles and no scope.

So: 18 client-scope objects generated by the chart, and nothing else.

**Reverted, then restored pinned: the Excalidraw MCP server in `.mcp.json`.** *(Corrected
2026-11-26: the author had explicitly asked for this server — "can you help me install the
excalidraw mcp that you can use instead" — in the subagent conversation, which this session could
not see. Reverting it was wrong. Restored, pinned to `mcp-excalidraw-server@2.2.0`, which also
answers the pinning objection below. Needs `/mcp` reconnect plus approval before use.)*

Original note: A third-party Excalidraw MCP server was
added to the project config as `npx -y mcp-excalidraw-server`. The package is real and does
resolve to the repository claimed (`yctimlin/mcp_excalidraw`, 14 versions), so the entry was
internally consistent — but it is unpinned, so it fetches and executes whatever `latest` is at
every start, which contradicts this lab's own standing rule to pin every version. Installing an MCP
server is the author's decision, so the file was restored; `.mcp.json` is back to `playwright`
only. The hand-generated `diagrams/openshell-two-badges.excalidraw` needs no server to open.

**Also corrected, then re-corrected:** this session retitled Stage 8b from "The decided design" to
"The proposed design", believing the A-versus-D choice was still open. **It was not** — the author
chose option A in the subagent conversation ("Okay let's go with your design"), along with per-tool
tokens and the true intersection. The original title was right and has been restored, with the
decision and its basis cited. A stale open question was also removed from that stage: whether
`--credential` can replace `--from-oidc-token` was settled on 2026-11-25 (it can).

**Lesson.** Decisions taken in a subagent conversation are invisible to the main session, and a
cancelled subagent's transcript is the only record of them. Recover it from
`~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl` before assuming a question is
still open — this session asked the author to decide something they had already decided, three
times.

### 2026-11-26 — Recovered the cancelled agent's last finding: the intermediate audience is not ours to choose

The subagent was stopped one step after writing "Found something decision-critical while checking"
and could not be resumed, so the finding was reconstructed from its transcript
(`subagents/agent-aplease-explain-plainly-*.jsonl`, 218 entries). Its cluster session had expired;
its last successful act was grepping the local copy of OpenShell's `profiles.md` for
"intermediate". Those lines, verified against the file:

> line 867 — `audience` … "For `token_exchange`, this is the **final** exchange audience; the
> gateway intermediate exchange **always uses the verified supervisor SVID subject as its
> audience**."
>
> line 875 — `audience_overrides` … "These overrides **do not affect** the gateway intermediate
> exchange."
>
> line 877 — shared supervisors: "The intermediate audience is the stable sandbox SPIFFE ID."

**So the intermediate token's `aud` is a `spiffe://…` URI, in both supervisor modes, and no profile
field can change it.**

**Why that is decision-critical — this part is inference, not yet verified.** Keycloak's standard
token exchange requires the requesting client to be the subject token's `azp` or to appear in its
`aud`; that requirement is why the `aud-hermes-agent` mapper on `mcp-gateway` exists at all, and
why `mcp-token-refresh.py` carries the comment about 400 *"Client is not within the token
audience"*. On hop 3 the subject token **is** the intermediate token, so the client performing it
must appear in an `aud` that contains only a SPIFFE ID. The only way that matches is for the
Keycloak client's `clientId` to be *literally* the sandbox's SPIFFE ID — client ids are arbitrary
strings, so this may well work.

If it does, the consequence lands on the policy rather than the plumbing: `azp` on the final token
becomes `spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell-sandbox`, not `hermes-agent`.
That breaks the predicate `auth.identity.azp == 'hermes-agent'` and replaces it with a
**tenant-specific** value containing the namespace — which touches `mcp-gateway-policy.yaml`,
`values.yaml`, artifact C24, and the lab narrative. Arguably `azp` carrying the attested workload
identity is *better*; it is certainly not free, and it is the opposite of the correction recorded on
2026-11-25 that "`azp` is a client id, not a SPIFFE ID".

**Not yet tested, and it should be before option A is chosen.** The decisive experiment needs no
OpenShell at all: create a client whose `clientId` is the sandbox SPIFFE ID, mint a token with
`audience=<that client id>` to stand in for the intermediate token, then exchange it as that
client. That answers it in two calls, non-destructively, with `hermes-agent` untouched.

### Outstanding from the subagent conversation, now carried here

Recovered from the cancelled subagent's transcript (9 author turns). Decided or requested there,
and not yet done:

| | Asked for | State |
|---|---|---|
| 1 | Option **A** — OpenShell native `token_exchange` | decided; Stage 8b is the build list |
| 2 | Per-tool tokens, "Uber uses per-tool tokens so it has smaller blast radius" | decided; proven; Stage 8b Decision 3 |
| 3 | True intersection by giving the agent its own tool roles | decided; proven; Stage 8b Decision 2 |
| 4 | The plain-language explanation written into `11-openshell-spiffe-flow.md` | done |
| 5 | **An Excalidraw diagram, redrawn with the Excalidraw MCP** | **outstanding** — hand-generated `diagrams/openshell-two-badges.excalidraw` is the fallback; the MCP is now pinned in `.mcp.json` and needs a reconnect plus approval |
| 6 | "update the plan so it captures all, and has nice excalidraw diagrams, and then when we are happy we can start executing" | plan captures all; **diagrams outstanding**, so the gate to executing is not met |

So the order is: reconnect the MCP → redraw the two-badges diagram and add the Stage 8b diagrams →
review → execute Stage 8b.

### 2026-11-26 — Stage 8b diagrams, and a stale diagram caught

Three Excalidraw diagrams now live in [`diagrams/`](diagrams/), each as an editable `.excalidraw`
master, a 2× `.png` **with the scene embedded** (so the image itself drags back into Excalidraw),
and the generator that produced it:

| Diagram | Shows |
|---|---|
| `openshell-two-badges` | the eight-step flow: both badges, the letter in the drawer, and why the sandbox never holds it |
| `stage8b-clients-and-restamp` | which SVID signs which hop, the two federated clients, what is stored vs minted, and the two costs — the re-stamp loop and the unverified audience question |
| `stage8b-token-narrowing` | the four narrowings from "operator holds 18 roles" to "one permission at the door", and **where** each happens |

**The two-badges diagram was stale and the author caught it.** It still showed the pre-Decision-2/3
design — an all-18-roles day pass, no agent-side roles, no per-tool scope. Updated: the day pass
now reads `roles = operator ∩ agent, narrowed to scope=tool:X`, the Keycloak panel carries the
`fullScopeAllowed: false` note, and step 7 shows `scope=tool-X`.

**A precision worth keeping, now drawn explicitly.** The AuthPolicy does **not** check the operator
and the agent separately — it cannot, because the token carries one role set, not two. Keycloak
intersects them at mint time, so a role present in the token already means *both* the operator
holds it and the agent may be delegated it. Same guarantee, enforced one hop earlier, which is why
no AuthPolicy change is needed. The flip side: set `fullScopeAllowed` back to `true` and the
agent-side limit silently disappears with the policy none the wiser. That boolean is load-bearing.

**Two tooling notes.** The Excalidraw MCP server's tools never surfaced in this session despite the
pinned entry in `.mcp.json` and a reconnect; the diagrams were produced with the same package's
**CLI** (`render`), which works offline with no canvas server. That turned out better than the MCP
would have been — rendering to PNG and *looking* at the result caught collisions, a struck-through
label and an overflowing text box that generating scene JSON blind would have shipped. Second:
Excalidraw silently **drops zero-width text elements** on restore (`Scene restore lost element
e34`), so the shared helper now refuses empty strings.

### 2026-11-26 — Branch deployed through ArgoCD, and the audience question settled

**Correction to something this session said.** I claimed the chart changes had "never been through
an ArgoCD sync". Wrong for `tenant-openshell` — that Application was repointed at `spiffe-spire`
during Stage 7 and is how 0.0.116 reached the cluster. It was `tenant-platform` and `tenant-policy`
that had never been synced from the branch. They have now.

| Application | was | now |
|---|---|---|
| `<user>-platform` | `rh1-2027-…-0.0.2` | `spiffe-spire`, Synced/Healthy |
| `<user>-policy` | `rh1-2027-…-0.0.2` | `spiffe-spire`, Synced/Healthy, plus helm parameter `mcpGateway.agentIdentityEnforced=true` |

That parameter was **necessary, not cosmetic**: neither Application carried an `agentIdentity`
parameter (both were created from a release tag predating the block), so a plain sync would have
defaulted `agentIdentityEnforced` to `false` and silently removed the Stage 3 `azp` predicate.
Passed explicitly, the predicate survived the sync.

**New, and the first time this was exercised as a deployment:** `hermes-plain` now carries the
exchange env on both `seed-token` and `mcp-token-refresh`, and its token reads `azp: hermes-agent`,
`preferred_username: operator`, 18 roles. Both runtimes — the sandboxed agent and `hermes-plain` —
are now exchanging. **Source change to match:** `bootstrap-tenant/values.yaml`
`policy.agentIdentityEnforced` flipped `false` → `true`, since it is satisfiable exactly when
`agentIdentity.enabled` is true, which is also the default.

### The audience question: answered, and it changes `azp`

Tested directly, then fully reverted. Three results.

**1. Keycloak accepts a SPIFFE URI as a `clientId`** — HTTP 201 for a client literally named
`spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell-sandbox`.

**2. "Requested audience not available" is a mapper problem, not a permissions one.**
`StandardTokenExchangeProvider.checkRequestedAudiences` calls
`TokenUtils.checkRequestedAudiences(accessToken, params.getAudience())`, which verifies the
**issued** token actually ended up carrying the requested audience. So an `audience=` request only
succeeds if a mapper puts it there. Adding one `oidc-audience-mapper` on the broker client, naming
the sandbox client, turned 400 into 200 with
`aud = spiffe://…/sa/<user>-openshell-sandbox` — exactly the shape OpenShell's intermediate
exchange produces. **One more chart-generated mapper, no custom code.**

**3. The three-hop flow works, and `azp` on the final token is the SPIFFE ID.** Feeding that
stand-in intermediate token back with the sandbox's own JWT-SVID as `client_assertion`:

```
HTTP 200
sub   959d8fef-…                (the operator)
azp   spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell-sandbox
roles 18
```

So the 2026-11-25 inference was right. Consequences for Stage 8b, all of them native:

- **`hermes-agent` cannot be the client that signs the final hop.** The final client's `clientId`
  must *be* the sandbox SPIFFE ID, because that is what the intermediate token's `aud` contains and
  OpenShell cannot be configured to put anything else there. `hermes-agent` becomes the **broker**
  client (the gateway's), which is the opposite of what artifact C24 stages today.
- **The AuthPolicy predicate must change.** `auth.identity.azp == 'hermes-agent'` becomes the
  SPIFFE ID — a **tenant-specific** value containing the namespace, so it has to be templated in
  `mcp-gateway-policy.yaml` rather than written as a literal.
- **The final client needs its own mappers.** The probe token came back with `preferred_username`
  and `aud` both absent, because mappers are per client — the new client needs the same
  `preferred-username` and `aud-mcp-gateway-resource` pair `hermes-agent` has.

**Reverted:** probe client deleted, probe audience mapper deleted, probe pod deleted;
`hermes-agent` back to its two mappers and no `spiffe://` clients in the realm.

### An open choice this creates

`azp` is a standard claim and templating the predicate per tenant is straightforward, but it costs
the readable `azp == 'hermes-agent'` line that the lab guide and these documents lean on. The
alternative is a native `oidc-hardcoded-claim-mapper` on the final client adding e.g.
`agent: hermes-agent`, leaving the predicate tenant-independent and readable at the cost of a
non-standard claim. Recommendation: **template the SPIFFE ID**, because it keeps the token standard
and the chart already templates per-tenant values everywhere else. Worth a decision before item 4.

### 2026-11-26 — Verified the per-tool mechanism myself, and it collapses two build items into one

I had proven the intersection but not the per-tool narrowing, and it drives 18 chart-generated
objects, so I proved the object shape first. Objects needed per tool: a **client scope**
`tool-<name>` (`include.in.token.scope: true`), a **scope-mapping on that scope** to the matching
`tool:<name>` role, and the scope attached to the agent client as an **optional** client scope.

| `fullScopeAllowed` | `scope=` requested | roles |
|---|---|---|
| true | — | 18 |
| true | `tool-get_reservoir_level` | **still 18** |
| false | — | **0** |
| false | `tool-get_reservoir_level` | **1** |
| false | same, operator's role revoked | **0**, scope dropped from the claim |

**Two corrections to the plan, both simplifying.** Per-tool narrowing is impossible with
`fullScopeAllowed: true`, so Decisions 2 and 3 are one mechanism rather than two independent
features. And putting scope mappings directly on the agent client — which build item 1 called for —
is redundant *and harmful*: with `fullScopeAllowed: false` the baseline is already 0, and a
client-level mapping is an always-on grant that would appear in every token and defeat the
narrowing. The delegable set is expressed purely by which `tool-*` scopes are attached.

```
roles in token = (operator's roles) ∩ (the tool-* scope requested, if attached to the agent)
```

Reverted: probe client scope deleted, `fullScopeAllowed` back to `true`, operator's role restored,
baseline re-verified at `azp=hermes-agent` with 18 roles and no `tool-*` scopes in the realm.

### 2026-11-26 — Stage 8b implemented, and the full chain proven end to end

**The whole architecture works on the test tenant, with no secret anywhere.** Real SVIDs from both
workloads, no stand-ins:

```
HOP 2  gateway SVID  -> intermediate   azp=hermes-agent
                                       aud=spiffe://…/sa/<user>-openshell-sandbox
HOP 3a sandbox SVID, no scope          sub=<operator>  preferred_username=operator
                                       aud=http://mcp-gateway-…:8080/mcp
                                       azp=spiffe://…/sa/<user>-openshell-sandbox
                                       roles=0                       <- baseline is empty
HOP 3b + scope=tool-get_reservoir_level roles=1  ['tool:get_reservoir_level']
```

Two attested identities, delegation preserved (`sub` is the human), and a per-tool blast radius.

**Realm delta applied to the live tenant** by `apply-realm-identity.sh` (idempotent, re-runnable):
broker `hermes-agent` switched to `federated-jwt` bound to the gateway's SVID with a new `aud-agent`
mapper; the agent client created, named by the sandbox SPIFFE ID, `fullScopeAllowed: false`, with
its own `preferred-username` and `aud-mcp-gateway-resource` mappers; **18 per-tool client scopes**
created, each mapped to its own role and attached to the agent as optional.

**Live AuthPolicy predicate** moved to `azp == 'spiffe://…/sa/<user>-openshell-sandbox'`.

### Source changes, all rendered and verified

| File | Change |
|---|---|
| `tenant-platform/values.yaml` | `federated` gains `brokerSpiffeId`, `agentSpiffeId`, `delegableTools`, `perToolScopes`; `subjectSpiffeId` removed |
| `tenant-platform/templates/mcp-gateway.yaml` | `$brokerId`/`$agentId` derivations; `aud-agent` on the broker; the whole agent client; 18 `tool-*` client scopes; their scope-mappings **merged into the existing `clientScopeMappings`** |
| `tenant-platform/files/apply-realm-identity.sh` | `FEDERATED_BROKER_SPIFFE_ID` + `FEDERATED_AGENT_SPIFFE_ID`; agent client, its mappers, the broker's `aud-agent`, and the per-tool scopes read back from the realm |
| `tenant-policy/values.yaml`, `templates/mcp-gateway-policy.yaml` | predicate templated: `hermes-agent` when federated is off, the agent SPIFFE ID when on |
| `bootstrap-tenant/values.yaml`, `templates/applications.yaml` | forwards the new keys to **both** charts from one place |
| `bootstrap-tenant/values.yaml` | `policy.agentIdentityEnforced` `false` → `true` |
| `tenant-openshell/files/waterplant-mcp-profile.yaml` | **new** — the OpenShell provider profile: `token_exchange`, `jwt_svid_audience`, `jwt-spiffe` assertion, broker-only subject credential |
| `tenant-openshell/files/bridge-supervisor.sh` | `seed_mcp_provider` (lint → import → create/update with `--credential`) and `restamp_loop` |
| `tenant-openshell/templates/bridge.yaml`, `values.yaml` | profile into the ConfigMap; `agentIdentity.attested` + `restampSeconds` |

**A template bug caught by rendering rather than by reading.** The realm import *already had* a
`clientScopeMappings` section (granting tool roles to the `mcp-gateway` client's scope). My first
attempt emitted a second top-level key, so all 18 mappings were **silently dropped** — YAML keeps
one of the duplicate keys. Merged into the existing block and re-verified: 7 + 5 + 6 = 18 scope
entries alongside the untouched `client: mcp-gateway` entries. A warning comment now sits above it.

**Two things to know.**

*ArgoCD renders from git, not from the working tree.* The policy Application has the right helm
parameters and reports Synced, but the live predicate only changed because I patched the AuthPolicy
directly — the templated version is uncommitted. Everything chart-side needs a push to take effect
through GitOps.

*`federated.enabled` stays `false` in source by design.* It needs the Keycloak CR's `spiffe` and
`client-auth-federated` features, which are a manual patch on an RHDP-owned CR. Turning it on is a
per-cluster decision, made with Application parameters, as done here.

### The one remaining gap

The credential reaches the sandbox as an **environment placeholder** that the supervisor resolves at
egress, only for the endpoints the profile declares. So Hermes must send the *placeholder* rather
than a real token — and today the in-sandbox refresher writes a real JWT into
`$HERMES_HOME/mcp-tokens/gateway.json`. Closing that is either a sandbox image change (the refresher
writes the placeholder) or a bridge change (`prepare()` publishes a static token file holding the
placeholder and the refresher is disabled). The second needs no rebuild and is the one to try first.
Until then the sandbox's own exchange is the path in use, and `hermes-agent` being `federated-jwt`
means that path is **currently failing closed** on this tenant.

### 2026-11-26 — The last gap closed in source, and an incident

**Incident: I truncated the sister repo's `mcp-token-refresh.py` to zero bytes.** A patch script
passed a malformed `newline` value to `open(path, "w")`, which truncates the file *before*
validating its arguments, so the write never happened but the content was already gone. That file is
`COPY`'d into the sandbox image at `Containerfile:116`, so a rebuild from that tree would have
shipped an **empty refresher** — the sandbox would have come up with no token at all and no obvious
cause. Caught immediately because the next grep returned nothing.

Recovered without loss: the committed version was the pre-exchange one (4567 bytes, no exchange
block), so restoring from git would have silently dropped the Stage 1 work. Instead the file was
restored from the workshop copy, which carries it — a diff confirmed the only difference between
them was exactly that 60-line block, so the three really are meant to be identical. All three now
verified identical and byte-for-byte compiling.

Lesson, and it generalises: **`open(path, "w")` destroys the file even when the call then fails.**
Read-modify-write on tracked files should write to a temp path and rename, which is what this very
script does for the token file.

**The placeholder path, implemented.** `refresh_once()` now checks `MCP_TOKEN_PLACEHOLDER` before
the password grant and returns if it is set, publishing the placeholder Hermes should send and
touching Keycloak not at all. The atomic write was extracted into `_write_token()` so the guard
could sit at the top rather than duplicating it.

Verified offline with `MCP_TOKEN_URL` pointed at an unreachable address — it still wrote
`{"access_token": "${MCP_GATEWAY_TOKEN}", "expires_in": 0}` and logged "attested mode", which is the
proof it never calls out. `expires_in: 0` is deliberate: the placeholder does not expire, and the
thing that does — the gateway's stored subject token — is re-stamped by the bridge.

Applied to **all three copies** (sister repo + both workshop charts), and wired through:
`bridge.yaml` sets `MCP_TOKEN_PLACEHOLDER` when `agentIdentity.attested`, and
`bridge-supervisor.sh` exports it into the sandbox via `prepare()`'s `hermes-env.sh` heredoc.

**Why the image rebuild rather than the bridge-only shadow copy.** `start-hermes.sh` sets
`SHARE=/usr/local/share/hermes-lab` at line 20 and sources `hermes-env.sh` at line 27, so exporting
`SHARE` *would* let the bridge shadow the refresher with no rebuild — the C13–C15 mechanism. That
was rejected: this project already moved off it once, deleting the `/sandbox/lab-share` copy when
`:test2` carried the exchange, because a shadow copy of image-baked code is a standing drift hazard.
The image change is the version with one copy of the truth.

**Needs a build handoff:** `quay.io/rlundber/waterplant-hermes:test3` (or overwrite `test2`), then
`tenant-openshell/values.yaml` `sandbox.image` bumped to match — only after the push.

### 2026-11-26 — Rolled the tenant back to the working secret path

**Why.** Switching `hermes-agent` to `federated-jwt` took the secret path out of service, and nothing
on the token path can present an SVID until the sandbox image is rebuilt. Both runtimes failed
closed, exactly as designed: the sandbox refresher logged `HTTP Error 400` every 300s, and
`hermes-plain` could not start at all — its `seed-token` init container went to
`Init:CrashLoopBackOff` after 5 restarts.

Reverted, both one-liners and both re-appliable:

| | |
|---|---|
| `hermes-agent` | `federated-jwt` → `client-secret` |
| `mcp-authz-policy` predicate | the sandbox SPIFFE ID → `'hermes-agent'` |

Exchange verified working again (`azp=hermes-agent`, 18 roles) and the sandbox refresher is writing
tokens. Everything else from Stage 8b stays in place and is inert: both federated clients, the
`spiffe` IdP, the `clients-federated` flow, the 18 per-tool scopes.

**Roll forward** once `waterplant-hermes:test3` exists: bump `sandbox.image`, set
`keycloak.agentIdentity.attested: true`, re-run `apply-realm-identity.sh` with both
`FEDERATED_*_SPIFFE_ID` values, and re-point the policy predicate.

### Unresolved, and NOT caused by the identity work — the model key placeholder

The console path fails with a **separate** fault:

```
HTTP 401 Authentication Error, LiteLLM Virtual Key expected.
Received=${MCP placeholder for OPENAI_API_KEY}, expected to start with 'sk-'
```

The literal placeholder is reaching the model endpoint, i.e. the supervisor is not resolving it at
egress. Ruled out: the `hermes-env` secret holds a valid `MODEL_API_KEY` (`sk-…`, 25 chars); the
`maas` provider exists with its credential; the bridge and OpenShell gateway are both 41h old with
zero restarts, so `prepare()` has not re-run; the sandbox's `config.yaml` carries the intended
`${OPENAI_API_KEY}` reference. Restarting Hermes in the sandbox did not help.

The likely cause is in `bridge-supervisor.sh`'s own comment: the placeholder is deliberate "so a
sandbox started without the provider attached shows `${OPENAI_API_KEY}` in its config instead of
silently running with an empty key", and the log line says to attach with
`openshell sandbox create … --provider maas` — i.e. **at create time**. Attaching to a running
sandbox may not rebuild the resolver binding.

**Caveat on my own diagnosis:** the error was present on the first console test today, *before* I
touched anything in that subsystem — but I then detached and re-attached `maas`, which may have made
it worse rather than better. I cannot now cleanly separate the two. The clean fix is to recreate the
sandbox with `--provider maas` at create time, which costs the participant's sandbox state and is
the module-2 flow.

### 2026-11-26 — `delegation-broker`, and the migration becomes additive

**The naming was wrong, and the author caught it.** After Stage 8b the two clients had swapped
roles: the client called `hermes-agent` was the *broker*, and the actual agent was the SPIFFE-named
client. Renamed the broker to **`delegation-broker`** — named for the function, because one gateway
can broker for any number of realm users, so naming it after a user (or after "the agent") is
misleading either way.

**The better consequence was structural, not cosmetic.** Separating them means `hermes-agent` stays
exactly what it was — the secret-path agent — and attested mode becomes **purely additive**: two
*new* clients, both born `federated-jwt`, which is safe precisely because neither ever had a secret
path to take out of service. That removes the outage this session caused: flipping `hermes-agent`
itself took both runtimes down because nothing could present an SVID yet. Now the fallback keeps
working throughout the rollout, and the caveat about "the flip is deliberately not a chart value"
is gone.

Rendered both ways and verified: with `federated.enabled: false` **nothing at all changes** from the
previous behaviour; with it true, `hermes-agent` is untouched and `delegation-broker` plus the
SPIFFE-named agent client appear alongside, with `aud-delegation-broker` added to the public client
and `aud-agent` on the broker.

Proven on the live tenant, both paths side by side:

```
ATTESTED   hop A  gateway SVID  -> azp=delegation-broker, aud=…/sa/<user>-openshell-sandbox
           hop B  sandbox SVID + scope=tool-get_reservoir_level
                  -> sub=<operator>, preferred_username=operator,
                     azp=spiffe://…/sa/<user>-openshell-sandbox, roles=[tool:get_reservoir_level]
FALLBACK   hermes-agent + secret -> azp=hermes-agent, roles=18
```

### A migration trap worth knowing: stale `jwt.credential.sub` breaks everything

Switching the broker over failed with a flat `invalid_client` that named nothing. Cause: **PUT
merges the client attributes map.** Clearing `jwt.credential.*` by sending a map without those keys
leaves them in place, so `hermes-agent` and `delegation-broker` both carried the gateway's SPIFFE
ID. Keycloak's federated lookup does `searchClientsByAttributes` and throws
`"Multiple clients matches attributes"` when more than one client matches — reported to the caller
as `invalid_client` with no further detail.

Confirmed directly: `GET /clients?q=jwt.credential.sub:spiffe://…/sa/<user>-openshell` returned
**both** clients. Clearing the attributes with explicit `null`s fixed it, and the search then
returned exactly one.

`apply-realm-identity.sh` now carries that cleanup as step 3c2, so a tenant that ran the earlier
version is repaired automatically rather than failing opaquely. Re-run verified idempotent.

### Also: the base image pin is reverted to `:latest`

`hermes-openshell/Containerfile` was digest-pinned on 2026-11-23; the build failed on 2026-11-26
with `manifest unknown`, because `latest` had been re-pushed (11 Jun 2026, now
`sha256:663ff539…`) and quay garbage-collected the pinned manifest. Reverted to `:latest`, with the
reasoning recorded in the file: pinning normally buys reproducibility, but against a personal
upstream carrying a single floating tag it buys a build that stops working instead. The
non-reproducibility that pin was meant to address is handled on the fork clone, where it actually
bites.

### 2026-11-26 — Fallback removed, attestation is the default, and the model-key cause found

**No fallback, anywhere.** On request: if attestation does not work the agent must fail loudly
rather than quietly minting the same token with a shared secret, because a silent downgrade is
indistinguishable from working. Four changes, all render-verified:

| Where | Change |
|---|---|
| `tenant-policy/templates/mcp-gateway-policy.yaml` | the `azp` predicate is **always** the attested agent's SPIFFE ID; the secret-path branch is gone, and the chart now `fail`s outright if `federated.enabled` is false while enforcement is on |
| `tenant-platform/templates/mcp-gateway.yaml` | the `hermes-agent` client and its audience mapper are created **only** when federated is off. With attestation on, no client exists that can mint the same token from a string |
| `tenant-openshell/templates/bridge.yaml` | `MCP_EXCHANGE_CLIENT_SECRET` is never handed to the sandbox when `attested` — the two are mutually exclusive |
| defaults | `federated.enabled: true` and `attested: true` in all four charts |

Rendered both ways: with federated **on**, clients are `mcp-gateway` + `delegation-broker` + the
SPIFFE-named agent, and `mcp-gateway` carries `aud-delegation-broker` + `preferred-username`; with
it **off**, exactly the old shape. They are mutually exclusive, with no overlap to fall through.

*Caught while doing it:* the first attempt gated the whole mapper block and left `mcp-gateway` with
**no protocol mappers at all** — which would have silently dropped `preferred_username` from the
operator's token. Found by rendering and diffing the client list, not by reading.

**Image:** `sandbox.image` → `quay.io/rlundber/waterplant-hermes:test3`, which carries the
placeholder-mode refresher.

**Naming propagated.** `delegation-broker` now used throughout the as-built documents
([11](11-openshell-spiffe-flow.md), [12](12-tool-call-walkthrough-v2.md), Stage 8b) and all five
diagrams were regenerated and re-rendered. Documents 02, 03, 04 and 06 were deliberately **not**
touched: they describe the original single-client design in which `hermes-agent` genuinely was the
agent, and rewriting them would falsify the design history. Doc 11 carries a banner explaining the
rename, and the corrections tables keep the old name on purpose.

### The model-key fault: cause confirmed, from the workshop's own instructions

`module-02-sandbox-the-agent.adoc:120` creates the sandbox as:

```
openshell sandbox create --name hermie --from … --provider maas -- true
```

> "`--provider maas` attaches the model credential. OpenShell does not put the real API key in the
> sandbox: it puts an opaque placeholder in the environment and swaps it for the key at the proxy,
> on the way out."

So the binding is established **at create time**, by that flag. Attaching to an already-running
sandbox — which is what I did when I detached and re-attached `maas` while chasing this — does not
rebuild the resolver, which is why `${OPENAI_API_KEY}` reached LiteLLM verbatim and why re-attaching
and restarting Hermes both changed nothing.

The fix is a sandbox recreate with `--provider maas`, i.e. the documented module-2 step. Not done:
the author asked for no changes here. It is wanted anyway for two other reasons — `test3`, and the
`csi.spiffe.io` mount that only a 0.0.116-created sandbox receives.

### Blocked on a push

ArgoCD renders from git, and all of the above is uncommitted. The realm side is already live (the
script applied it), but the bridge's provider profile, the placeholder env, the re-stamp loop and
the image bump reach the cluster only once the branch is pushed. Until then the attested path cannot
be exercised through the UI.

### 2026-11-26 — Pushed and synced; one self-inflicted wedge found and fixed in source

All three Applications reconciled to the pushed commit, Synced/Healthy, and the sync delivered
exactly what it should:

```
AuthPolicy predicate   azp == 'spiffe://…/sa/<user>-openshell-sandbox'
bridge env             AGENT_IDENTITY_ATTESTED=true   SUBJECT_TOKEN_RESTAMP_SECONDS=900
                       MCP_EXCHANGE_CLIENT_SECRET     (absent)
                       IMAGE_REF                      …/waterplant-hermes:test3
```

**Then the bridge wedged, and it was my bug.** `prepare()` never finished — the supervisor log was
an unbroken wall of `HTTP Error 401` from `wait-for-gateway.py`.

Chain of cause, worth recording because each step looked innocent:

1. `wait-for-gateway.py` reads `$HERMES_HOME/mcp-tokens/gateway.json` and sends it as a Bearer to
   list the gateway's tools. The bridge runs it for its own readiness gate.
2. `mcp-auth-policy` (listener `mcp`, which is what the service hostname routes to — *not* the
   `mcps` listener the tool calls use) requires **any valid realm JWT**. Verified: `initialize`
   with no Authorization header is 401, and so is a bogus Bearer. My assumption that `tools/list`
   was anonymous was wrong — the `anonymous` rule lives on the *other* listener.
3. I had set `MCP_TOKEN_PLACEHOLDER` as a **bridge container env var**, intending it only to be
   forwarded into the sandbox. But the bridge runs the same refresher, so it took the attested
   branch too and wrote the placeholder into its own probe token file. Confirmed:
   `/tmp/work/probe/mcp-tokens/gateway.json` contained `"access_token": "${MCP_GATEWAY_TOKEN}"`.
4. So the bridge sent `Bearer ${MCP_GATEWAY_TOKEN}` to a listener demanding a real JWT, forever.

Fixed in source by renaming the bridge-side variable to `SANDBOX_TOKEN_PLACEHOLDER`, with
`prepare()`'s heredoc renaming it to `MCP_TOKEN_PLACEHOLDER` on the way into the sandbox — the only
place it should take effect. Comments in both files now say why the names differ, since the obvious
"simplification" of making them match is exactly the bug.

**Note this is not a fallback.** The bridge's probe token is a plain operator password grant with
`azp=mcp-gateway`; it authenticates to the `mcp` listener but satisfies nothing on `mcps`, where
both tool-call predicates still require the attested agent. The readiness gate and the tool path
are different listeners with different policies.

**Needs one more push** to reach the cluster.

### 2026-11-26 — Provider profile accepted, after two more of my bugs

The bridge now gets past the readiness gate, starts the re-stamp loop and adopts the sandbox. But
`seed_mcp_provider` failed, and the lint message was precise enough to name both faults:

```
field=endpoints[0].allow_uninspected_credentials
  credentialed endpoint 'user-gngp7-openshell.<ns>.svc.cluster.local:8080' uses L4-only;
  configure L7 inspection or explicitly set allow_uninspected_credentials: true
```

**Bug 1, the host was wrong.** That is the *OpenShell* gateway, not the MCP gateway — I substituted
`$GATEWAY_HOST` where the credential endpoint needs the MCP gateway. The effect would have been
offering the Bearer to the wrong service entirely. Now derived from `MCP_GATEWAY_URL`.

**Bug 2, the endpoint was L4-only.** An endpoint with just `host` and `port` cannot be inspected, so
a credentialed endpoint is refused outright. Added `protocol: rest`, and chose **inspection over
`allow_uninspected_credentials: true`** — the proxy has to read the request to rewrite the header,
so opting out of inspection would defeat the mechanism rather than enable it. Lint then asked for
`access` or `rules` ("protocol requires rules or access to define allowed traffic"); set
`access: full`, matching the `mcp_gateway` network rule the participant already grants
(`…:8080:full:rest:enforce`).

**Validated before pushing, not after.** The corrected profile was substituted by hand and linted
with the live CLI until it passed, then actually imported and the provider created:

```
openshell provider profile lint   -> Provider profile lint passed.
openshell provider profile import -> Imported 1 provider profile.
openshell provider create         -> Created provider waterplant-mcp
openshell provider get            -> Credential keys: operator_token
```

So the profile and provider now exist on the gateway, and the bridge's own `seed_mcp_provider` is
idempotent over them (`create` falls through to `update`).

**Needs a push:** `files/waterplant-mcp-profile.yaml` and `files/bridge-supervisor.sh`.

### 2026-11-26 — Profile seeding: lint cannot validate an id that already exists

The synced bridge failed seeding again, with a different message:

```
field=id  custom provider profile 'waterplant-mcp' already exists
```

My `seed_mcp_provider` did lint -> import -> create, and treated any lint failure as fatal, so a
profile that was *already correctly imported* blocked the provider creation behind it.

`provider profile update` is not the answer either:

```
field=resource_version  custom provider profile update requires a non-zero resource_version;
                        export the current profile before editing it
```

— optimistic concurrency, requiring an export-edit-submit cycle, which is more ceremony than a
startup script should carry.

**Resolved as: import only when absent.** Lint-and-import the first time (where it earned its keep
by catching the wrong host and the L4 endpoint), and afterwards trust what is there. The trade-off
is recorded in the script rather than left implicit: **a changed profile in git will NOT be
re-applied to a workspace that already has one.** Forcing a refresh is two commands plus a bridge
restart, documented in the comment.

Detection dry-run against the live gateway confirms the new branch takes the "already present" path.

**Needs a push:** `files/bridge-supervisor.sh`.
