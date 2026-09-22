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
APPLIED_POLICY=""

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

# The policy is given at creation, because filesystem rules are fixed then: a
# live sandbox accepts new paths but refuses to drop any.
create_sandbox() {
  log "creating sandbox $SANDBOX_NAME from $IMAGE_REF with $1"
  # `-- echo ready` prints "No such file or directory" after the sandbox is up;
  # harmless, and the phase check below is what counts.
  openshell sandbox create --name "$SANDBOX_NAME" --from "$IMAGE_REF" --policy "$1" \
    --cpu "$SANDBOX_CPU" --memory "$SANDBOX_MEMORY" --no-tty -- echo ready 2>&1 | strip | tail -3
}

wait_ready() {
  local i phase
  log "waiting for sandbox $SANDBOX_NAME to be Ready"
  for i in $(seq 1 60); do
    phase=$(sandbox_phase)
    [ "$phase" = "Ready" ] && return 0
    sleep 5
  done
  log "sandbox not Ready after 300s (phase: ${phase:-none})"
  return 1
}

# Applies the current policy. Network changes load into the running sandbox.
# A policy that removes a filesystem path cannot be applied live, so the
# sandbox is recreated with it; Hermes' files are rewritten afterwards anyway.
apply_policy() {
  local pf out i
  pf=$(policy_file)
  log "applying the sandbox policy from $pf (sha256 $(policy_hash))"
  if out=$(openshell policy set --policy "$pf" --wait "$SANDBOX_NAME" 2>&1); then
    APPLIED_POLICY=$(policy_hash)
    return 0
  fi
  if printf '%s' "$out" | grep -q "cannot be removed on a live sandbox"; then
    log "the policy removes filesystem paths, which a live sandbox cannot drop; recreating $SANDBOX_NAME"
    openshell sandbox delete "$SANDBOX_NAME" 2>&1 | strip | tail -1
    for i in $(seq 1 60); do [ -z "$(sandbox_phase)" ] && break; sleep 5; done
    create_sandbox "$pf"
    wait_ready || return 1
    APPLIED_POLICY=$(policy_hash)
    return 0
  fi
  # Most often a policy participants edited into something OpenShell refuses.
  log "policy rejected: $(printf '%s' "$out" | strip | grep -vE '^\s*$' | tr -s ' ' | tr -d '│×' | tr '\n' ' ' | cut -c1-400)"
  return 1
}

# put_file <local path> <sandbox path> <mode>
put_file() {
  local b64
  b64=$(base64 -w0 "$1")
  X "mkdir -p \"\$(dirname '$2')\" && printf '%s' '$b64' | base64 -d > '$2' && chmod $3 '$2'" >/dev/null
}

# put_blob <local path> <sandbox path>
# put_file in chunks. The plugin tarball's base64 is far longer than one exec
# command line holds.
put_blob() {
  local b64 i n
  b64=$(base64 -w0 "$1")
  n=${#b64}
  X "rm -f '$2.b64'" >/dev/null || return 1
  i=0
  while [ "$i" -lt "$n" ]; do
    X "printf '%s' '${b64:$i:16000}' >> '$2.b64'" >/dev/null || return 1
    i=$((i + 16000))
  done
  X "base64 -d '$2.b64' > '$2' && rm -f '$2.b64'" >/dev/null
}

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

# hermes_otel is not in the sandbox image. It is fetched here, in the bridge,
# where no sandbox policy applies, checked against the pinned digest and pushed
# in. So a participant who tightens their policy stops the traces leaving, not
# the install.
install_otel_plugin() {
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
  tar -czf "$dir/pkg.tar.gz" -C "$dir/pkg" .
  put_blob "$dir/pkg.tar.gz" /tmp/hermes-otel.tar.gz || return 1
  X "mkdir -p /sandbox/.hermes/plugins/hermes_otel && tar -xzf /tmp/hermes-otel.tar.gz -C /sandbox/.hermes/plugins/hermes_otel && rm -f /tmp/hermes-otel.tar.gz" >/dev/null || return 1
  rm -rf "$dir"
}

# configure_otel <token> <experiment id>
configure_otel() {
  local rc
  sed -e "s|__MLFLOW_EXPERIMENT_ID__|$2|g" -e "s|__MLFLOW_TOKEN__|$1|g" \
    /config/hermes-otel-config.yaml.template > "$WORK/hermes-otel-config.yaml"
  put_file "$WORK/hermes-otel-config.yaml" /sandbox/.hermes/plugins/hermes_otel/config.yaml 600
  rc=$?
  rm -f "$WORK/hermes-otel-config.yaml"
  return $rc
}

# Tracing is best-effort: a participant whose MLflow is unreachable should still
# get a working agent, just an unobservable one. Says which it was.
setup_otel() {
  otel_enabled || return 0
  local token id
  token=$(mlflow_token)
  if [ -z "$token" ]; then log "could not mint an MLflow token; tracing is off"; return 0; fi
  id=$(mlflow_experiment_id "$token")
  if [ -z "$id" ]; then log "no MLflow experiment $MLFLOW_EXPERIMENT; tracing is off"; return 0; fi
  log "MLflow experiment $MLFLOW_EXPERIMENT is id $id"
  install_otel_plugin || { log "hermes_otel not installed; tracing is off"; return 0; }
  configure_otel "$token" "$id" || { log "hermes_otel not configured; tracing is off"; return 0; }
  # Where the spans actually go, which is the relay rather than
  # MLFLOW_TRACKING_URI: the bridge talks to MLflow directly, the sandbox
  # cannot. Read it back from the template so the two can never disagree.
  local endpoint
  endpoint=$(sed -n 's/^[[:space:]]*endpoint:[[:space:]]*//p' /config/hermes-otel-config.yaml.template | head -1 | tr -d '"')
  log "hermes_otel installed, posting spans to ${endpoint:-the configured endpoint}"
}

relay_healthy() {
  [ -n "$RELAY_HOST" ] || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
        --cacert /mtls/ca.crt --cert /mtls/tls.crt --key /mtls/tls.key \
        -H "Host: $RELAY_HOST" "$GATEWAY_ENDPOINT/health" 2>/dev/null)" = "200" ]
}

provision() {
  local i out url
  MODEL_API_KEY=$(secret_value MODEL_API_KEY)
  API_SERVER_KEY=$(secret_value API_SERVER_KEY)
  if [ -z "$MODEL_API_KEY" ] || [ -z "$API_SERVER_KEY" ]; then
    log "Secret $HERMES_ENV_SECRET in $AGENTOPS_NS is missing, or lacks MODEL_API_KEY or API_SERVER_KEY"
    return 1
  fi

  if [ -z "$(sandbox_phase)" ]; then
    create_sandbox "$(policy_file)"
  fi
  wait_ready || return 1
  apply_policy || return 1

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

  # Before Hermes starts: it reads its plugins at start-up, as it does its
  # tools. Hermes' config enables hermes_otel, so the plugin and its config
  # have to be in place by then.
  setup_otel

  # Stop whatever an earlier bridge started. The bracketed patterns keep the
  # command from matching its own command line.
  log "restarting Hermes and its token refresher inside the sandbox"
  X 'for p in $(ps -eo pid,args | awk "/[h]ermes gateway run|mcp-token-refres[h]/ {print \$1}"); do kill "$p" 2>/dev/null; done; sleep 2; true' >/dev/null 2>&1
  if ! X ". /sandbox/.hermes-env.sh && python3 /sandbox/mcp-token-refresh.py" >/dev/null 2>&1; then
    log "token fetch inside the sandbox failed; the sandbox policy must let python3 reach Keycloak"
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
  # A participant synced a new sandbox policy (the mounted ConfigMap changed).
  if [ "$(policy_hash)" != "$APPLIED_POLICY" ]; then
    log "the sandbox policy changed; applying it and restarting Hermes"
    until provision; do log "set-up failed; retrying in 30s"; sleep 30; done
    failures=0
    continue
  fi
  if relay_healthy; then failures=0; continue; fi
  failures=$((failures + 1))
  log "Hermes did not answer through the relay ($failures/3)"
  if [ "$failures" -ge 3 ]; then
    log "setting the sandbox up again (it may have restarted)"
    until provision; do log "set-up failed; retrying in 30s"; sleep 30; done
    failures=0
  fi
done
