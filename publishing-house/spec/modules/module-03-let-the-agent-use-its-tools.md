# Module 3 — Let the Agent Use Its Tools

### Brief Overview

Participants learn that sandboxing the process is not the same as authorizing every plant tool. Hermie can now reach MCP Gateway, but the operator still has excessive Keycloak role mappings. Participants reproduce the whole-plant shutdown and plant-configuration attacks, inspect traces to identify the exact tools involved, remove unnecessary `tool:` roles from the operator, and verify that attacks fail while normal telemetry and individual pump control still work.

### Audience and Time

**Personas:** Same as module 1, especially architects and technical specialists explaining identity-aware tool governance.

**Module prerequisites:** Module 2 sandboxed Hermie with MCP Gateway, Keycloak, model, and MLflow access restored.

**Duration:** 15 minutes.

### Learning Objectives

- Explain how Keycloak and MCP Gateway participate in plant-tool access
- Use traces to identify the tool calls behind unsafe actions
- Distinguish useful operator permissions from excessive control permissions
- Remove unnecessary Keycloak tool-role assignments from the operator user
- Verify blocked attack outcomes with traces, notifications, and plant state
- Confirm legitimate telemetry and individual pump control still work

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Review MCP Gateway and Keycloak authorization | 3 min |
| 2 | Reproduce remaining tool-based attacks | 3 min |
| 3 | Investigate the operator's role mappings | 3 min |
| 4 | Remove unnecessary tool roles | 3 min |
| 5 | Verify attacks and legitimate tasks | 3 min |

### Detailed Steps

1. Review that Hermie reaches plant tools through MCP Gateway and that Keycloak role mappings determine which `tool:` permissions the operator has.
2. Re-run the whole-plant shutdown prompt and inspect plant panels and the trace.
3. Re-run the plant-configuration dump prompt and inspect the trace.
4. Record the exact tool names used by the attacks, especially `emergency_shutdown` and `dump_plant_configuration`.
5. Open the Keycloak admin console for the participant realm `waterplant-{user}` and inspect the `operator` user's role mappings.
6. Find the tool roles corresponding to the attack traces.
7. Remove `tool:emergency_shutdown` and `tool:dump_plant_configuration` while keeping roles needed for telemetry and individual pump control.
8. Allow the bridge to restart sandboxed Hermie after role changes.
9. Repeat both attack prompts and run matching attack cases from the footer.
10. Verify that the restricted tools no longer execute and that the plant state/configuration is protected.
11. Confirm useful tasks still work: pump 4 status and stopping an individual pump.
12. Run all evaluations and compare with the baseline.

### Key Takeaways

- Network access to MCP Gateway is not authorization to use every MCP tool.
- Tool access should come from trusted identity and role mappings, not from prompts.
- Traces show which tool permission actually enabled an unsafe outcome.
- Removing excessive tool roles must be paired with regression checks for legitimate operator work.

### Infrastructure Notes

Requires participant Keycloak realm, admin console access, `operator` user, per-tool role mappings for plant MCP tools, bridge behavior that refreshes/restarts Hermie after role changes, MCP Gateway enforcement, MLflow traces, plant state reset, attack definitions, and evaluation cases.
