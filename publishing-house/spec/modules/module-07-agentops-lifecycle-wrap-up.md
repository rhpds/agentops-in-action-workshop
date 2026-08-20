# Module 7 — AgentOps lifecycle and wrap-up

### Brief Overview

The closing module connects everything participants just did into one repeatable workflow and makes the positioning explicit: one unchanged agent was progressively surrounded with production controls, and each layer had a distinct job. Participants recap the ten-step journey from observing MLflow through to re-evaluating in EvalHub, then discuss how these controls integrate into real development and deployment processes rather than remaining a lab exercise. Optional advanced challenges are provided for participants who finish the core path early.

### Audience and Time

**Personas:** Same as module 1. This module is where architects and technical sales specialists consolidate the story they will retell to customers.

**Module prerequisites:** Modules 1 through 6.

**Duration:** 10 minutes, plus open-ended optional advanced challenges for participants who finish early.

### Learning Objectives

- Describe how evaluations, traces, policies, identity, and observability compose into a repeatable AgentOps workflow
- Differentiate the enforcement responsibility of each layer applied during the lab
- Explain how these controls integrate into development and deployment processes
- Identify recommended practices for moving an agent from experimentation to enterprise use

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Recap the ten-step AgentOps journey | 4 min |
| 2 | Layer responsibilities and the BYOA position | 3 min |
| 3 | Integrating AgentOps into delivery practice | 3 min |
| — | Optional advanced challenges | open-ended |

### Detailed Steps

1. Recap the journey in order, naming the technology used at each step:
   1. **Observe** — MLflow Tracing
   2. **Establish baseline** — EvalHub
   3. **Attack** — Garak plus manual adversarial testing
   4. **Contain execution** — Agent Sandbox and Kata
   5. **Apply runtime policy** — OpenShell
   6. **Protect credentials** — OpenShell with Vault or Kubernetes Secrets
   7. **Govern enterprise tools** — MCP Gateway
   8. **Establish identity** — SPIFFE/SPIRE and inbound caller authentication
   9. **Authorize** — Kuadrant AuthPolicy, Authorino, and OPA
   10. **Re-evaluate** — EvalHub, MLflow, and Garak
2. State the responsibility of each layer in one line: vLLM and Model Gateway make the model usable; Agent Sandbox and Kata contain execution; OpenShell governs what the agent can do; MCP Gateway governs what the agent can reach; SPIFFE and caller identity establish who is acting; OPA, Authorino, and Kuadrant decide what is allowed; Guardrails protect the inference boundary; MLflow shows what happened; Garak finds weaknesses; EvalHub proves the controls improved the system without destroying its usefulness.
3. Return to the module 1 framing and confirm it held: the agent framework was never changed, and every control came from the infrastructure around it.
4. Discuss where each control belongs in a delivery process — which are deployment-time decisions, which are continuous, and which belong in a pre-production gate.
5. Discuss how continuous evaluation detects regression when models, tools, or policies change after go-live.
6. Summarize the recommended practices for moving an agent from experimentation toward enterprise operation.
7. Point participants who finished early at the optional advanced challenges.

### Key Takeaways

- AgentOps is a loop, not a hardening checklist: observe, baseline, attack, contain, authorize, re-evaluate, tune
- The same agent that "works" at the start of the lab is observable, contained, identity-aware, and policy-governed at the end — with no change to the agent itself
- Each layer has a distinct and non-substitutable responsibility, and confusing them is how agents get deployed unsafely
- Bring the agent you want; the platform supplies the security, identity, observability, governance, and lifecycle infrastructure that makes it production-ready

### Infrastructure Notes

Optional advanced challenges should be available without additional provisioning and may include: additional Garak profiles, more granular network and tool policies, deliberate policy troubleshooting scenarios, and deeper analysis of agent traces and evaluation scorecards. Forward-looking capabilities such as an MCP registry or an agent and skill catalog belong in this wrap-up discussion rather than as hands-on dependencies.
