#!/usr/bin/env bash
# Sets up and supervises one participant's Hermes inside their OpenShell
# sandbox. See templates/bridge.yaml for why this is a supervisor.
#
# Never runs with -x: the model key and Hermes' server key pass through here.
set -uo pipefail
export PATH="/tools:$PATH"
export HOME=/tmp
export XDG_CONFIG_HOME=/tmp/.config
umask 077

WORK=/tmp/work
mkdir -p "$WORK/probe/mcp-tokens"
GATEWAY_ENDPOINT="https://${GATEWAY_HOST}:8080"
RELAY_HOST=""

log()   { echo "[$(date -u +%H:%M:%S)] $*"; }
strip() { sed 's/\x1b\[[0-9;]*m//g'; }
# Runs inside the sandbox's policy-enforced network namespace, as the sandbox
# user. Plain `oc exec` would land outside it, where the relay cannot reach.
X()     { openshell sandbox exec --name "$SANDBOX_NAME" -- /bin/sh -c "$1"; }

secret_value() {
  oc get secret "$HERMES_ENV_SECRET" -n "$AGENTOPS_NS" -o "jsonpath={.data.$1}" 2>/dev/null | base64 -d
}

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

# put_file <local path> <sandbox path> <mode>
put_file() {
  local b64
  b64=$(base64 -w0 "$1")
  X "mkdir -p \"\$(dirname '$2')\" && printf '%s' '$b64' | base64 -d > '$2' && chmod $3 '$2'" >/dev/null
}

relay_healthy() {
  [ -n "$RELAY_HOST" ] || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        --cacert /mtls/ca.crt --cert /mtls/tls.crt --key /mtls/tls.key \
        -H "Host: $RELAY_HOST" "$GATEWAY_ENDPOINT/health" 2>/dev/null)" = "200" ]
}

provision() {
  local i phase out url
  MODEL_API_KEY=$(secret_value MODEL_API_KEY)
  API_SERVER_KEY=$(secret_value API_SERVER_KEY)
  if [ -z "$MODEL_API_KEY" ] || [ -z "$API_SERVER_KEY" ]; then
    log "Secret $HERMES_ENV_SECRET in $AGENTOPS_NS is missing, or lacks MODEL_API_KEY or API_SERVER_KEY"
    return 1
  fi

  if [ -z "$(sandbox_phase)" ]; then
    log "creating sandbox $SANDBOX_NAME from $IMAGE_REF"
    openshell sandbox create --name "$SANDBOX_NAME" --from "$IMAGE_REF" \
      --cpu "$SANDBOX_CPU" --memory "$SANDBOX_MEMORY" --no-tty -- echo ready 2>&1 | strip | tail -3
  fi
  log "waiting for sandbox $SANDBOX_NAME to be Ready"
  for i in $(seq 1 60); do
    phase=$(sandbox_phase)
    [ "$phase" = "Ready" ] && break
    if [ "$i" -eq 60 ]; then log "sandbox not Ready after 300s (phase: ${phase:-none})"; return 1; fi
    sleep 5
  done

  log "applying the sandbox policy"
  if ! out=$(openshell policy set --policy /config/policy.yaml --wait "$SANDBOX_NAME" 2>&1); then
    log "policy set failed: $(printf '%s' "$out" | strip | tail -3)"
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

  log "writing Hermes' files into the sandbox"
  {
    cat /config/hermes-config.yaml
    printf '\nmodel:\n  default: %s\n  provider: custom\n  base_url: %s\n  api_key: %s\n' \
      "$MODEL_DEFAULT" "$MODEL_BASE_URL" "$MODEL_API_KEY"
    printf '\ncustom_providers:\n  - name: %s\n    base_url: %s\n    api_key: %s\n    model: %s\n' \
      "$MODEL_DEFAULT" "$MODEL_BASE_URL" "$MODEL_API_KEY" "$MODEL_DEFAULT"
  } > "$WORK/config.yaml"
  cat > "$WORK/env.sh" <<EOF
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
EOF
  local ok=1
  put_file "$WORK/config.yaml" /sandbox/.hermes/config.yaml 600 || ok=0
  put_file "$WORK/env.sh" /sandbox/.hermes-env.sh 600 || ok=0
  put_file /config/mcp-token-refresh.py /sandbox/mcp-token-refresh.py 700 || ok=0
  rm -f "$WORK/config.yaml" "$WORK/env.sh"
  if [ "$ok" -ne 1 ]; then log "could not write files into the sandbox"; return 1; fi

  # Stop whatever an earlier bridge started. The bracketed patterns keep the
  # command from matching its own command line.
  log "restarting Hermes and its token refresher inside the sandbox"
  X 'for p in $(ps -eo pid,args | awk "/[h]ermes gateway run|mcp-token-refres[h]/ {print \$1}"); do kill "$p" 2>/dev/null; done; sleep 2; true' >/dev/null 2>&1
  if ! X ". /sandbox/.hermes-env.sh && python3 /sandbox/mcp-token-refresh.py" >/dev/null 2>&1; then
    log "token fetch inside the sandbox failed; check the policy's keycloak_token rule"
    return 1
  fi
  # setsid and a subshell reparent both to the supervisor, so exec returns.
  X ". /sandbox/.hermes-env.sh && (setsid sh -c 'python3 /sandbox/mcp-token-refresh.py --loop ${TOKEN_REFRESH_SECONDS} < /dev/null >> /sandbox/mcp-token-refresh.log 2>&1' < /dev/null > /dev/null 2>&1 &); true" >/dev/null 2>&1
  X ". /sandbox/.hermes-env.sh && (setsid sh -c 'hermes gateway run < /dev/null >> /sandbox/hermes-gateway.log 2>&1' < /dev/null > /dev/null 2>&1 &); true" >/dev/null 2>&1

  log "waiting for Hermes' API server"
  for i in $(seq 1 36); do
    X "curl -sf --max-time 5 http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
    if [ "$i" -eq 36 ]; then
      log "Hermes did not answer /health after 180s; last lines of its log:"
      X "tail -20 /sandbox/hermes-gateway.log" 2>&1 | sed 's/^/    /'
      return 1
    fi
    sleep 5
  done

  log "exposing Hermes through the gateway's relay"
  openshell service delete "$SANDBOX_NAME" openai >/dev/null 2>&1 || true
  out=$(openshell service expose "$SANDBOX_NAME" "$API_PORT" openai 2>&1 | strip)
  url=$(printf '%s\n' "$out" | awk '/URL:/ {print $2}')
  if [ -z "$url" ]; then log "service expose returned no URL: $out"; return 1; fi
  RELAY_HOST=${url#https://}
  RELAY_HOST=${RELAY_HOST%%[:/]*}

  sed -e "s|__GATEWAY_HOST__|${GATEWAY_HOST}|g" -e "s|__RELAY_HOST__|${RELAY_HOST}|g" \
    /config/nginx.conf.template > /shared/nginx.conf.tmp
  mv /shared/nginx.conf.tmp /shared/nginx.conf

  if ! relay_healthy; then log "the relay did not answer /health for $RELAY_HOST"; return 1; fi
  log "Hermes is up in sandbox $SANDBOX_NAME, relayed as $RELAY_HOST"
}

connect_cli
until provision; do log "set-up failed; retrying in 30s"; sleep 30; done

failures=0
while true; do
  sleep "$HEALTH_CHECK_SECONDS"
  if relay_healthy; then failures=0; continue; fi
  failures=$((failures + 1))
  log "Hermes did not answer through the relay ($failures/3)"
  if [ "$failures" -ge 3 ]; then
    log "setting the sandbox up again (it may have restarted)"
    until provision; do log "set-up failed; retrying in 30s"; sleep 30; done
    failures=0
  fi
done
