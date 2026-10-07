#!/bin/sh
# Starts, or restarts, Hermes inside the OpenShell sandbox.
#
# Uploaded with the rest of /hermes by the participant (a tar stream through
# `openshell sandbox exec`, unpacked at /sandbox/setup) and run with
#   openshell sandbox exec --name hermes -- sh /sandbox/setup/start-hermes.sh
# The bridge runs the same script when the operator's Keycloak roles change.
# Idempotent: it reinstalls the uploaded files and replaces any running Hermes.
#
# Runs as the sandbox user, inside the sandbox's policy, so everything Hermes
# reaches — the model, Keycloak, MLflow — must be allowed by that policy.
set -u
SETUP=$(cd "$(dirname "$0")" && pwd)
. "$SETUP/hermes-env.sh"

# Install what was uploaded. Overwritten every run, so a re-upload of a fresh
# /hermes always takes effect on the next start.
mkdir -p "$HERMES_HOME"
cp "$SETUP/config.yaml" "$HERMES_HOME/config.yaml"
chmod 600 "$HERMES_HOME/config.yaml" "$SETUP/config.yaml" "$SETUP/hermes-env.sh"
if [ -f "$SETUP/hermes_otel.tar.gz" ] && [ -f "$SETUP/hermes-otel-config.yaml" ]; then
  rm -rf "$HERMES_HOME/plugins/hermes_otel"
  mkdir -p "$HERMES_HOME/plugins/hermes_otel"
  tar -xzf "$SETUP/hermes_otel.tar.gz" -C "$HERMES_HOME/plugins/hermes_otel"
  cp "$SETUP/hermes-otel-config.yaml" "$HERMES_HOME/plugins/hermes_otel/config.yaml"
  chmod 600 "$HERMES_HOME/plugins/hermes_otel/config.yaml" "$SETUP/hermes-otel-config.yaml"
fi

# Stop whatever ran before. The bracketed patterns keep the command from
# matching its own command line.
for p in $(ps -eo pid,args | awk '/[h]ermes gateway run|mcp-token-refres[h]/ {print $1}'); do
  kill "$p" 2>/dev/null
done
sleep 2

# A fresh token before Hermes' first MCP handshake: it carries the operator's
# current roles, which is why a role change needs this restart at all.
if ! python3 "$SETUP/mcp-token-refresh.py" >/dev/null 2>&1; then
  echo "could not fetch an MCP token: the sandbox policy must let python3 reach Keycloak ($MCP_TOKEN_URL)" >&2
  exit 1
fi

# setsid and a subshell detach both from this exec, so it returns.
(setsid sh -c "python3 '$SETUP/mcp-token-refresh.py' --loop $TOKEN_REFRESH_SECONDS < /dev/null >> /sandbox/mcp-token-refresh.log 2>&1" < /dev/null > /dev/null 2>&1 &)
(setsid sh -c "hermes gateway run < /dev/null >> /sandbox/hermes-gateway.log 2>&1" < /dev/null > /dev/null 2>&1 &)

i=0
while [ "$i" -lt 36 ]; do
  if curl -sf --max-time 5 "http://127.0.0.1:${API_SERVER_PORT}/health" >/dev/null 2>&1; then
    echo "Hermes is up on 127.0.0.1:${API_SERVER_PORT}"
    exit 0
  fi
  i=$((i + 1))
  sleep 5
done
echo "Hermes did not answer /health after 180s; last lines of /sandbox/hermes-gateway.log:" >&2
tail -20 /sandbox/hermes-gateway.log >&2
exit 1
