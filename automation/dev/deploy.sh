#!/usr/bin/env bash
# Build and deploy the development operator console for one participant.
#
#   automation/dev/deploy.sh <username>        # e.g. deploy.sh 7ql4q
#
# This stands up `water-plant-ui-dev` alongside the ArgoCD-managed
# `water-plant-ui`, on its own Route, built from the working tree rather than
# from quay. The live console is owned by the `<user>-platform` Application
# with prune and selfHeal on, so anything changed there by hand is reverted
# within the sync interval — which makes it the wrong place to iterate.
#
# Nothing here carries an `argocd.argoproj.io/tracking-id`. ArgoCD prunes what
# it tracks and leaves everything else alone, so these objects survive a sync.
# The image is built in-cluster and pushed to the internal registry, so no
# registry credentials are involved anywhere.
set -euo pipefail

USER_SLUG="${1:-}"
if [[ -z "$USER_SLUG" ]]; then
  echo "usage: $(basename "$0") <username>   (e.g. 7ql4q)" >&2
  exit 64
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The console source lives in the sibling lab repo, not this one.
UI_DIR="${UI_DIR:-$(cd "$HERE/../../../agentops-rh1-lab/ui" 2>/dev/null && pwd || true)}"
if [[ ! -f "$UI_DIR/Containerfile" ]]; then
  echo "cannot find the console source; set UI_DIR to agentops-rh1-lab/ui" >&2
  exit 66
fi

export USER="$USER_SLUG"
export NS="user-${USER_SLUG}-agentops"
export APPS_DOMAIN="$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')"

echo "==> namespace $NS on $APPS_DOMAIN"
oc get ns "$NS" >/dev/null

# --- build -----------------------------------------------------------------
if ! oc -n "$NS" get bc water-plant-ui-dev >/dev/null 2>&1; then
  echo "==> creating BuildConfig"
  oc -n "$NS" new-build --binary --strategy=docker --name=water-plant-ui-dev >/dev/null
  # `new-build --strategy=docker` looks for a file literally named Dockerfile;
  # this repo's is a Containerfile, and without this the build dies with
  # "open /tmp/build/inputs/Dockerfile: no such file or directory".
  oc -n "$NS" patch bc water-plant-ui-dev --type=json \
    -p='[{"op":"add","path":"/spec/strategy/dockerStrategy/dockerfilePath","value":"Containerfile"}]' >/dev/null
fi

echo "==> building from $UI_DIR"
# --from-dir must be relative. On WSL the `oc` on PATH is the Windows binary,
# which reads an absolute /mnt/c/... path as a literal Windows path and fails
# with "CreateFile C:\mnt\c\...: The system cannot find the path specified".
( cd "$UI_DIR" && oc -n "$NS" start-build water-plant-ui-dev --from-dir=. --follow >/dev/null )

# --- deploy ----------------------------------------------------------------
echo "==> applying manifests"
# envsubst only on our own placeholders: the manifest contains ${...} nowhere
# else, but being explicit keeps a future $(something) in a comment safe.
envsubst '${USER} ${NS} ${APPS_DOMAIN}' < "$HERE/water-plant-ui-dev.yaml" | oc apply -f -

oc -n "$NS" rollout status deploy/water-plant-ui-dev --timeout=180s

echo
echo "console: https://$(oc -n "$NS" get route water-plant-ui-dev -o jsonpath='{.spec.host}')"
