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
#
# Usage:
#   KC_PASS=... ./apply-realm-identity.sh <username> <keycloak-host> <apps-domain> [agent-client-id] [agent-secret]
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
