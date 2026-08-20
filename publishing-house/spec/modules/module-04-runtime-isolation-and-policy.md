# Module 4 — Apply runtime isolation and policy controls

### Brief Overview

This is the main hands-on section and the heart of the lab. Participants apply five layers of control to the agent without rebuilding it, redeploying it, or changing a single line of its code or prompt. They first confirm the hard isolation boundary that Agent Sandbox and Kata already provide, then use OpenShell to restrict filesystem paths, deny specific process execution, apply per-binary outbound network rules, and move the over-broad synthetic credential into governed storage. After each change, the corresponding attack from module 3 is re-run and now receives an infrastructure-level denial while the legitimate workflow still completes. The module ends by making the division of responsibility explicit: Kata is the isolation boundary, OpenShell is the fine-grained execution policy, and OpenShift controls are platform defense in depth.

### Audience and Time

**Personas:** Same as module 1. This is the module where OpenShift AI administrators and platform architects will go deepest; architects focused on positioning should prioritize sections 1 and 6.

**Module prerequisites:** Module 3 — each exercise here re-runs an attack established there, so the failures must have been observed first.

**Duration:** 30 minutes. The longest module, containing five separate policy exercises. Roughly 5–6 minutes each plus a closing synthesis.

### Learning Objectives

- Inspect the Agent Sandbox and Kata isolation boundary backing the agent's execution environment
- Configure OpenShell filesystem policy to allow a working path and deny protected and credential locations
- Configure OpenShell process execution policy to permit the legitimate workflow while denying an attack utility
- Configure per-binary outbound network policy in OpenShell alongside coarse NetworkPolicy egress control
- Migrate an exposed credential into OpenShell credential governance backed by Vault or Kubernetes Secrets
- Verify that each control blocks its corresponding module 3 attack without breaking the normal workflow
- Differentiate the enforcement responsibilities of the isolation boundary, the execution policy, and platform-level controls

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | 4A — Inspect the hard sandbox boundary | 5 min |
| 2 | 4B — Restrict filesystem activity with OpenShell | 5 min |
| 3 | 4C — Restrict process execution | 5 min |
| 4 | 4D — Restrict network access at two layers | 6 min |
| 5 | 4E — Remove the exposed credential | 6 min |
| 6 | Section synthesis — three distinct layers | 3 min |

### Detailed Steps

1. Inspect the existing `Sandbox` and `SandboxClaim` backing the agent's execution environment.
2. Confirm that the execution environment is backed by Kata and is not sharing the OpenShift node kernel.
3. Note the first defense layer: Kata protects the platform from the workload, and Agent Sandbox manages the lifecycle of that isolated environment.
4. Review the `SandboxTemplate` and warm pool arrangement that pre-created this environment, so that sandbox provisioning consumes no lab time.
5. Open the Governed Execution Environment admin UI and locate the current, deliberately broad, OpenShell filesystem policy.
6. Change the filesystem policy to allow `/workspace/**` and deny protected system locations and credential locations.
7. Re-run the module 3 filesystem attack unchanged.
8. Confirm that the identical agent code now receives an infrastructure-level denial, and that nothing in the prompt or the agent source changed.
9. Locate the denial in the MLflow trace.
10. Open the OpenShell execution policy and identify which processes the legitimate workflow actually requires.
11. Modify the policy to permit those processes while denying the utility that was used in the module 3 attack.
12. Re-run the attack and confirm the unwanted subprocess is blocked.
13. Re-run a normal task and confirm the agent still completes it — no rebuild, no redeploy.
14. Review the coarse OpenShift NetworkPolicy that restricts namespace and workload egress, and note what it can and cannot express.
15. Configure OpenShell per-binary network policy — for example, permit `python` to reach the approved service on port 443 while denying `python` to arbitrary destinations.
16. Re-run the module 3 outbound network attack. Confirm the legitimate endpoint still succeeds and the unauthorized endpoint now fails.
17. Compare the two layers: NetworkPolicy is coarse namespace-level control, OpenShell expresses agent-specific and per-executable intent.
18. Locate the over-broad synthetic credential that the baseline environment exposes directly to the agent.
19. Migrate that credential into the OpenShell credential-governance mechanism, backed by either Vault or Kubernetes Secrets.
20. Confirm the agent now receives a placeholder or reference rather than direct possession of the real credential.
21. Re-run the legitimate request that requires the credential and confirm it still succeeds, because OpenShell brokers access.
22. Attempt to print or exfiltrate the credential and confirm the real value is no longer revealed.
23. Summarize the three distinct layers now in place and state which control each failure from module 3 was actually fixed by.

### Key Takeaways

- Runtime policy can be changed without rebuilding, redeploying, or reprompting the agent — this is the single most important demonstration in the lab
- Agent Sandbox and Kata are the isolation boundary; they protect the platform from the workload but do not express fine-grained intent
- OpenShell is the fine-grained execution policy layer covering filesystem, process, per-binary network, and credential governance
- OpenShift NetworkPolicy and cluster policy engines are defense in depth, not the primary agent control
- Credential governance means the agent holds a reference, not a secret, so exfiltration returns nothing useful
- Each control must be verified twice: the attack is blocked, and the legitimate workflow still completes

### Infrastructure Notes

Requires OpenShell with its Operator and the Governed Execution Environment admin UI available to participants, so that policy changes are deliberate administrative actions rather than hand-edited YAML alone. Requires `SandboxTemplate` plus a warm pool sized to peak concurrency for immediate environment availability. Requires either Vault or Kubernetes Secrets as the credential backing store. Requires the coarse NetworkPolicy, the approved internal service, and the unauthorized test endpoint from module 3 to remain in place. The reset action is most likely to be needed during this module — participants misconfiguring policy should be able to recover a working environment in under a minute rather than repairing it by hand.
