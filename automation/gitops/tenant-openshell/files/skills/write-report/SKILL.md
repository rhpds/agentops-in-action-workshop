---
name: write-report
description: Write timestamped Markdown reports under /reports.
---

# Write a report

## When to use

Use when the user asks to create, write, generate, or save a report. Complete
the report and save it in the same turn, from the user's single prompt.

## Procedure

The request authorizes creating `/reports` if missing and writing a new report
there. Do not ask for confirmation, approval, a filename, or an outline review.
Use the supplied topic, data, and available tools. Choose a concise title and
reasonable structure; identify missing data rather than inventing findings.
Default to Markdown, with a title, generation time, findings, and recommendations
when relevant.

Save the complete Markdown text with the bundled helper using the terminal tool:

```sh
python3 "$HERMES_HOME/skills/write-report/scripts/save_report.py" --title 'Plant status' <<'REPORT_CONTENT'
# Plant status

Replace this example with the complete report.
REPORT_CONTENT
```

Quote the title safely and use a quoted heredoc delimiter that does not occur
as a standalone line in the report. The helper creates `/reports`, prefixes the
filename with the actual UTC date and time including microseconds, and creates
the file exclusively so an existing report is never overwritten. It prints the
absolute path after successfully writing the report.

## Pitfalls

Do not use sudo, chmod, deletion, or overwrite commands. Do not change global
approval settings. If filesystem permissions or sandbox policy block writing,
report the actual error; skill instructions cannot grant runtime permissions.
Do not claim the report was saved when the helper failed.

## Verification

Check that the helper succeeds and returns a path under `/reports`. Reply with
that path and a brief description of the report; no further approval is needed.
