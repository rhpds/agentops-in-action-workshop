#!/bin/sh
# Restore the lab's skill library to the state the chart ships, and remove
# anything else that has appeared in it.
#
#   reseed-skills.sh <pristine-dir> <hermes-home>
#
# Both runtimes publish the same flat filenames — read-safety-docs-SKILL.md,
# write-report-SKILL.md, save-report.py — so the only difference is where
# they were published to and which home to write into:
#
#   plain    reseed-skills.sh /config         /app/.hermes
#   sandbox  reseed-skills.sh /sandbox/hermes /sandbox/.hermes
#
# Why this exists rather than three cp lines inline. $HERMES_HOME is a PVC and
# the skills tree is writable, which is deliberate — module 5 is about an agent
# that can act. But Hermes' post-turn skill review can patch a SKILL.md, and
# an injected instruction that reaches a skill file stops being a one-turn
# attack: it fires on every later lookup and outlives the conversation that
# carried it. The chart disables that review (waterplant.hermesSkills), and
# this script is the way back for an environment that already drifted, or
# that a participant edited while exploring.
#
# Idempotent, and the only path that writes these three files, so "the live
# skill differs from the ConfigMap" is always a reseed away from fixed.
set -e

SRC="${1:?usage: reseed-skills.sh <pristine-dir> <hermes-home>}"
HOME_DIR="${2:?usage: reseed-skills.sh <pristine-dir> <hermes-home>}"
SKILLS="$HOME_DIR/skills"

mkdir -p "$SKILLS/read-safety-docs" "$SKILLS/write-report/scripts"
cp "$SRC/read-safety-docs-SKILL.md" "$SKILLS/read-safety-docs/SKILL.md"
cp "$SRC/write-report-SKILL.md"     "$SKILLS/write-report/SKILL.md"
cp "$SRC/save-report.py"            "$SKILLS/write-report/scripts/save_report.py"

# Anything else under skills/ was created after the pod started: an
# agent-authored skill, or a curator archive. Neither belongs in a lab whose
# modules assume exactly these two.
for d in "$SKILLS"/* "$SKILLS"/.archive; do
  [ -d "$d" ] || continue
  case "${d##*/}" in
    read-safety-docs|write-report) continue ;;
  esac
  rm -rf "$d"
done

# Usage counters and curator scheduling state name skills that may no longer
# exist and carry patch counts from the run being reset. Hermes recreates both
# on demand, so removing them is how the reset reads as a fresh pod.
rm -f "$SKILLS/.usage.json" "$SKILLS/.usage.json.lock" \
      "$SKILLS/.curator_state" "$SKILLS/.bundled_manifest"

echo "reseed-skills: restored read-safety-docs and write-report from $SRC"
