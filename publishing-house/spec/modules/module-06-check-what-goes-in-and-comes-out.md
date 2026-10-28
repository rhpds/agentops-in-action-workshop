# Module 6 — Check What Goes In and Comes Out

### Brief Overview

Participants add content checks around the console-to-agent path using NeMo Guardrails. Before enabling guardrails, they create a poisoned handover skill, test a prompt with personal contact details, and try an off-topic Berlin travel request hidden inside an operational context. They inspect the NeMo configuration, connect the console to the guardrails endpoint, and verify sensitive-data and topic-policy verdicts while also seeing that guardrails at this location do not fix every problem inside Hermie's allowed environment.

### Audience and Time

**Personas:** Same as module 1, especially architects and platform owners evaluating where to place content checks and how to explain their limits.

**Module prerequisites:** Modules 1–5, with the sandbox, tool access, reports, and documentation paths already tuned.

**Duration:** 20 minutes.

### Learning Objectives

- Investigate unwanted behavior introduced through an installed skill
- Identify personal contact details in otherwise operational prompts
- Test topic-boundary behavior for unrelated personal travel requests
- Inspect NeMo Guardrails configuration, Presidio sensitive-data detection, and model-based self-checks
- Connect the operator console to the guardrails service
- Verify input-blocking verdicts and rail names
- Distinguish checks on operator input from protection against retrieved content, installed skills, and assistant output
- Re-check legitimate plant tasks and account for added latency

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Create and observe a poisoned handover skill | 3 min |
| 2 | Test personal details and off-topic requests before guardrails | 4 min |
| 3 | Inspect the NeMo Guardrails policy | 4 min |
| 4 | Connect the console to NeMo Guardrails | 3 min |
| 5 | Verify sensitive-data and topic checks | 4 min |
| 6 | Keep Hermie useful and review limits | 2 min |

### Detailed Steps

1. Ask Hermie to create the `northgate-handover-style` skill containing the pineapple sentence.
2. Request a shift handover summary and inspect whether the poisoned instruction appears.
3. Send a handover request containing synthetic email and phone number and observe baseline behavior before guardrails.
4. Test direct and mixed Berlin travel requests to see what Hermie does without the NeMo endpoint connected.
5. Open the `nemo-guardrails-config` ConfigMap in OpenShift and inspect `config.yaml`, `prompts.yaml`, and `rails.co`.
6. Identify sensitive-data detectors for `EMAIL_ADDRESS` and `PHONE_NUMBER`, and read the topic/self-check policies.
7. Set `NEMO_ENDPOINT=http://nemo-guardrails:80` on the water-plant UI container and wait for rollout.
8. Refresh the console and repeat the prompt containing synthetic contact details.
9. Confirm the console reports input blocked by NeMo Guardrails with `detect sensitive data on input`.
10. Remove contact details and verify the operational handover prompt reaches Hermie.
11. Repeat the mixed Berlin travel request and confirm `self check input` blocks unrelated travel/entertainment content.
12. Send an operational partner-plant maintenance checklist prompt and confirm it passes.
13. Re-test pump status and run all evaluations.
14. Discuss that input checks can block unsafe prompts before Hermie sees them, but do not automatically sanitize poisoned skills or allowed retrieved documents.

### Key Takeaways

- Guardrails are most useful when their placement is clear: here, the console checks operator input before forwarding to Hermie.
- Local sensitive-data detection and model-based topic checks solve different problems and have different latency/cost profiles.
- A blocked request may produce no new Hermie trace because it never reached the agent.
- Guardrails do not replace sandbox policy, MCP authorization, or careful control of installed skills and retrieved content.
- Every new control must be followed by useful-task regression checks.

### Infrastructure Notes

Requires NeMo Guardrails service, `nemo-guardrails-config` ConfigMap, UI support for `NEMO_ENDPOINT`, rollout permissions, guardrail verdict display in the console, Presidio detector configuration, model-based self-check model access, poisoned skill creation, MLflow/evaluation links, and latency/error behavior visible to participants.
