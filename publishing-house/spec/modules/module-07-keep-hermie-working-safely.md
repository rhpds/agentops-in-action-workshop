# Module 7 — Keep Hermie Working Safely

### Brief Overview

The closing module consolidates the lab into an operating loop. Participants recap what each layer contributed, where each layer has limits, and how to continue using traces and evaluations after the workshop. The module intentionally keeps the remaining gaps visible, including report deletion semantics, checks on retrieved content and responses, and guardrail availability decisions.

### Audience and Time

**Personas:** Same as module 1, especially architects and technical sales specialists who need to retell the end-to-end AgentOps story.

**Module prerequisites:** Modules 1 through 6.

**Duration:** 5 minutes.

### Learning Objectives

- Summarize the controls applied to keep Hermie useful and safer
- Differentiate responsibilities across OpenShell, Keycloak/MCP Gateway, documentation path policy, NeMo Guardrails, traces, and evaluations
- Explain the AgentOps loop: observe, make a change, take action, evaluate, continue
- Identify remaining gaps and next operational decisions

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | What you achieved | 2 min |
| 2 | Keep the AgentOps loop going | 2 min |
| 3 | Remaining gaps and production responsibility | 1 min |

### Detailed Steps

1. Review the starting state: Hermie could inspect pumps, take actions, and write reports, but had excessive access that could be misused.
2. Recap the harms explored: excessive plant access, accidental report deletion, compromised documentation, poisoned skill instructions, unnecessary personal details, and off-topic requests.
3. Map each control layer to what it contributed: OpenShell sandbox and policies, Keycloak and MCP Gateway, scoped documentation access, NeMo Guardrails, traces, and evaluations.
4. Acknowledge known limits such as writable-report deletion, malicious instructions inside allowed content, retrieved-content/output checks, and guardrail-unavailable behavior.
5. Review the AgentOps loop: observe, make a change, take action, evaluate, and continue.
6. Connect the simulated Northgate responsibility to real production agent operations.

### Key Takeaways

- AgentOps is an ongoing loop, not a one-time hardening checklist.
- A useful assistant must be checked for both blocked misuse and preserved operator workflows.
- Each layer enforces something different; no single layer replaces the others.
- Evidence from traces, logs, plant state, saved files, and evaluations is what makes a control claim credible.

### Infrastructure Notes

Requires no new hands-on infrastructure beyond prior modules. The page references the AgentOps loop graphic, MLflow token/cost curiosity note, and the evidence produced during modules 1–6.
