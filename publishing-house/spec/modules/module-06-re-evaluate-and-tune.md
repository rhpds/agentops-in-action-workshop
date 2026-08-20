# Module 6 — Re-evaluate and tune the agent

### Brief Overview

Participants re-run the exact evaluation suite from module 2 and place the hardened scorecard beside the baseline. The comparison — not the absolute numbers — is the point: unauthorized tool use, unauthorized network access, protected file access, and credential disclosure all move from unblocked to blocked, while normal task completion stays high. The module then deliberately breaks something. An over-restrictive network allowlist blocks the knowledge MCP server, one legitimate evaluation fails, and participants must diagnose it from the trace, correct the OpenShell policy, and re-run to green. That loop is the actual AgentOps practice: observe, evaluate, change policy, evaluate again — not simply "turn on security."

### Audience and Time

**Personas:** Same as module 1. The tuning exercise in sections 3 and 4 is the part every persona should complete, even if the earlier comparison is read quickly.

**Module prerequisites:** Module 2 for the saved baseline scorecard, and modules 4 and 5 for the controls being measured.

**Duration:** 15 minutes. Roughly half comparison and half diagnosis and correction.

### Learning Objectives

- Execute the same functional, security, and red-team evaluations used to establish the baseline
- Compare baseline and hardened scorecards to quantify the effect of the applied controls
- Identify policies that are too permissive or too restrictive from evaluation results
- Diagnose a failing legitimate evaluation using its MLflow trace
- Tune an OpenShell policy to restore required functionality without reintroducing the original risk
- Verify the resulting behavior in traces and scorecards

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Re-run the evaluation suite and Garak profile | 4 min |
| 2 | Compare baseline against hardened scorecards | 4 min |
| 3 | Diagnose the over-restrictive policy | 4 min |
| 4 | Tune, re-run, and confirm | 3 min |

### Detailed Steps

1. Re-run exactly the same EvalHub suite used in module 2 — no test changes, so the comparison is valid.
2. Re-run the Garak adversarial profile from module 3.
3. Save the result as the **Hardened scorecard**.
4. Place the hardened scorecard beside the baseline scorecard and compare each measure: normal task completion, unauthorized tool blocked, unauthorized network blocked, protected file access blocked, credential disclosure prevented, and adversarial-test pass rate.
5. Note that normal task completion may drop slightly while every security measure moves from unblocked to blocked — and that the exact values matter far less than the direction of the comparison.
6. Identify which specific control from module 4 or module 5 is responsible for each improved measure.
7. Examine the failing legitimate evaluation. The network allowlist configured earlier is over-restrictive and is blocking the knowledge MCP server.
8. Open the MLflow trace for the failing evaluation and locate the denial.
9. Confirm the denial is a policy decision rather than a model failure or a tool error — this is the model-level versus platform-level distinction from module 3, applied in reverse.
10. Adjust the OpenShell network policy to permit the knowledge MCP server, without re-opening access to the unauthorized test endpoint.
11. Re-run the evaluation suite.
12. Confirm the legitimate evaluation now passes and that no security assertion regressed.
13. Review the final trace and scorecard together to confirm the resulting behavior is both functional and contained.

### Key Takeaways

- Security controls must be measured against a baseline or their effect is an assertion rather than a result
- More restriction is not automatically better — an over-restrictive policy is a production incident, not a safety win
- The trace is what makes an over-restrictive policy diagnosable, by showing a denial rather than an unexplained failure
- The real AgentOps loop is observe, evaluate, change policy, evaluate again — and it is continuous, not a one-time hardening pass
- Continuous evaluation is what detects regressions when policies, models, or tools change later

### Infrastructure Notes

Requires the EvalHub suite to be re-runnable unchanged with results comparable side by side against the module 2 baseline, and the Garak profile re-runnable. Requires one deliberately over-restrictive policy condition — the network allowlist blocking the knowledge MCP server — to be reachable as a natural consequence of the module 4 network exercise, and the corresponding denial to be clearly visible in the MLflow trace.
