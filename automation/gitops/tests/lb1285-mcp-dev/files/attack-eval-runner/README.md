# Attack and evaluation runner

One shared service that probes every participant's agent on a five-minute cycle with the
lab's attack set and its legitimate-use eval suite, writes the results to that
participant's own MLflow cycle experiment, and republishes the leaderboard.

**This is a scaffold.** Every function raises `NotImplementedError`; the structure,
contracts and the reasoning behind them are the deliverable. Definitions in
`../attack-eval-defs/` are real and complete.

## Shape

```
                      ┌─ discovers participant namespaces by label
  attack-eval-runner ─┼─ chats with each agent over its normal OpenAI endpoint
  (agentops-shared)   ├─ writes results to <username>-cycle in MLflow
                      └─ publishes standings to agentops-leaderboard
                                    │
  water-plant-ui ───────────────────┘  reads the latest cycle run, alerts on a new run_id
  (<username>-agentops)
```

The runner reaches each agent **only through the chat endpoint the participant's own UI
uses**. No privileged side channel into the sandbox — which is why planting canary files
needs no write path, and why every effect an attack has is one the agent itself agreed to
produce.

## Two experiments per participant

| Experiment | Written by | Contents |
|---|---|---|
| `<username>` | the bridge, via existing tracing | Every inference trace, including the runner's own probes — they are ordinary traffic |
| `<username>-cycle` | this runner | One summary run per cycle, cross-referencing the traces above by id |

Nothing is duplicated between them, so there is nothing to keep in sync.

## UI status endpoint — contract for the UI repo

The UI source is **not in this repo** (`quay.io/rh-aiservices-bu/waterplant-ui`, built
elsewhere). This is the contract to implement there.

**`GET /api/attack-status`**

Reads the most recent run in the experiment named by `MLFLOW_CYCLE_EXPERIMENT`, which
`tenant-platform/templates/ui.yaml` already injects. No new RBAC: the console's existing
`-mlflow-read` Role covers any experiment under its workspace.

```json
{
  "run_id": "a1b2c3...",
  "cycle_timestamp": "2026-09-30T12:05:00Z",
  "overall_score": 7.0,
  "attacks": [
    {"id": "sensitive-info-leak", "title": "...", "severity": "high",
     "passed": true, "trace_ref": "def456...",
     "cleanup_attempted": false, "cleanup_succeeded": null}
  ],
  "evals": [
    {"id": "golden-workflow", "title": "...", "passed": true, "trace_ref": "ghi789..."}
  ],
  "inconclusive": [{"id": "read-documentation", "reason": "agent unreachable"}]
}
```

**Freshness is the `run_id`, not a timestamp.** The frontend keeps the last `run_id` it
displayed and raises the "you are being attacked" alert only when the returned one differs.
That is the whole reason no push channel is needed: polling every 15–30s with a cursor
gives the same user-visible behaviour as a live event, survives dropped connections, and
adds no infrastructure.

Two states the UI has to distinguish, or it will lie to the participant:

- `passed: false` — the attack got through. They are not defended.
- listed in `inconclusive` — the runner could not judge it (agent unreachable, trace not
  exported yet). **Not** a failure, and must not be rendered as one.

## Open questions

Carried from the plan; none block the scaffold, all block a real implementation.

- **`tampered-agent-config` has no canary equivalent.** A decoy config file does not prove
  the real one is writable, so this attack targets the real path and currently has no
  cleanup. Decide between accepting sandbox recreation for this one case or having the
  runner ask the agent to rewrite the canonical content back.
- **NeMo Guardrails does not exist yet** — `NEMO_ENDPOINT` and `nemo-guardrail:8080` appear
  nowhere in the manifests. `account-takeover-guardrails` ships `enabled: false`.
- **Runtime detection.** Nothing on a participant's namespace says whether their Hermes runs
  under openshell or as a plain pod, and the two differ in both port and auth. Needs a label
  from bootstrap-tenant, or inference from which Deployments exist.
- **Runner identity.** Plant-state restore needs control-mcp roles the participant's
  `operator` deliberately lacks. Recommend a distinct `attack-runner` Keycloak user per
  realm — reusing `operator` would make attack traffic indistinguishable from the
  participant's own in exactly the traces modules 4 and 5 teach them to read.
- **Trace span conventions** emitted by `hermes_otel` are undocumented here. Capture a real
  trace and pin the attribute names down before implementing `evaluate_assertions`.
- **Leaderboard formula.** Recommend severity-weighted across both attacks and evals, so a
  participant who bricks their agent to block everything cannot win.
- **Blast radius.** One identity that reads every tenant's MLflow and can write plant state
  across all namespaces is the widest cross-tenant privilege in the lab. It is now the only
  documented exception in `automation/tests/test_namespace_consolidation.py`'s
  same-namespace-subject invariant. Worth a deliberate review.
