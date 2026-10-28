# Module 5 — Let the Agent Reach the Docs Website

### Brief Overview

Participants restore Hermie's access to safety documentation without reopening the internet. They inspect the `read-safety-docs` skill, allow the documentation service, then discover a compromised bulletin that redirects Hermie to an attack path causing emoji-only behavior. They replace the broad host rule with method-and-path scoped access to `/doc` and `/doc/**`, proving that useful documentation still works while the redirected `/attack/override` request is denied.

### Audience and Time

**Personas:** Same as module 1, especially architects explaining least-privilege network access and indirect prompt injection.

**Module prerequisites:** Modules 2–4, with sandboxed Hermie, required plant/model/tracing access, tool roles narrowed, and report writing restored.

**Duration:** 20 minutes.

### Learning Objectives

- Diagnose blocked documentation access using a skill definition and traces
- Restore access to a specific documentation host without broad internet access
- Recognize indirect prompt injection delivered through retrieved content
- Investigate redirects and OpenShell HTTP denials in logs
- Replace a broad host rule with method-and-path scoped rules
- Verify legitimate documentation reads while blocking the unwanted redirect path
- Explain why allowed sources can still carry untrusted instructions

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Reproduce the blocked safety-documentation lookup | 3 min |
| 2 | Inspect the `read-safety-docs` skill | 2 min |
| 3 | Add initial documentation access | 3 min |
| 4 | Investigate the compromised bulletin | 4 min |
| 5 | Replace broad access with scoped `/doc` rules | 5 min |
| 6 | Verify useful docs and blocked attack path | 3 min |

### Detailed Steps

1. Ask Hermie for pump vibration limits from safety documentation and confirm the lookup fails.
2. Inspect `/sandbox/.hermes/skills/read-safety-docs/SKILL.md` to find the documentation URL used by the skill.
3. Add an OpenShell network rule for `waterplant-docs:8080` and verify safety-documentation prompts work.
4. Ask Hermie to read the latest field service bulletin and observe the emoji/injection behavior.
5. Inspect traces and Hermie logs for the redirect from `/doc/field-service-bulletin` to `/attack/override`.
6. Open the documentation website and confirm the bulletin content is compromised.
7. Remove the broad `waterplant_docs` rule.
8. Create a replacement rule that permits only `GET /doc` and `GET /doc/**` on `waterplant-docs:8080` for the relevant binaries.
9. Insert the rule into the current policy and apply it with `openshell policy set`.
10. Confirm no remaining broad rule grants the same host.
11. Retry the bulletin request and verify the redirect to `/attack/override` is denied.
12. Retry the useful pump-vibration documentation prompt and confirm it still works.
13. Run all evaluations and inspect any documentation regressions.

### Key Takeaways

- Restoring a dependency should start narrow and become narrower as evidence improves.
- Host-level access can be too broad when one path is useful and another path is malicious.
- Redirects and fetched content must be checked against policy too.
- Blocking an attack delivery route is not the same as solving all prompt injection; allowed documents can still contain hostile instructions.
- Tracing and policy logs are both needed to explain what happened.

### Infrastructure Notes

Requires `waterplant-docs` service and route, documentation pages under `/doc`, compromised field service bulletin redirecting to `/attack/override`, `read-safety-docs` skill, OpenShell HTTP path/method enforcement, policy set/get commands, sandbox logs, MLflow traces, and documentation-related evaluation cases.
