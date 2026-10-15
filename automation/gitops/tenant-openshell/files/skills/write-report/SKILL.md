---
name: write-report
description: Write timestamped Markdown reports under /reports.
---

# Write a report

## When to use

Use when the user asks to create, write, generate, or save a report. Complete
the report and save it in the same turn, from the user's single prompt.

## Procedure

Use `/reports` for every report, including when the user just says
"create a report" or "write a report" without specifying a directory. Never ask
an operator for a Linux path. When asked to list or read reports without a path,
use the same directory; use the latest report if that is what the user requests.

The request authorizes creating `/reports` if missing and writing a new report
there. Do not ask for confirmation, approval, a filename, or an outline review.
Use the supplied topic, data, and available tools. Choose a concise title and
reasonable structure; identify missing data rather than inventing findings.
Default to Markdown, with a title, generation time, findings, and recommendations
when relevant.

Base a plant report on telemetry and maintenance data. Do not read the
documentation site for it: a reading outside its limits is a finding to report,
not a prompt to go looking up the procedure. Consult the documentation only
when the operator asks about safety rules, operating procedures or a bulletin,
and then follow `read-safety-docs` rather than this skill.

Save the complete Markdown text with the bundled helper by running this with
the `terminal` tool. Use `terminal` and no other tool for the save: not
`execute_code`, not `write_file`. The helper does the writing, and `terminal`
is the only tool whose use of it is approved here.

```sh
python3 "$HERMES_HOME/skills/write-report/scripts/save_report.py" --title 'Plant status' <<'REPORT_CONTENT'
# Plant status

Replace this example with the complete report.
REPORT_CONTENT
```

Run it with `terminal`. Quote the title safely and use a quoted heredoc delimiter that does not occur
as a standalone line in the report. The helper creates `/reports`, prefixes the
filename with the actual UTC date and time including microseconds, and creates
the file exclusively so an existing report is never overwritten. It prints the
absolute path after successfully writing the report.

## Pitfalls

Do not use sudo, chmod, deletion, or overwrite commands. Do not change global
approval settings. Do not reach for `execute_code` when `terminal` is the
documented path; it is unavailable here, and a report that waits on approval
is a report that was never written. If filesystem permissions or sandbox policy block writing,
report the actual error; skill instructions cannot grant runtime permissions.
If you cannot create `/reports`, create or save the report, or read a report,
say so explicitly in your reply. Include the affected path and the actual tool
error or reason, when available. Distinguish a successful save from a failed
read-back. Never claim to have created, saved, read, or verified a report when
that operation failed.

## Verification

Check that the helper succeeds and returns a path under `/reports`, then read
the saved report to verify its contents. If either operation fails, explain the
failure as described above. On success, reply with the path and a brief
description of the report; no further approval is needed.
