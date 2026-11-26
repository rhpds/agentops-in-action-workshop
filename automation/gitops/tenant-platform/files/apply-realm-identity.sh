#!/usr/bin/env bash
# Apply the agent-identity realm delta to an ALREADY-PROVISIONED tenant.
#
# Why this exists: a KeycloakRealmImport applies once. The operator's Job runs
#   kc.sh import --optimized --file=... --override=false
# and is Complete, so editing the realm block in templates/mcp-gateway.yaml has
# NO effect on a tenant that already exists. The chart is the source of truth
# for new clusters; this is the same delta for live ones. Keep them in step.
#
# Nothing runs this automatically. It is idempotent: re-running it reports what
# already exists and changes nothing.
#
# Creates, in realm waterplant-<username>:
#   on client mcp-gateway   aud-<agent>        oidc-audience-mapper
#                           preferred-username oidc-usermodel-property-mapper
#   client <agent>          confidential, no service account, exchange enabled
#   on that client          aud-mcp-gateway-resource, preferred-username
# And, only when FEDERATED_SPIFFE_ID is set:
#   idp spiffe              trust domain + SPIRE bundle endpoint
#   flow clients-federated  a copy of the built-in `clients` flow + federated-jwt
#   on that client          clientAuthenticatorType=federated-jwt, no secret
#
# Usage:
#   KC_PASS=... ./apply-realm-identity.sh <username> <keycloak-host> <apps-domain> [agent-client-id] [agent-secret]
#
# To also swap the clients' secrets for SPIRE-attested JWT-SVIDs (Stage 8/8b),
# add FEDERATED_BROKER_SPIFFE_ID and FEDERATED_AGENT_SPIFFE_ID. Optional overrides: FEDERATED_TRUST_DOMAIN,
# FEDERATED_BUNDLE_ENDPOINT, FEDERATED_IDP_ALIAS, FEDERATED_FLOW_ALIAS.
#   FEDERATED_BROKER_SPIFFE_ID=spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell \\
#   FEDERATED_AGENT_SPIFFE_ID=spiffe://agentops.lab/ns/<user>-agentops/sa/<user>-openshell-sandbox \\
#   KC_PASS=... ./apply-realm-identity.sh ...
# PER_TOOL_SCOPES=false skips the 18 per-tool client scopes.
#
# Never echoes a secret. Reads KC_PASS from the environment, or prompts.

set -euo pipefail

USERNAME="${1:?usage: $0 <username> <keycloak-host> <apps-domain> [agent-client-id] [agent-secret]}"
KC_HOST="${2:?keycloak host, e.g. sso.apps.example.com}"
APPS_DOMAIN="${3:?apps domain, e.g. apps.example.com}"
AGENT_ID="${4:-hermes-agent}"
AGENT_SECRET="${5:-hermes-agent-lab-secret}"

REALM="waterplant-${USERNAME}"
NS="${USERNAME}-agentops"
KC="https://${KC_HOST}"
GW_RESOURCE="http://mcp-gateway-data-science-gateway-class.${NS}.svc.cluster.local:8080/mcp"

if [ -z "${KC_PASS:-}" ]; then
  read -rsp "Keycloak realm admin password for ${REALM} (user 'admin'): " KC_PASS; echo
fi

say() { printf '  %s\n' "$*"; }

TOKEN=$(curl -sk --max-time 30 -X POST "${KC}/realms/${REALM}/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=admin-cli -d username=admin --data-urlencode "password=${KC_PASS}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')
[ -n "$TOKEN" ] || { echo "could not authenticate to ${REALM} as admin" >&2; exit 1; }

api() { curl -sk --max-time 30 -H "Authorization: Bearer ${TOKEN}" "$@"; }

client_uuid() {
  api "${KC}/admin/realms/${REALM}/clients?clientId=$1" \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r[0]["id"] if r else "")'
}

has_mapper() {  # has_mapper <client-uuid> <mapper-name>
  api "${KC}/admin/realms/${REALM}/clients/$1/protocol-mappers/models" \
    | python3 -c "import json,sys; print('yes' if any(m['name']=='$2' for m in json.load(sys.stdin)) else 'no')"
}

add_mapper() { # add_mapper <client-uuid> <name> <json-payload>
  if [ "$(has_mapper "$1" "$2")" = yes ]; then say "mapper $2: already present"; return 0; fi
  code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
    "${KC}/admin/realms/${REALM}/clients/$1/protocol-mappers/models" -d "$3")
  [ "$code" = 201 ] && say "mapper $2: created" || { echo "  mapper $2: FAILED (HTTP $code)" >&2; exit 1; }
}

echo "realm ${REALM} on ${KC}"

# --- 1. mappers on the public client the operator authenticates through ------
GW_UUID=$(client_uuid mcp-gateway)
[ -n "$GW_UUID" ] || { echo "client mcp-gateway not found in ${REALM}" >&2; exit 1; }

# Required for RFC 8693: the requesting client must be the subject token's azp
# or appear in its aud. Without it the exchange fails 400 "Client is not within
# the token audience".
add_mapper "$GW_UUID" "aud-${AGENT_ID}" "$(cat <<JSON
{"name":"aud-${AGENT_ID}","protocol":"openid-connect","protocolMapper":"oidc-audience-mapper",
 "config":{"included.client.audience":"${AGENT_ID}","access.token.claim":"true",
           "introspection.token.claim":"true","id.token.claim":"false"}}
JSON
)"

# The realm replaced Keycloak's built-in client scopes, so there is no `basic`
# scope and no subject, and no `profile` scope and no username. This is the only
# reason a human appears in the token at all.
add_mapper "$GW_UUID" "preferred-username" "$(cat <<'JSON'
{"name":"preferred-username","protocol":"openid-connect","protocolMapper":"oidc-usermodel-property-mapper",
 "config":{"user.attribute":"username","claim.name":"preferred_username","jsonType.label":"String",
           "access.token.claim":"true","id.token.claim":"true",
           "introspection.token.claim":"true","userinfo.token.claim":"true"}}
JSON
)"

# --- 2. the agent's own client -----------------------------------------------
AGENT_UUID=$(client_uuid "${AGENT_ID}")
if [ -n "$AGENT_UUID" ]; then
  say "client ${AGENT_ID}: already present"
else
  code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
    "${KC}/admin/realms/${REALM}/clients" -d "$(cat <<JSON
{"clientId":"${AGENT_ID}",
 "name":"Hermie agent identity",
 "description":"The agent acting on the operator's behalf. No service account: it can only re-mint a token someone else authenticated.",
 "enabled":true,"publicClient":false,"serviceAccountsEnabled":false,
 "directAccessGrantsEnabled":false,"standardFlowEnabled":false,"implicitFlowEnabled":false,
 "fullScopeAllowed":true,"protocol":"openid-connect",
 "secret":"${AGENT_SECRET}",
 "defaultClientScopes":["roles","groups"],
 "attributes":{"standard.token.exchange.enabled":"true"}}
JSON
)")
  [ "$code" = 201 ] && say "client ${AGENT_ID}: created" || { echo "  client ${AGENT_ID}: FAILED (HTTP $code)" >&2; exit 1; }
  AGENT_UUID=$(client_uuid "${AGENT_ID}")
fi

# Per-hop audience, fixed rather than requested: passing audience= on the
# exchange re-scopes which mappers apply and can drop resource_access.
add_mapper "$AGENT_UUID" "aud-mcp-gateway-resource" "$(cat <<JSON
{"name":"aud-mcp-gateway-resource","protocol":"openid-connect","protocolMapper":"oidc-audience-mapper",
 "config":{"included.custom.audience":"${GW_RESOURCE}","access.token.claim":"true",
           "introspection.token.claim":"true","id.token.claim":"false"}}
JSON
)"

# Mappers are per client and the exchanged token is issued FOR this one, so it
# carries only this client's mappers plus the shared scopes. Measured: without
# this the exchanged token had sub but preferred_username ABSENT, leaving the
# actor a bare UUID.
add_mapper "$AGENT_UUID" "preferred-username" "$(cat <<'JSON'
{"name":"preferred-username","protocol":"openid-connect","protocolMapper":"oidc-usermodel-property-mapper",
 "config":{"user.attribute":"username","claim.name":"preferred_username","jsonType.label":"String",
           "access.token.claim":"true","id.token.claim":"true",
           "introspection.token.claim":"true","userinfo.token.claim":"true"}}
JSON
)"

# --- 3. SPIFFE as the agent's credential (optional) --------------------------
# Off unless FEDERATED_SPIFFE_ID is set. Replaces the client's shared secret
# with a SPIRE-attested JWT-SVID, per docs/agent-identity Stage 8 route 1.
#
# Prerequisite the chart cannot supply: the Keycloak CR needs
#   spec.features.enabled: [spiffe, client-auth-federated]
# Both are preview, and on a shared RHDP cluster that CR is not ours. Without
# them the `spiffe` identity provider type and the `federated-jwt` client
# authenticator are simply absent and the calls below 400.
#
# The trap that cost a session: `federated-jwt` is added to a realm's client
# authentication flow by DefaultAuthenticationFlows.clientAuthFlow() ONLY when
# CLIENT_AUTH_FEDERATED is enabled AT REALM CREATION. A realm imported before
# the flag was set keeps the four stock executions, the admin API refuses to
# add one ("It is illegal to add execution to a built in flow"), and every
# attempt fails as `client_not_found` -- which looks like the client lookup but
# is actually the authenticator never running. FederatedJWTClientAuthenticator
# never calls context.setClient(), so EVERY failure in it reports that error.
# Hence the copy-extend-rebind below.
if [ -n "${FEDERATED_BROKER_SPIFFE_ID:-}" ]; then
  TRUST_DOMAIN="${FEDERATED_TRUST_DOMAIN:-spiffe://agentops.lab}"
  BUNDLE_ENDPOINT="${FEDERATED_BUNDLE_ENDPOINT:-https://spire-oidc.${APPS_DOMAIN}/keys}"
  IDP_ALIAS="${FEDERATED_IDP_ALIAS:-spiffe}"
  FLOW="${FEDERATED_FLOW_ALIAS:-clients-federated}"

  # 3a. the SPIFFE identity provider. The config key for the trust domain is
  # `issuer`, NOT `trustDomain`: SpiffeIdentityProviderConfig.getTrustDomain()
  # reads IdentityProviderModel.ISSUER. It must match ^spiffe://[a-z0-9.\-_]*$
  # or the create fails 400 "Invalid trust domain name".
  if api "${KC}/admin/realms/${REALM}/identity-provider/instances/${IDP_ALIAS}" \
       | grep -q '"alias"'; then
    say "idp ${IDP_ALIAS}: already present"
  else
    code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
      -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      "${KC}/admin/realms/${REALM}/identity-provider/instances" -d "$(cat <<JSON
{"alias":"${IDP_ALIAS}","providerId":"spiffe","enabled":true,
 "config":{"issuer":"${TRUST_DOMAIN}","bundleEndpoint":"${BUNDLE_ENDPOINT}"}}
JSON
)")
    [ "$code" = 201 ] && say "idp ${IDP_ALIAS}: created" \
      || { echo "  idp ${IDP_ALIAS}: FAILED (HTTP $code) -- is spiffe enabled on the Keycloak CR?" >&2; exit 1; }
  fi

  # 3b. a writable copy of the built-in `clients` flow, plus the execution.
  if api "${KC}/admin/realms/${REALM}/authentication/flows" \
       | python3 -c "import json,sys; sys.exit(0 if any(f['alias']=='${FLOW}' for f in json.load(sys.stdin)) else 1)"; then
    say "flow ${FLOW}: already present"
  else
    code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
      -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      "${KC}/admin/realms/${REALM}/authentication/flows/clients/copy" -d "{\"newName\":\"${FLOW}\"}")
    [ "$code" = 201 ] && say "flow ${FLOW}: copied from clients" \
      || { echo "  flow ${FLOW}: FAILED (HTTP $code)" >&2; exit 1; }
  fi

  EXEC_JSON=$(api "${KC}/admin/realms/${REALM}/authentication/flows/${FLOW}/executions" \
    | python3 -c 'import json,sys; print(json.dumps(next((e for e in json.load(sys.stdin) if e.get("providerId")=="federated-jwt"), {})))')
  if [ "$EXEC_JSON" = '{}' ]; then
    code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
      -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      "${KC}/admin/realms/${REALM}/authentication/flows/${FLOW}/executions/execution" \
      -d '{"provider":"federated-jwt"}')
    [ "$code" = 201 ] && say "execution federated-jwt: added" \
      || { echo "  execution federated-jwt: FAILED (HTTP $code) -- is client-auth-federated enabled?" >&2; exit 1; }
    EXEC_JSON=$(api "${KC}/admin/realms/${REALM}/authentication/flows/${FLOW}/executions" \
      | python3 -c 'import json,sys; print(json.dumps(next(e for e in json.load(sys.stdin) if e.get("providerId")=="federated-jwt")))')
  fi
  # It lands DISABLED; an ALTERNATIVE sitting beside the four stock ones means
  # the secret path keeps working for every other client in the realm.
  code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X PUT \
    -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
    "${KC}/admin/realms/${REALM}/authentication/flows/${FLOW}/executions" \
    -d "$(printf '%s' "$EXEC_JSON" | python3 -c 'import json,sys; e=json.load(sys.stdin); e["requirement"]="ALTERNATIVE"; print(json.dumps(e))')")
  [ "$code" = 204 ] && say "execution federated-jwt: ALTERNATIVE" \
    || { echo "  execution requirement: FAILED (HTTP $code)" >&2; exit 1; }

  # 3c. bind the copy as the realm's client authentication flow
  code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X PUT \
    -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
    "${KC}/admin/realms/${REALM}" -d "{\"realm\":\"${REALM}\",\"clientAuthenticationFlow\":\"${FLOW}\"}")
  [ "$code" = 204 ] && say "realm clientAuthenticationFlow: ${FLOW}" \
    || { echo "  flow binding: FAILED (HTTP $code)" >&2; exit 1; }

  # 3d. the client itself. jwt.credential.sub and jwt.credential.issuer are
  # already in JpaClientProviderFactory.REQUIRED_SEARCHABLE_ATTRIBUTES, so the
  # attribute lookup needs no build option.
  #
  # FEDERATED_SPIFFE_ID is the SPIFFE ID of whichever workload holds the
  # credential -- one client, one ID, because the lookup demands exactly one
  # match. Today that is the OpenShell gateway, the only pod on the token path
  # with a csi.spiffe.io mount.
  # ---- 3c2. undo the earlier design, if this tenant ran it ------------------
  # An earlier version of this script made ${AGENT_ID} itself the broker by
  # writing jwt.credential.* onto it. Leaving those behind is not cosmetic: the
  # federated lookup does searchClientsByAttributes and throws
  # "Multiple clients matches attributes" when more than one client carries the
  # same jwt.credential.sub -- surfacing as a flat `invalid_client` that names
  # nothing. Null them out before creating the broker that should own them.
  #
  # Note PUT MERGES the attributes map, so clearing requires explicit nulls;
  # sending a map without the keys leaves them in place.
  if api "${KC}/admin/realms/${REALM}/clients/${AGENT_UUID}" | grep -q 'jwt.credential.sub'; then
    code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X PUT \
      -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      "${KC}/admin/realms/${REALM}/clients/${AGENT_UUID}" \
      -d "{\"clientId\":\"${AGENT_ID}\",\"clientAuthenticatorType\":\"client-secret\",\"attributes\":{\"jwt.credential.issuer\":null,\"jwt.credential.sub\":null}}")
    [ "$code" = 204 ] && say "client ${AGENT_ID}: cleared stale jwt.credential.* (was the broker)" \
      || { echo "  clearing ${AGENT_ID} attributes: FAILED (HTTP $code)" >&2; exit 1; }
  fi

  # ---- 3d. the DELEGATION BROKER, a NEW client ------------------------------
  # Deliberately NOT a change to ${AGENT_ID}. That client keeps its secret and
  # keeps working, so enabling attested mode is additive and no live tenant
  # breaks. Flipping it instead took both runtimes down on 2026-11-26.
  BROKER_ID="${FEDERATED_BROKER_CLIENT_ID:-delegation-broker}"
  BROKER_UUID=$(client_uuid "${BROKER_ID}")
  if [ -n "$BROKER_UUID" ]; then
    say "client ${BROKER_ID}: already present"
  else
    code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
      -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
      "${KC}/admin/realms/${REALM}/clients" -d "$(cat <<JSON
{"clientId":"${BROKER_ID}",
 "name":"Delegation broker",
 "description":"The OpenShell gateway, authenticated by its SPIRE-issued JWT-SVID. Exchanges a stored user token for an intermediate token addressed to one specific sandbox.",
 "enabled":true,"publicClient":false,"serviceAccountsEnabled":false,
 "directAccessGrantsEnabled":false,"standardFlowEnabled":false,"implicitFlowEnabled":false,
 "fullScopeAllowed":true,"protocol":"openid-connect",
 "clientAuthenticatorType":"federated-jwt",
 "defaultClientScopes":["roles","groups"],
 "attributes":{"standard.token.exchange.enabled":"true",
               "jwt.credential.issuer":"${IDP_ALIAS}",
               "jwt.credential.sub":"${FEDERATED_BROKER_SPIFFE_ID}"}}
JSON
)")
    [ "$code" = 201 ] && say "client ${BROKER_ID}: created, federated-jwt <- ${FEDERATED_BROKER_SPIFFE_ID}" \
      || { echo "  client ${BROKER_ID}: FAILED (HTTP $code)" >&2; exit 1; }
    BROKER_UUID=$(client_uuid "${BROKER_ID}")
  fi

  # RFC 8693 needs the requesting client in the subject token's aud, and in
  # attested mode that requester is the broker, not the secret-path agent.
  add_mapper "$GW_UUID" "aud-${BROKER_ID}" "$(cat <<JSON
{"name":"aud-${BROKER_ID}","protocol":"openid-connect","protocolMapper":"oidc-audience-mapper",
 "config":{"included.client.audience":"${BROKER_ID}","access.token.claim":"true",
           "introspection.token.claim":"true","id.token.claim":"false"}}
JSON
)"

  # ---- 3e. the AGENT client, whose clientId IS the sandbox's SPIFFE ID ------
  # Forced, not chosen: OpenShell always sets the intermediate token's audience
  # to the supervisor's SVID subject, and Keycloak resolves the final
  # exchange's client out of that audience. So azp on the token Authorino sees
  # is this SPIFFE ID, and tenant-policy templates its predicate to match.
  if [ -n "${FEDERATED_AGENT_SPIFFE_ID:-}" ]; then
    SBX_UUID=$(client_uuid "${FEDERATED_AGENT_SPIFFE_ID}")
    if [ -n "$SBX_UUID" ]; then
      say "client ${FEDERATED_AGENT_SPIFFE_ID}: already present"
    else
      code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
        -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
        "${KC}/admin/realms/${REALM}/clients" -d "$(cat <<JSON
{"clientId":"${FEDERATED_AGENT_SPIFFE_ID}",
 "name":"Hermie agent (attested)",
 "description":"The sandbox supervisor, authenticated by its SPIRE-issued JWT-SVID. Signs the final token exchange, so its id is the azp Authorino sees.",
 "enabled":true,"publicClient":false,"serviceAccountsEnabled":false,
 "directAccessGrantsEnabled":false,"standardFlowEnabled":false,"implicitFlowEnabled":false,
 "fullScopeAllowed":false,"protocol":"openid-connect",
 "clientAuthenticatorType":"federated-jwt",
 "defaultClientScopes":["roles","groups"],
 "attributes":{"standard.token.exchange.enabled":"true",
               "jwt.credential.issuer":"${IDP_ALIAS}",
               "jwt.credential.sub":"${FEDERATED_AGENT_SPIFFE_ID}"}}
JSON
)")
      [ "$code" = 201 ] && say "client ${FEDERATED_AGENT_SPIFFE_ID}: created" \
        || { echo "  agent client: FAILED (HTTP $code)" >&2; exit 1; }
      SBX_UUID=$(client_uuid "${FEDERATED_AGENT_SPIFFE_ID}")
    fi

    # its own mappers -- without these the final token came back with
    # preferred_username and aud both absent (measured 2026-11-26)
    add_mapper "$SBX_UUID" "aud-mcp-gateway-resource" "$(cat <<JSON
{"name":"aud-mcp-gateway-resource","protocol":"openid-connect","protocolMapper":"oidc-audience-mapper",
 "config":{"included.custom.audience":"${GW_RESOURCE}","access.token.claim":"true",
           "introspection.token.claim":"true","id.token.claim":"false"}}
JSON
)"
    add_mapper "$SBX_UUID" "preferred-username" "$(cat <<'JSON'
{"name":"preferred-username","protocol":"openid-connect","protocolMapper":"oidc-usermodel-property-mapper",
 "config":{"user.attribute":"username","claim.name":"preferred_username","jsonType.label":"String",
           "access.token.claim":"true","id.token.claim":"true",
           "introspection.token.claim":"true","userinfo.token.claim":"true"}}
JSON
)"

    # the broker needs an audience mapper naming this client, or its
    # intermediate exchange is refused 400 "Requested audience not available":
    # checkRequestedAudiences asserts the ISSUED token carries the audience.
    add_mapper "$BROKER_UUID" "aud-agent" "$(cat <<JSON
{"name":"aud-agent","protocol":"openid-connect","protocolMapper":"oidc-audience-mapper",
 "config":{"included.client.audience":"${FEDERATED_AGENT_SPIFFE_ID}","access.token.claim":"true",
           "introspection.token.claim":"true","id.token.claim":"false"}}
JSON
)"
  fi


  # ---- 3f. one optional client scope per tool -------------------------------
  # So a single exchange can ask for exactly the tool in flight and the token
  # carries ONE role instead of eighteen. Measured 2026-11-26: this only
  # narrows because the agent client has fullScopeAllowed:false and NO scope
  # mappings of its own -- with either of those different, every token carries
  # every role the operator holds.
  #
  # The tool list is read back from the realm rather than passed in, so it can
  # never drift from the roles that actually exist.
  if [ -n "${FEDERATED_AGENT_SPIFFE_ID:-}" ] && [ "${PER_TOOL_SCOPES:-true}" = true ]; then
    SBX_UUID=$(client_uuid "${FEDERATED_AGENT_SPIFFE_ID}")
    created=0; existing=0
    for mcp in $(api "${KC}/admin/realms/${REALM}/clients" \
          | python3 -c "import json,sys;print(' '.join(c['id'] for c in json.load(sys.stdin) if c['clientId'].startswith('${NS}/')))"); do
      for role in $(api "${KC}/admin/realms/${REALM}/clients/${mcp}/roles" \
            | python3 -c "import json,sys;print(' '.join(r['name'] for r in json.load(sys.stdin) if r['name'].startswith('tool:')))"); do
        tool=${role#tool:}
        scope="tool-${tool}"
        sid=$(api "${KC}/admin/realms/${REALM}/client-scopes" \
              | python3 -c "import json,sys;print(next((c['id'] for c in json.load(sys.stdin) if c['name']=='${scope}'),''))")
        if [ -z "$sid" ]; then
          code=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' -X POST \
            -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
            "${KC}/admin/realms/${REALM}/client-scopes" -d "$(cat <<JSON
{"name":"${scope}","description":"Permission to call ${tool} on this one hop",
 "protocol":"openid-connect",
 "attributes":{"include.in.token.scope":"true","display.on.consent.screen":"false"}}
JSON
)")
          [ "$code" = 201 ] || { echo "  scope ${scope}: FAILED (HTTP $code)" >&2; exit 1; }
          sid=$(api "${KC}/admin/realms/${REALM}/client-scopes" \
                | python3 -c "import json,sys;print(next(c['id'] for c in json.load(sys.stdin) if c['name']=='${scope}'))")
          created=$((created+1))
        else
          existing=$((existing+1))
        fi
        # the scope -> role mapping, and the scope onto the agent as OPTIONAL
        rolejson=$(api "${KC}/admin/realms/${REALM}/clients/${mcp}/roles/${role}" \
          | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps([{"id":d["id"],"name":d["name"]}]))')
        curl -sk --max-time 30 -o /dev/null -X POST \
          -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
          "${KC}/admin/realms/${REALM}/client-scopes/${sid}/scope-mappings/clients/${mcp}" -d "$rolejson"
        curl -sk --max-time 30 -o /dev/null -X PUT -H "Authorization: Bearer ${TOKEN}" \
          "${KC}/admin/realms/${REALM}/clients/${SBX_UUID}/optional-client-scopes/${sid}"
      done
    done
    say "per-tool scopes: ${created} created, ${existing} already present"
  fi

  echo
  say "${AGENT_ID} is UNCHANGED and still authenticates with its secret --"
  say "attested mode is additive, so the fallback path keeps working."
  say "to roll back: delete ${BROKER_ID} and the agent client, and point"
  say "tenant-policy's predicate back at ${AGENT_ID}."
fi

echo
echo "verify:"
cat <<EOF
  OPTOK=\$(curl -sk -X POST "${KC}/realms/${REALM}/protocol/openid-connect/token" \\
    -d grant_type=password -d client_id=mcp-gateway -d username=operator -d password=operator \\
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')

  curl -sk -X POST "${KC}/realms/${REALM}/protocol/openid-connect/token" \\
    -d grant_type=urn:ietf:params:oauth:grant-type:token-exchange \\
    -d client_id=${AGENT_ID} -d client_secret=<secret> \\
    -d subject_token="\$OPTOK" \\
    -d subject_token_type=urn:ietf:params:oauth:token-type:access_token

  expect: azp=${AGENT_ID}, sub + preferred_username = the operator,
          aud=${GW_RESOURCE}, resource_access unchanged at 18 roles
EOF
