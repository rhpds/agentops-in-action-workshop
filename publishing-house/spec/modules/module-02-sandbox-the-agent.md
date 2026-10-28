# Module 2 — Sandbox the Agent

### Brief Overview

Participants put Hermie into an OpenShell sandbox and experience the operational tradeoff of default-deny isolation. The sandbox blocks network and filesystem access by default, so participants progressively restore only the dependencies Hermie needs: Keycloak, MCP Gateway, the model endpoint, and MLflow tracing. They then confirm that broad internet and file access remain blocked while core plant queries work again.

### Audience and Time

**Personas:** Same as module 1, with emphasis on platform architects and OpenShift AI administrators who need to explain and operate runtime controls.

**Module prerequisites:** Module 1 baseline behavior and basic terminal/OpenShift use.

**Duration:** 20 minutes.

### Learning Objectives

- Explain why prompt instructions alone do not enforce runtime limits
- Describe OpenShell's sandbox, supervisor, gateway, and bridge components
- Create a sandboxed Hermie instance from the existing Hermes image
- Upload externalized Hermie configuration and expose the sandboxed service
- Use OpenShell logs to identify denied dependencies
- Add scoped network rules for Keycloak, MCP Gateway, model access, and MLflow tracing
- Verify that plant queries work while unnecessary internet and filesystem access remain blocked

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Why sandboxing matters and what OpenShell is | 3 min |
| 2 | Create and start sandboxed Hermie | 6 min |
| 3 | Point the UI at the sandboxed agent | 2 min |
| 4 | Investigate default-deny failures | 3 min |
| 5 | Restore required network dependencies | 4 min |
| 6 | Check what sandboxing changed | 2 min |

### Detailed Steps

1. Review why asking the agent not to do something is different from enforcing it.
2. Identify OpenShell's sandbox, supervisor, gateway, and the lab's Hermes bridge.
3. Log in to OpenShift and verify the OpenShell gateway and bridge pods.
4. Enter the bridge CLI container, add/select the OpenShell gateway, and create the `hermie` sandbox from `quay.io/rh-aiservices-bu/waterplant-hermes:0.2.7`.
5. Inspect the sandbox resource and its pod, then upload `/hermes` configuration into `/sandbox`.
6. Start Hermie inside the sandbox and expose service port 8080.
7. Update the water-plant UI `AGENT_URL` to target the sandboxed agent and wait for rollout.
8. Send a pump query and observe that default-deny networking prevents a useful answer.
9. Inspect OpenShell and Hermie logs for denied Keycloak, MCP Gateway, model, and MLflow requests.
10. Add network policy rules for MCP Gateway and Keycloak, restart Hermie for tool discovery, then add the model endpoint.
11. Use OpenShell Term or the equivalent CLI command to allow MLflow tracing.
12. Confirm pump status works and produces a trace.
13. Re-test New York web search, `/README.md` file reading, and report generation to determine which broad capabilities remain blocked.
14. Run evaluations and record intended restrictions versus regressions.

### Key Takeaways

- Sandboxing immediately reduces risk but can also break legitimate dependencies until policy is tuned.
- OpenShell network rules should restore named destinations, not reopen general internet access.
- The sandbox does not change Hermie's code; it changes what the running process is allowed to reach.
- Logs and traces make the difference between model behavior and infrastructure denial visible.

### Infrastructure Notes

Requires OpenShell gateway, Hermes bridge with CLI/certificates, sandbox CRD/operator, the Hermes image, prepared `/hermes` configuration, `hermes-agent` bridge service, Keycloak, MCP Gateway, MaaS endpoint, MLflow relay, OpenShell Term tab, and UI environment-variable rollout permissions.
