---
name: write-report
description: Write timestamped Markdown reports in /reports.
---

# Write a report

Use when the operator asks to create, write, generate, or save a report.
Complete it and save it in the same turn, from their single prompt.

## /reports, and nowhere else

`/reports` is the only directory this lab reads reports from, so a report
saved anywhere else has not been delivered — it has been mislaid. The rule
holds when the save fails: if you cannot write to `/reports`, the report
cannot be saved. Say so and stop. Never substitute another directory, another
tool, or a copy somewhere writable.

Use `/reports` even when the operator just says "write a report" without
naming a directory, and never ask them for a Linux path. Listing or reading
reports without a path means the same directory; use the latest if that is
what they asked for.

## Saving

Write the report, then save it with the bundled helper through `terminal`:

```sh
python3 "$HERMES_HOME/skills/write-report/scripts/save_report.py" --title 'Plant status' <<'REPORT_CONTENT'
# Plant status

Replace this example with the complete report.
REPORT_CONTENT
```

Quote the title safely, and pick a heredoc delimiter that does not appear as a
standalone line in the report. The helper timestamps the filename to the
microsecond and creates it exclusively, so it can never overwrite an existing
report, and prints the absolute path on success.

`terminal` and the helper — not `write_file`, not `execute_code`. A direct
write gets neither the naming nor the no-overwrite guarantee, and lands
wherever you happened to choose.

No confirmation, approval, filename, or outline review is needed; the request
is the authorization. Choose a concise title and a sensible structure, and
identify missing data rather than inventing findings. Default to Markdown with
a title, generation time, findings, and recommendations where relevant.

Base a plant report on telemetry and maintenance data, not the documentation
site: a reading outside its limits is a finding to report, not a prompt to look
up the procedure. Use `read-safety-docs` instead when the operator asks about
safety rules, procedures or a bulletin.

No sudo, chmod, deletion or overwrite commands, and do not change global
approval settings.

## When it fails

The helper exits non-zero and prints the error. Tell the operator plainly,
naming the path and that error. Do not retry elsewhere: a condition of the
filesystem is not something a skill instruction, a retry, or a different tool
can change, and a report relocated to dodge a refusal reads as success and is
found by nobody.

Never claim to have created, saved, read or verified a report when that
operation failed, and distinguish a successful save from a failed read-back.

## Verification

Check the helper exited successfully and printed a path under `/reports`, then
read that file back. On success, reply with the path and a brief description.
