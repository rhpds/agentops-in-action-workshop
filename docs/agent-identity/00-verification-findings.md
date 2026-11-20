# 00 — Phase 0 verification findings

Everything below was read from a live 3-tenant build (`api.ocp.c5qkd.sandbox1942.opentlc.com`,
tenants `user-9c5ls`, `user-qkc86`, `user-xc25n`) on 2026-11-19. Strictly read-only: nothing
was created, patched, or written, including inside pods.

These findings are the evidence base for every other document here. Where a later document
makes a claim about the current system, it should be traceable to a row in this one.

## Results

| # | Question | Result |
|---|---|---|
| 1 | Does the agent's token name a subject? | **No.** See below. |
| 2 | Which client scopes and mappers exist? | Only `offline_access`, `roles`, `groups`. `mcp-gateway` has **no** protocol mappers. |
| 3 | Is RFC 8693 token exchange available? | **Yes**, advertised. Plus `private_key_jwt` *and* `tls_client_auth` client auth. |
| 4 | Does the deployed OpenShell support SPIFFE/token-exchange provider grants? | **No.** Profile schema is static-credential only. |
| 5 | Can the MCP servers see caller identity? | **Yes, natively** — mcp 2.x has a first-class identity surface. |
| 6 | Is `AGENT_API_KEY` empty on the console? | **No — false alarm.** It is set, length 48. |
| 7 | Is FGAP V2 enablable on the realm? | Currently `false`, but the per-realm toggle exists. |

## 1. The agent's token has no subject and no audience

Decoded from `/app/.hermes/mcp-tokens/gateway.json` in `hermes-plain`:

```
CLAIMS PRESENT: [azp, exp, groups, iat, iss, jti, resource_access, scope, sid, typ]

  sub:                <ABSENT>
  aud:                <ABSENT>
  preferred_username: <ABSENT>
  azp:                mcp-gateway
  scope:              roles groups
  resource_access:    3 clients, 18 tool roles total
```

This is stronger than "the agent borrows the operator's identity". **No human is named at all**,
and the only software named is `mcp-gateway` — the public client every caller in the realm shares.
The token is a bearer of 18 permissions with no principal attached.

Two consequences:

- Adding a subject is the cheapest visible improvement available, and it is a prerequisite for
  everything else here.
- RFC 8693 standard token exchange **will fail until `aud` is populated**: Keycloak requires the
  requesting client to be the subject token's `azp` or to appear in its `aud`. Today it is neither.
  An audience mapper is a hard prerequisite, not a refinement.

## 2. Why there is no subject: the realm replaced Keycloak's built-in scopes

Live realm `waterplant-user-9c5ls`:

```
client-scopes: offline_access (no mappers)
               roles          (resource_access -> oidc-usermodel-client-role-mapper)
               groups         (groups -> oidc-group-membership-mapper)

client mcp-gateway: publicClient=true, fullScopeAllowed=true
                    defaultClientScopes = [roles, groups]
                    protocolMappers     = NONE
```

The realm import at `automation/gitops/tenant-platform/templates/mcp-gateway.yaml` declares
`clientScopes:` explicitly, which **replaces** Keycloak's built-ins rather than adding to them.
No `basic` scope means no `sub` mapper; no `profile` scope means no `preferred_username`. This is
a side effect of the import, not a deliberate choice — nothing in the repo argues for an
anonymous token.

Note also that `openid` appears in the chart's `defaultClientScopes` but **not** in the live
realm. It is not a real client scope name, so that entry is inert.

## 3. Token exchange is available; so are two client-auth methods worth knowing about

From `/.well-known/openid-configuration` on the participant realm:

```
grant_types_supported:                 ... urn:ietf:params:oauth:grant-type:token-exchange ...
scopes_supported:                      [openid, offline_access, roles, groups]
token_endpoint_auth_methods_supported: [private_key_jwt, client_secret_basic, client_secret_post,
                                        tls_client_auth, client_secret_jwt]
```

`scopes_supported` independently confirms finding 2 — no `basic`, no `profile`.

The presence of **both** `private_key_jwt` and `tls_client_auth` matters for the SPIFFE design.
SPIRE issues X509-SVIDs as its primary credential and JWT-SVIDs secondarily, so mTLS client
authentication with an X509-SVID is arguably a more natural binding than a JWT-SVID used as a
`private_key_jwt` assertion. See [05-spiffe-and-ztwim.md](05-spiffe-and-ztwim.md).

## 4. The deployed OpenShell cannot do SPIFFE-backed token grants

This is the finding that most changes the plan.

The vendored chart (`helm-chart-0.0.92.tgz`) *does* carry a SPIFFE switch —
`server.providerTokenGrants.spiffe.{enabled,workloadApiSocketPath}` — but enabling it renders
exactly one config key (`provider_spiffe_workload_api_socket_path`), the chart's own unit test
asserts `[openshell.gateway.spiffe]` is **not** rendered, and the StatefulSet mounts no SPIFFE
volume.

More decisively, the **provider profile schema on this build has no dynamic-credential surface at
all**. A live export of a builtin inference profile:

```yaml
id: deepinfra
credentials:
- name: api_key
  env_vars: [DEEPINFRA_API_KEY]
  required: true
  auth_style: bearer
  header_name: authorization
endpoints:
- {host: api.deepinfra.com, port: 443, protocol: rest, access: read-write, enforcement: enforce}
binaries: [/usr/bin/curl, /usr/local/bin/curl]
inference_capable: true
```

There is no `token_grant`, no `refresh.strategy`, no `client_assertion_type`, no `subject_token`.
The newer OpenShell documentation describes all of those, but at **v0.1.9** — against a deployed
gateway chart of **0.0.92** and CLI **0.0.88**. `openshell provider create` does expose a
`--runtime-credentials` flag ("credentials resolved at runtime by the gateway/sandbox"), but there
is no profile schema on this build to drive it.

**Consequence:** the SPIFFE work must not go through OpenShell's provider mechanism on the current
build. Do it on `hermes-plain` with a plain `csi.spiffe.io` volume and a `ClusterSPIFFEID`, which
keeps OpenShell off the critical path entirely. Extending it into the sandbox is a separate,
later question gated on an OpenShell upgrade.

### Incidental observation

`seed_provider()` in `bridge-supervisor.sh` creates the model provider with `--type openai`, and
the provider exists and works (`maas | openai | 1 credential | 1 config`) — but there is **no
`openai` profile** in either the workspace-scoped or global profile list on this build. The
gateway accepted an unrecognised profile type and stored it. The lab works, so this is an
observation rather than a defect, but it means provider-type names are not validated against the
profile catalogue here.

## 5. The MCP servers have a native identity surface (mcp 2.x)

The three MCP servers run **mcp 2.x**, where `FastMCP` was renamed to `MCPServer`. Probing the
live `maintenance-mcp`:

```
mcp.server submodules include: auth, context, request_state, mcpserver, ...

mcp.server.request_state exposes: get_access_token, authenticated_principal,
                                  principal_components, ServerRequestContext,
                                  RequestStateSecurity, RequestStateCodec
```

This is better than the custom-header approach the earlier draft assumed. The SDK has a
first-class place for caller identity, so provenance can be read through a sanctioned API rather
than parsed out of a header in ASGI middleware.

**Caveat, and it is a real one:** the servers have no auth configured today — `settings.py`
exposes only `PLANT_API_URL`, `HOST`, `PORT`, `REQUEST_TIMEOUT_S`, `ALLOWED_HOSTS`, with no
issuer, audience or verifier. So `get_access_token()` will return nothing until a verifier is
configured. Whether to configure one, or to keep enforcement strictly at the gateway and pass an
injected header instead, is the open design question in
[06-provenance.md](06-provenance.md) — and it touches the lab's stated principle that
"authorization belongs to MCP Gateway".

## 6. `AGENT_API_KEY` is populated — correcting an earlier claim

An earlier draft recorded the console's `AGENT_API_KEY` as resolving empty, and flagged it as a
possible open front door. That was wrong, and the cause was a redaction filter in my own
inspection command that hid any line matching `KEY|PASSWORD|SECRET|TOKEN`.

Verified directly:

```
AGENT_API_KEY set: True | length: 48
  <- secretKeyRef hermes-env/API_SERVER_KEY (optional: true)
  hermes-env keys: [API_SERVER_KEY, MODEL_API_KEY]
```

No risk here. Recorded so the phantom does not reappear.

## 7. FGAP V2 is off but available

```
realm waterplant-user-9c5ls: adminPermissionsEnabled: false
```

The field exists, which means the per-realm toggle is available on this Keycloak (26.4.18) — FGAP
V2 has been GA and on by default since Keycloak 26.2. It is **not** a blocker for delegation; the
blocker is the `token-exchange-delegation` preview feature, which needs Keycloak 26.8+. See
[04-keycloak-upgrade-path.md](04-keycloak-upgrade-path.md).

## Deliberately not done in Phase 0

Both are changes, and both are worth doing at implementation time:

- `openshell provider profile lint` on a candidate profile — needs a file written into a pod.
  Largely moot given finding 4.
- Authorino `logLevel: debug` — a cluster-wide patch, best done in a quiet window. It is the
  cheapest instrument for the header-propagation question in
  [08-open-questions.md](08-open-questions.md).
