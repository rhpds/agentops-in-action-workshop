# Module 2 — Explore the agent and establish a baseline

### Brief Overview

Participants inspect what the agent can actually reach and capture the measurements that every later module is compared against. The agent starts already inside an Agent Sandbox backed by Kata, but with an intentionally permissive OpenShell policy — broad filesystem access, common utilities allowed, general outbound HTTPS, one over-broad synthetic credential, and both read and privileged update MCP tools available. Participants run three normal tasks, inspect one execution end to end in MLflow, then run a prebuilt EvalHub suite and save the result as the baseline scorecard. The deliberate point of this module is that the agent scores well: it works because it has too much authority.

### Audience and Time

**Personas:** Same as module 1. Participants who are less comfortable reading traces should pair with the guided walkthrough in section 3.

**Module prerequisites:** Module 1 — participants must already know the request path and be able to find a trace in MLflow.

**Duration:** 15 minutes. First hands-on module; roughly two thirds of the time is inspection, one third is running the evaluation suite.

### Learning Objectives

- Enumerate the tools, MCP servers, and resources currently available to the agent
- Observe how the agent selects and invokes a tool for a given request
- Inspect a complete agent execution trace in MLflow, span by span
- Execute a prebuilt EvalHub suite and save the resulting baseline scorecard
- Identify where the baseline configuration grants more authority than the workflow requires

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Review the baseline security posture | 3 min |
| 2 | Perform three normal agent tasks | 4 min |
| 3 | Inspect one execution in MLflow Tracing | 4 min |
| 4 | Run the EvalHub suite and save the baseline scorecard | 4 min |

### Detailed Steps

1. Review the agent's starting configuration and record each control's baseline state: filesystem is broadly accessible inside the sandbox; Python, shell, and common utilities are permitted; general outbound HTTPS is allowed; one intentionally over-broad synthetic credential is present; both read and privileged update MCP tools are reachable; user authorization is minimally differentiated; only basic content safety is enabled.
2. Review the list of tools and MCP servers exposed to the agent, and note which are read-only and which can change enterprise state.
3. Perform the first normal task — a knowledge lookup.
4. Perform the second normal task — an incident or ticket lookup.
5. Perform the third normal task — a calculation or code execution request.
6. For each task, note which tool the agent chose and whether the choice was the one you expected.
7. Open MLflow Tracing and select one of the three executions.
8. Walk the trace in order and identify each stage: prompt, model request, tool choice, MCP call, tool response, final answer.
9. Note which parts of the trace are model behavior and which are runtime or platform behavior — this distinction is used directly in modules 3 and 6.
10. Open EvalHub and run the prebuilt suite of approximately 8–10 tests covering successful knowledge lookup, successful ticket lookup, successful calculation or code execution, correct tool selection, response quality, and a small number of security assertions.
11. Save the result as the **Baseline scorecard**. This artifact is compared directly against the hardened scorecard in module 6.
12. Review the baseline scores. Note that functional results are strong and security assertions are weak, and identify at least one specific capability the agent holds that its normal workflow never uses.

### Key Takeaways

- A functional baseline and a security baseline are different measurements, and an agent can pass one while failing the other
- The agent performs well in the baseline because it has been granted authority far beyond what its workflow requires
- Traces distinguish model decisions from runtime enforcement, which is what makes later failures diagnosable
- A saved baseline scorecard is what turns "we added security" into a measurable before-and-after claim

### Infrastructure Notes

Requires the permissive baseline OpenShell policy pre-loaded per participant, a `SandboxClaim` already allocated from a warm pool, MCP servers registered through MCP Gateway with both read and privileged update tools exposed, synthetic incident and knowledge-base data seeded, the MLflow experiment active, and the EvalHub project with its 8–10 test baseline suite prebuilt and runnable without configuration.
