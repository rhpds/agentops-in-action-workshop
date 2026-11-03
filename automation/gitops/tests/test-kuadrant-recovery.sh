#!/usr/bin/env bash
# Offline behavioral checks of the actual Helm-rendered recovery script.
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for chart in bootstrap-infra tests/lb1285-mcp-dev; do
  helm template test "$root/automation/gitops/$chart" > "$tmp/rendered.yaml"
  python3 - "$tmp/rendered.yaml" "$tmp/recover.sh" <<'PY'
import sys, yaml
docs = list(yaml.safe_load_all(open(sys.argv[1])))
job = next(x for x in docs if x and x.get('kind') == 'Job' and
           (x['metadata'].get('name') == 'kuadrant-dependency-recovery' or
            x['metadata'].get('generateName') == 'kuadrant-dependency-recovery-'))
open(sys.argv[2], 'w').write(job['spec']['template']['spec']['containers'][0]['args'][0])
assert job['metadata'].get('generateName') == 'kuadrant-dependency-recovery-'
assert job['metadata']['annotations']['argocd.argoproj.io/hook-delete-policy'] == 'HookSucceeded'
PY
  for scenario in ready transient stuck missing permanent_missing api_error dependency_failure delete_failure rollout_failure; do
    export SCENARIO=$scenario NS=kuadrant-system DEP=authorino-operator KOP=kuadrant-operator
    export SETTLE=120 ATTEMPTS=1 READY_TIMEOUT=600
    set +e
    bash -c '
      SECONDS=0; restarted=0
      sleep() { SECONDS=$((SECONDS + $1)); }
      oc() {
        case "$1" in
          wait) [[ $SCENARIO != dependency_failure ]]; return ;;
          delete)
            echo DELETE >&2
            [[ $SCENARIO != delete_failure ]] || return 1
            restarted=1; return 0 ;;
          rollout) [[ $SCENARIO != rollout_failure ]]; return ;;
          get)
            [[ $SCENARIO != api_error ]] || return 1
            local status=False reason=Reconciling
            if [[ $SCENARIO == ready ]] || { [[ $SCENARIO == transient ]] && (( SECONDS >= 300 )); } || { (( restarted )) && [[ $SCENARIO != permanent_missing ]]; }; then
              status=True; reason=Ready
            elif [[ $SCENARIO == missing || $SCENARIO == permanent_missing || $SCENARIO == delete_failure || $SCENARIO == rollout_failure ]]; then
              reason=MissingDependency
            fi
            case "${*: -1}" in
              *.status\}) printf %s "$status" ;;
              *.reason\}) printf %s "$reason" ;;
              *.message\}) printf %s "fixture condition" ;;
            esac ;;
          *) return 1 ;;
        esac
      }
      source "$1"
    ' bash "$tmp/recover.sh" > "$tmp/output" 2>&1
    rc=$?
    set -e
    case "$scenario" in
      ready|transient|missing) expected=0 ;;
      *) expected=1 ;;
    esac
    if [[ $rc != "$expected" ]]; then
      cat "$tmp/output"
      echo "FAIL $chart $scenario: expected $expected, got $rc" >&2
      exit 1
    fi
    case "$scenario" in
      missing|permanent_missing|delete_failure|rollout_failure) [[ $(grep -c DELETE "$tmp/output") == 1 ]] ;;
      *) if grep -q DELETE "$tmp/output"; then echo "unexpected restart: $scenario"; exit 1; fi ;;
    esac
    echo "PASS $chart $scenario"
  done
done
