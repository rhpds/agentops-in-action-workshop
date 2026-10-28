# Module 1 — Introduction to AgentOps & Meet Hermie

### Brief Overview

Participants meet Hermie, the Northgate Water Treatment Works operator assistant, and establish the baseline operating picture used throughout the lab. They learn what the agent can do, how it reaches models and MCP tools, where operators interact with it, and how MLflow traces record the evidence behind answers. The module intentionally lets participants try useful plant operations, report writing, broad web/file access, and attack prompts before any controls are added.

### Audience and Time

**Personas:** Solution architects, AI platform architects, consultants and services professionals, technical sales specialists, OpenShift AI administrators, and technical leaders advising on enterprise AI adoption.

**Module prerequisites:** General containers, Kubernetes/OpenShift, and generative AI familiarity. No prior Hermie, OpenShell, MLflow, or MCP experience is required.

**Duration:** 20 minutes.

### Learning Objectives

- Explain the role of Hermie as a tool-enabled waterplant operator assistant
- Identify the main parts of the starting architecture: operator console, Hermie, model, MCP Gateway, plant tools, skills, and MLflow
- Run legitimate plant operations and report generation before controls are added
- Observe broad web and filesystem access that exceeds the operator's needs
- Use the console's attack and evaluation controls to establish baseline behavior
- Locate request evidence in MLflow traces

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Your role and the initial Hermie deployment | 4 min |
| 2 | Ask Hermie about the plant and stop one pump | 4 min |
| 3 | Ask for a maintenance report | 2 min |
| 4 | Find request evidence in MLflow | 3 min |
| 5 | Explore access beyond operator needs | 3 min |
| 6 | Run one attack and the baseline evaluations | 4 min |

### Detailed Steps

1. Review the Northgate scenario and the distinction between the Hermes framework and the customized Hermie assistant.
2. Inspect the starting architecture: Hermie, the operator console, MCP Gateway, telemetry/maintenance/control MCP tools, and the MaaS-hosted LLM.
3. Open the operator console and identify the plant panels, safety envelope, maintenance assistant, footer controls, reset button, attack selector, evaluation button, and MLflow trace link.
4. Ask for pump 4 status and verify the answer against the plant panel.
5. Ask Hermie to stop pump 4 because of high vibration and verify the actual plant state changed.
6. Ask Hermie to write a current plant-status report and observe that the `write-report` skill saves a file under `/reports`.
7. Open MLflow, select the participant experiment, and inspect traces for the pump and control requests.
8. Ask Hermie to list water plants in New York and to read `/README.md`, then discuss why those capabilities are broader than the operator needs.
9. Try the whole-plant shutdown and plant-configuration prompts, then reset the plant.
10. Run an available attack from the console footer and interpret the notification states: got through, blocked, declined-not-blocked, and inconclusive.
11. Run all evaluations and save the baseline understanding of which useful tasks and attacks currently succeed.

### Key Takeaways

- Hermie is useful because it can call tools, use skills, and act on the plant, but those same abilities create risk.
- Chat claims are not enough; participants must verify plant state, saved files, traces, and evaluation results.
- MLflow traces are the evidence layer used throughout the rest of the lab.
- The baseline intentionally shows both useful behavior and excessive authority before controls are introduced.

### Infrastructure Notes

Requires the water-plant UI, unsandboxed/baseline Hermie endpoint, plant APIs, MCP Gateway and plant MCP servers, report-writing skill, MLflow tracing, attack definitions, evaluation definitions, reset support, and participant-specific OpenShift AI access.
