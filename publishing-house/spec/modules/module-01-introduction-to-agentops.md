# Module 1 — Introduction to AgentOps

### Brief Overview

This module establishes why operating an AI agent is not the same problem as operating a traditional application, and gives participants the complete architecture picture before any individual control is discussed. Rather than opening with slides, it opens with the already-running agent answering one ordinary business question, then shows that the same interaction produced a full MLflow trace. The central teaching point is the BYOA position: the agent framework itself is not the Red Hat product — the infrastructure around the agent is. Everything in the remaining six modules is a layer added to this starting picture.

### Audience and Time

**Personas:** Solution architects, AI platform architects, consultants and services professionals, technical sales specialists, OpenShift AI administrators, technical leaders advising on enterprise AI adoption.

**Module prerequisites:** None beyond the lab prerequisites — containers and Kubernetes basics, generative AI and LLM concepts, and familiarity with the general idea of AI agents.

**Duration:** 10 minutes. This module is framing rather than hands-on; participants perform one interaction and one trace lookup.

### Learning Objectives

- Describe how operating a tool-enabled AI agent differs operationally from operating a traditional application
- Identify the main categories of risk introduced by tool-enabled and autonomous agents
- Trace a single agent request through the request path: user, agent, model, tools, enterprise services
- Locate an agent execution in MLflow and identify its component spans

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | What AgentOps is and why agents are different | 3 min |
| 2 | Ask the agent one business question | 3 min |
| 3 | Walk the request path through the architecture | 2 min |
| 4 | Find the same interaction in MLflow | 2 min |

### Detailed Steps

1. Read the framing: AI agents invoke tools, execute generated code, and reach enterprise services, which is what makes them useful and what makes an uncontrolled agent a security and governance problem.
2. Review the risk categories that the rest of the lab addresses: excessive tool authority, unconstrained code execution, unconstrained network egress, over-broad credentials, and authorization decided by prompt content rather than by identity.
3. Open the agent's browser UI. Confirm the agent is already running — nothing needs to be deployed.
4. Ask the agent one normal business question, for example: "Find the open incident for application X, summarize it, and recommend the next action."
5. Observe the answer the agent returns.
6. Walk through what just happened: the agent received the request; called the model through Model Gateway; selected an MCP tool; MCP Gateway routed the call; the tool returned the ticket; the model produced the final answer.
7. Open MLflow Tracing and locate the trace for the interaction just performed.
8. Confirm the trace contains the prompt, the model request, the tool choice, the MCP call, the tool response, and the final answer.
9. Note the two mental models that structure the rest of the lab — the request path (user → agent → model → tools → enterprise services) and the control stack (identity → sandbox → policy → tracing → evaluation).

### Key Takeaways

- Agents differ from traditional applications because they choose their own actions at runtime, so authority granted at deploy time is exercised unpredictably
- The agent framework is the customer's choice; Red Hat supplies the identity, isolation, observability, governance, and lifecycle infrastructure around it
- Every agent interaction produces a trace, and the trace is the primary evidence used throughout this lab
- The request path and the control stack are two different views of the same system, and both are needed to reason about agent risk

### Infrastructure Notes

Requires the agent, its UI, Model Gateway, MCP Gateway, at least one MCP server with synthetic incident data, and an MLflow experiment already collecting traces. Trace latency between the interaction and its appearance in MLflow should be short enough that participants can find it within the 2 minutes allotted.
