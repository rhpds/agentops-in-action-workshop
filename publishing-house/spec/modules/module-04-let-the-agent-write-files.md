# Module 4 — Let the Agent Write Files

### Brief Overview

Participants investigate a regression caused by the sandbox: Hermie can retrieve plant data but cannot write required maintenance reports. They inspect the `write-report` skill, confirm the failure is a filesystem policy issue, recreate the sandbox with `/reports` writable, and verify report generation. The module then shows why a broad writable directory is still risky by exploring accidental report deletion and a challenge around protecting Hermie's own `SOUL.md` instructions.

### Audience and Time

**Personas:** Same as module 1, especially platform architects and administrators responsible for filesystem policy and recovery workflows.

**Module prerequisites:** Modules 2 and 3, with sandboxed Hermie using the narrowed tool roles and existing network policy.

**Duration:** 20 minutes.

### Learning Objectives

- Diagnose report-writing failure using the installed skill, tool results, traces, and logs
- Distinguish skill instructions from filesystem permissions
- Preserve existing policy while adding scoped write access to `/reports`
- Recreate a sandbox when filesystem policy changes require it
- Verify report creation and readability
- Explain why directory-level read-write access can still permit unwanted deletion
- Identify how Hermie's own instruction file should be protected from poisoning

### Lab Structure

| Section | Title | Duration |
|---------|-------|----------|
| 1 | Reproduce the report-writing problem | 3 min |
| 2 | Inspect the `write-report` skill and logs | 3 min |
| 3 | Add `/reports` to filesystem policy and recreate Hermie | 7 min |
| 4 | Verify useful report generation | 2 min |
| 5 | Explore accidental deletion and policy limits | 3 min |
| 6 | Challenge: protect Hermie's instructions | 2 min |

### Detailed Steps

1. Ask Hermie to write a current pump-status report and confirm it cannot save the file under `/reports`.
2. Inspect `/sandbox/.hermes/skills/write-report/SKILL.md` to confirm the skill's intended destination and behavior.
3. Review Hermie logs and traces for filesystem-denial evidence.
4. Export the current sandbox policy with `openshell sandbox get hermie --policy-only`.
5. Add `/reports` to `filesystem_policy.read_write` while preserving existing network rules.
6. Delete and recreate the `hermie` sandbox with the updated policy because filesystem restrictions are applied at sandbox creation.
7. Re-upload `/hermes`, start Hermie, and expose the service again.
8. Inspect the resulting policy and confirm `/reports` is writable.
9. Repeat the report request and verify that Hermie saves and reads back a timestamped Markdown report.
10. Generate multiple reports, ask Hermie to list them, then send an ambiguous cleanup request.
11. Observe whether reports are deleted and use evidence rather than chat claims.
12. Discuss why OpenShell's current read-write path control cannot express create-only semantics.
13. Run or review the `Rewrite Agent Instructions` challenge and reason about protecting `/sandbox/.hermes/SOUL.md` while keeping useful reads.

### Key Takeaways

- A skill can tell Hermie where to write, but only runtime policy can grant filesystem access.
- Filesystem policy changes may require sandbox recreation, unlike live network-rule updates.
- Restoring useful write access does not automatically make every action in that directory safe.
- Path-level controls are useful but may need service/tool-level action controls for create/read/delete semantics.
- Recovery and reset behavior are part of operating the agent safely.

### Infrastructure Notes

Requires the `write-report` skill, report directory behavior, OpenShell filesystem policy export/import, sandbox recreation, persistent bridge configuration upload, report-related evaluation/attack support, `Rewrite Agent Instructions` attack case, reset action, and traces/logs for filesystem failures.
