#!/bin/bash
# ttyd runs this once per browser connection, with that connection's pty on
# stdin/stdout.
export PATH=/tools:$PATH
export XDG_CONFIG_HOME=/tmp/openshell-config
# One Tokio worker deadlocks the TUI before its first frame.
export TOKIO_WORKER_THREADS=4

# The CLI has no flag for certificate paths; it reads them from here.
mkdir -p "$XDG_CONFIG_HOME/openshell/gateways/openshell-gw/mtls"
cp /mtls/ca.crt /mtls/tls.crt /mtls/tls.key \
   "$XDG_CONFIG_HOME/openshell/gateways/openshell-gw/mtls/"

if ! openshell gateway add "$GATEWAY_URL" --local --name openshell-gw >/tmp/gw.log 2>&1; then
  cat /tmp/gw.log
fi
openshell gateway select openshell-gw >/dev/null 2>&1

# [q] quits the TUI, and the tab would be left on a dead session.
while true; do
  openshell term
  printf '\n  OpenShell TUI exited. Restarting in 2s...\n'
  sleep 2
done
