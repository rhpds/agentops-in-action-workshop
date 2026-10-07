#!/usr/bin/env bash
# Prepares and supervises one participant's Hermes in their OpenShell sandbox.
# See templates/bridge.yaml for the split between this and the participant.
#
# The participant creates the sandbox, uploads /hermes into it, starts Hermes
# and exposes it, from the `cli` container beside this one. This script:
#
#   prepare   before any of that: waits for the MCP gateway, renders Hermes'
#             config, fetches the MLflow plugin and token, and writes it all to
#             /hermes for the participant to upload
#   adopt     after it: finds the exposed service and points the console's
#             relay at it
#   restart   Hermes when the operator's Keycloak tool roles change, or when it
#             stops answering. Never on a policy change: those are the
#             participant's to apply, and restart, by hand.
#
# Never runs with -x: the model key and Hermes' server key pass through here.
set -uo pipefail
export PATH="/tools:$PATH"
export HOME=/tmp
export XDG_CONFIG_HOME=/tmp/.config
umask 077

WORK=/tmp/work
OUT=/hermes
mkdir -p "$WORK/probe/mcp-tokens"
GATEWAY_ENDPOINT="https://${GATEWAY_HOST}:8080"
RELAY_HOST=""
PUBLISHED_POLICY=""
# Where the participant's upload (a tar of /hermes streamed through
# `openshell sandbox exec`, unpacked at /sandbox/setup) puts start-hermes.sh.
# Must match the lab instructions.
START_SCRIPT=/sandbox/setup/start-hermes.sh
# Serializes restart_hermes(): role_watch_loop calls it from a background
# process, and must never overlap the main loop's own calls to it.
RESTART_LOCK=/tmp/work/restart.lock

log()   { echo "[$(date -u +%H:%M:%S)] $*"; }
strip() { sed 's/\x1b\[[0-9;]*m//g'; }
# Runs inside the sandbox's policy-enforced network namespace, as the sandbox
# user. Plain `oc exec` would land outside it, where the relay cannot reach.
X()     { openshell sandbox exec --name "$SANDBOX_NAME" -- /bin/sh -c "$1"; }

secret_value() {
  oc get secret "$HERMES_ENV_SECRET" -n "$AGENTOPS_NS" -o "jsonpath={.data.$1}" 2>/dev/null | base64 -d
}

# The sandbox policy participants edit lives in tenant-policy, mounted at
# /policy once that Application has been synced. Until then, the chart's
# baseline, which is equally permissive: an unsynced policy Application means
# open everywhere else in the lab too (no AuthPolicy, no NetworkPolicy).
policy_file() {
  if [ -s /policy/policy.yaml ]; then echo /policy/policy.yaml; else echo /config/baseline-policy.yaml; fi
}
policy_hash() { sha256sum "$(policy_file)" | cut -c1-12; }

connect_cli() {
  local mtls="$XDG_CONFIG_HOME/openshell/gateways/lab/mtls"
  mkdir -p "$mtls"
  cp /mtls/ca.crt /mtls/tls.crt /mtls/tls.key "$mtls/"
  openshell gateway add "$GATEWAY_ENDPOINT" --local --name lab >/dev/null 2>&1 || true
  openshell gateway select lab >/dev/null 2>&1
  log "waiting for the OpenShell gateway at $GATEWAY_ENDPOINT"
  until openshell sandbox list >/dev/null 2>&1; do sleep 5; done
}

sandbox_phase() {
  openshell sandbox list 2>/dev/null | strip | awk -v n="$SANDBOX_NAME" '$1 == n {print $NF}'
}

# The relay URL of the participant's exposed `openai` service, if there is one.
service_url() {
  openshell service list 2>/dev/null | strip | awk -v n="$SANDBOX_NAME" '$1 == n && $2 == "openai" {print $NF}'
}

# publish <local file> <name in /hermes>
# Atomic, so the participant never uploads a half-written file.
publish() {
  cp "$1" "$OUT/.$2.tmp" && chmod 644 "$OUT/.$2.tmp" && mv "$OUT/.$2.tmp" "$OUT/$2"
}

publish_policy() {
  publish "$(policy_file)" policy.yaml
  PUBLISHED_POLICY=$(policy_hash)
}

# ---------------------------------------------------------------------------
# Watches Keycloak for changes to the operator's tool: roles and restarts
# Hermes the moment they change. Without this, a grant or revoke only reaches
# Hermes on mcp-token-refresh.py's next scheduled refresh at best, and was
# measured to take up to 20 minutes in practice — Hermes' MCP client does not
# reconnect just because the token file on disk changed underneath it.
#
# Polls the realm admin REST API with the realm's admin account rather than a
# Keycloak webhook: this cluster's Keycloak has no webhook feature enabled,
# and turning one on is a cluster-wide change this does not need. admin's
# password is the same lab credential already in git as
# tenant-platform's keycloak.adminPassword — not a secret, see there.
#
# KC_HOST and KC_REALM come from MCP_TOKEN_URL rather than their own values,
# since that URL already names both.
# ---------------------------------------------------------------------------
KC_ISSUER=${MCP_TOKEN_URL%/protocol/openid-connect/token}
KC_HOST=$(printf '%s' "$KC_ISSUER" | sed -E 's#^https://([^/]+)/.*#\1#')
KC_REALM=$(printf '%s' "$KC_ISSUER" | sed -E 's#.*/realms/##')

kc_admin_token() {
  curl -sk --max-time 10 -X POST \
    "https://${KC_HOST}/realms/${KC_REALM}/protocol/openid-connect/token" \
    -d grant_type=password -d client_id="$MCP_CLIENT_ID" \
    -d username="$ROLE_WATCH_ADMIN_USER" -d password="$ROLE_WATCH_ADMIN_PASSWORD" \
    2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])" 2>/dev/null
}

kc_operator_id() {
  local token="$1"
  curl -sk --max-time 10 -H "Authorization: Bearer $token" \
    "https://${KC_HOST}/admin/realms/${KC_REALM}/users?username=${MCP_USERNAME}&exact=true" \
    2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])" 2>/dev/null
}

# Hashes every tool: role currently mapped onto the operator, across every
# MCP server client. Any grant or revoke changes the hash.
kc_role_hash() {
  local token="$1" id="$2"
  curl -sk --max-time 10 -H "Authorization: Bearer $token" \
    "https://${KC_HOST}/admin/realms/${KC_REALM}/users/${id}/role-mappings" \
    2>/dev/null | python3 -c "
import sys, json, hashlib
try:
    d = json.load(sys.stdin)
    pairs = sorted(
        f\"{cm['client']}:{r['name']}\"
        for cm in d.get('clientMappings', {}).values()
        for r in cm.get('mappings', [])
    )
    print(hashlib.sha256(','.join(pairs).encode()).hexdigest()[:16])
except Exception:
    pass
" 2>/dev/null
}

# Runs for the life of the container, alongside the main loop, as its own
# background process.
role_watch_loop() {
  local token id hash last
  log "role watch: polling every ${ROLE_WATCH_SECONDS}s for tool: role changes on $MCP_USERNAME"
  token=$(kc_admin_token)
  id=$(kc_operator_id "$token")
  if [ -z "$id" ]; then
    log "role watch: could not resolve $MCP_USERNAME's user id; role watch is off"
    return
  fi
  last=$(kc_role_hash "$token" "$id")
  while true; do
    sleep "$ROLE_WATCH_SECONDS"
    token=$(kc_admin_token) || continue
    hash=$(kc_role_hash "$token" "$id")
    [ -z "$hash" ] && continue
    if [ "$hash" != "$last" ]; then
      log "role watch: $MCP_USERNAME's tool roles changed; restarting Hermes"
      last="$hash"
      restart_hermes || log "role watch: restart failed; Hermes keeps its old roles until it is restarted"
    fi
  done
}

# ---------------------------------------------------------------------------
# MLflow tracing, prepared here and uploaded by the participant.
# ---------------------------------------------------------------------------
otel_enabled() { [ "${MLFLOW_ENABLED:-false}" = "true" ] && [ -n "${MLFLOW_TRACKING_URI:-}" ]; }

# MLflow identifies the caller by this token and authorizes it with a
# SelfSubjectAccessReview, so the agent needs one of its own: the bridge's
# projected token rotates, and what goes into the sandbox is a static file.
# templates/bridge.yaml allows this ServiceAccount to mint a token for itself
# and for nothing else.
mlflow_token() {
  oc create token hermes-openshell-bridge -n "$OPENSHELL_NS" \
    --duration="${MLFLOW_TOKEN_DURATION_HOURS}h" 2>/dev/null
}

# mlflow_experiment_id <token>
# The experiment this participant's traces land in, created once. The REST API
# is under /mlflow; only OTLP ingest is at the server root.
mlflow_experiment_id() {
  local token="$1" id
  id=$(curl -sk --max-time 30 -H "Authorization: Bearer $token" \
        -H "X-MLflow-Workspace: $AGENTOPS_NS" \
        "${MLFLOW_TRACKING_URI}/mlflow/api/2.0/mlflow/experiments/get-by-name?experiment_name=${MLFLOW_EXPERIMENT}" 2>/dev/null \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('experiment',{}).get('experiment_id',''))" 2>/dev/null)
  if [ -z "$id" ]; then
    id=$(curl -sk --max-time 30 -X POST -H "Authorization: Bearer $token" \
          -H "X-MLflow-Workspace: $AGENTOPS_NS" -H "Content-Type: application/json" \
          -d "{\"name\":\"${MLFLOW_EXPERIMENT}\"}" \
          "${MLFLOW_TRACKING_URI}/mlflow/api/2.0/mlflow/experiments/create" 2>/dev/null \
          | python3 -c "import sys,json;print(json.load(sys.stdin).get('experiment_id',''))" 2>/dev/null)
  fi
  printf '%s' "$id"
}

# hermes_otel is not in the sandbox image. It is fetched here, where no sandbox
# policy applies, checked against the pinned digest and repacked for upload. So
# a participant who tightens their policy stops the traces leaving, not the
# install.
fetch_otel_plugin() {
  local dir="$WORK/otel"
  rm -rf "$dir"; mkdir -p "$dir/pkg"
  if ! curl -fsSL --max-time 120 "$MLFLOW_PLUGIN_URL" -o "$dir/src.tar.gz"; then
    log "could not download hermes_otel from $MLFLOW_PLUGIN_URL"
    return 1
  fi
  if [ "$(sha256sum "$dir/src.tar.gz" | cut -d' ' -f1)" != "$MLFLOW_PLUGIN_SHA256" ]; then
    log "hermes_otel does not match its pinned sha256; not installing it"
    return 1
  fi
  tar -xzf "$dir/src.tar.gz" --strip-components=2 -C "$dir/pkg" "$MLFLOW_PLUGIN_SUBDIR" || return 1
  tar -czf "$dir/pkg.tar.gz" -C "$dir/pkg" . || return 1
  publish "$dir/pkg.tar.gz" hermes_otel.tar.gz
  rm -rf "$dir"
}

# Tracing is best-effort: a participant whose MLflow is unreachable should still
# get a working agent, just an unobservable one. Says which it was.
prepare_otel() {
  rm -f "$OUT/hermes_otel.tar.gz" "$OUT/hermes-otel-config.yaml"
  otel_enabled || return 0
  local token id
  token=$(mlflow_token)
  if [ -z "$token" ]; then log "could not mint an MLflow token; tracing is off"; return 0; fi
  id=$(mlflow_experiment_id "$token")
  if [ -z "$id" ]; then log "no MLflow experiment $MLFLOW_EXPERIMENT; tracing is off"; return 0; fi
  log "MLflow experiment $MLFLOW_EXPERIMENT is id $id"
  fetch_otel_plugin || { log "hermes_otel not fetched; tracing is off"; return 0; }
  sed -e "s|__MLFLOW_EXPERIMENT_ID__|$id|g" -e "s|__MLFLOW_TOKEN__|$token|g" \
    /config/hermes-otel-config.yaml.template > "$WORK/hermes-otel-config.yaml"
  publish "$WORK/hermes-otel-config.yaml" hermes-otel-config.yaml
  rm -f "$WORK/hermes-otel-config.yaml"
  log "hermes_otel prepared"
}

# ---------------------------------------------------------------------------
# Prepare: everything that does not need the sandbox, before the participant
# creates it.
# ---------------------------------------------------------------------------
prepare() {
  local MODEL_API_KEY API_SERVER_KEY
  MODEL_API_KEY=$(secret_value MODEL_API_KEY)
  API_SERVER_KEY=$(secret_value API_SERVER_KEY)
  if [ -z "$MODEL_API_KEY" ] || [ -z "$API_SERVER_KEY" ]; then
    log "Secret $HERMES_ENV_SECRET in $AGENTOPS_NS is missing, or lacks MODEL_API_KEY or API_SERVER_KEY"
    return 1
  fi

  # Hermes lists tools once, at start-up. Starting it before the gateway has
  # discovered every server leaves it without those tools for good.
  log "waiting for the MCP gateway to list every server's tools"
  if ! HERMES_HOME="$WORK/probe" python3 /config/mcp-token-refresh.py >/dev/null 2>&1; then
    log "could not get an MCP token from $MCP_TOKEN_URL"
    return 1
  fi
  HERMES_HOME="$WORK/probe" python3 /config/wait-for-gateway.py || return 1

  {
    cat /config/hermes-config.yaml
    printf '\nmodel:\n  default: %s\n  provider: custom\n  base_url: %s\n  api_key: %s\n' \
      "$MODEL_DEFAULT" "$MODEL_BASE_URL" "$MODEL_API_KEY"
    printf '\ncustom_providers:\n  - name: %s\n    base_url: %s\n    api_key: %s\n    model: %s\n' \
      "$MODEL_DEFAULT" "$MODEL_BASE_URL" "$MODEL_API_KEY" "$MODEL_DEFAULT"
  } > "$WORK/config.yaml"
  cat > "$WORK/hermes-env.sh" <<EOF
export HERMES_HOME=/sandbox/.hermes
export HERMES_PROFILE=default
export XDG_STATE_HOME=/sandbox/.hermes/state
export MEM0_DB_PATH=/sandbox/.hermes/mem0
export API_SERVER_ENABLED=true
export API_SERVER_HOST=127.0.0.1
export API_SERVER_PORT=${API_PORT}
export API_SERVER_KEY='${API_SERVER_KEY}'
export MCP_SERVER_NAME='${MCP_SERVER_NAME}'
export MCP_CLIENT_ID='${MCP_CLIENT_ID}'
export MCP_USERNAME='${MCP_USERNAME}'
export MCP_PASSWORD='${MCP_PASSWORD}'
export MCP_TOKEN_URL='${MCP_TOKEN_URL}'
export TOKEN_REFRESH_SECONDS='${TOKEN_REFRESH_SECONDS}'
EOF
  publish "$WORK/config.yaml" config.yaml
  publish "$WORK/hermes-env.sh" hermes-env.sh
  rm -f "$WORK/config.yaml" "$WORK/hermes-env.sh"
  publish /config/mcp-token-refresh.py mcp-token-refresh.py
  publish /config/start-hermes.sh start-hermes.sh
  prepare_otel
  publish_policy
  log "prepared $OUT for upload: $(ls "$OUT" | tr '\n' ' ')"
}

# ---------------------------------------------------------------------------
# The console's relay. nginx serves a placeholder until there is a Hermes to
# relay to, so the pod is Ready whether or not the participant has started it.
# ---------------------------------------------------------------------------
write_nginx() {
  if [ -n "$RELAY_HOST" ]; then
    sed -e '/#PLACEHOLDER/d' \
        -e "s|__GATEWAY_HOST__|${GATEWAY_HOST}|g" -e "s|__RELAY_HOST__|${RELAY_HOST}|g" \
      /config/nginx.conf.template > /shared/nginx.conf.tmp
  else
    sed -e '/#BEGIN_RELAY/,/#END_RELAY/d' -e 's|#PLACEHOLDER||' \
      /config/nginx.conf.template > /shared/nginx.conf.tmp
  fi
  mv /shared/nginx.conf.tmp /shared/nginx.conf
}

relay_healthy() {
  [ -n "$RELAY_HOST" ] || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        --cacert /mtls/ca.crt --cert /mtls/tls.crt --key /mtls/tls.key \
        -H "Host: $RELAY_HOST" "$GATEWAY_ENDPOINT/health" 2>/dev/null)" = "200" ]
}

# Adopts the participant's Hermes once they have exposed it (step 4).
adopt() {
  local url
  [ "$(sandbox_phase)" = "Ready" ] || return 1
  url=$(service_url)
  [ -n "$url" ] || return 1
  RELAY_HOST=${url#https://}
  RELAY_HOST=${RELAY_HOST%%[:/]*}
  write_nginx
  log "adopted sandbox $SANDBOX_NAME, relayed as $RELAY_HOST"
}

forget() {
  RELAY_HOST=""
  write_nginx
  log "waiting for the participant to start Hermes in sandbox $SANDBOX_NAME and expose it"
}

# Re-runs the participant's own start script inside the sandbox. Skipped when
# there is nothing to restart: the participant has not uploaded it yet.
restart_hermes() {
  local lock_fd rc=0
  exec {lock_fd}>"$RESTART_LOCK"
  if ! flock -w 60 "$lock_fd"; then
    log "a restart is already running; skipping this trigger"
    exec {lock_fd}>&-
    return 1
  fi
  if [ "$(sandbox_phase)" != "Ready" ] || ! X "test -f $START_SCRIPT" >/dev/null 2>&1; then
    log "no started Hermes in sandbox $SANDBOX_NAME to restart"
    rc=1
  else
    log "restarting Hermes in sandbox $SANDBOX_NAME"
    X "sh $START_SCRIPT" 2>&1 | strip | sed 's/^/    /'
    rc=${PIPESTATUS[0]}
  fi
  flock -u "$lock_fd"
  exec {lock_fd}>&-
  return $rc
}

write_nginx
until prepare; do log "preparation failed; retrying in 30s"; sleep 30; done
connect_cli

if [ "${ROLE_WATCH_ENABLED:-false}" = "true" ]; then
  role_watch_loop &
else
  log "role watch is off (ROLE_WATCH_ENABLED != true)"
fi

adopt || forget
failures=0
while true; do
  sleep "$HEALTH_CHECK_SECONDS"
  # A participant synced a new sandbox policy (the mounted ConfigMap changed).
  # Published only: applying it, and restarting Hermes, is theirs to do.
  if [ "$(policy_hash)" != "$PUBLISHED_POLICY" ]; then
    publish_policy
    log "the sandbox policy changed; published it to $OUT/policy.yaml. Apply it with:"
    log "  openshell policy set --policy $OUT/policy.yaml --wait $SANDBOX_NAME"
    log "  openshell sandbox exec --name $SANDBOX_NAME -- sh $START_SCRIPT"
  fi
  if [ -z "$RELAY_HOST" ]; then
    adopt && failures=0
    continue
  fi
  if relay_healthy; then failures=0; continue; fi
  failures=$((failures + 1))
  log "Hermes did not answer through the relay ($failures/3)"
  if [ "$failures" -ge 3 ]; then
    failures=0
    if [ "$(sandbox_phase)" = "Ready" ] && [ -n "$(service_url)" ]; then
      restart_hermes || true
    else
      forget
    fi
  fi
done
