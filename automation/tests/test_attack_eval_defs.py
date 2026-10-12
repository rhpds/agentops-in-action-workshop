#!/usr/bin/env python3
"""Schema checks for the attack and eval definitions.

These live here because the definitions do. They are lab content, mounted into
the console as a ConfigMap rather than baked into its image, so nothing in the
agent repo validates them any more — and a broken one is only noticed when a
participant's console quietly drops a case.

Run: python3 -m pytest automation/tests/test_attack_eval_defs.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

DEFS = Path(__file__).resolve().parents[1] / "gitops/tenant-platform/files/attack-eval-defs"

#: Every goal type waterplant-ui's probes/goals.py can dispatch. A definition
#: naming anything else loads fine and then never produces a verdict, which
#: reads on screen as "inconclusive" forever with no clue why.
GOAL_TYPES = {
    "response_regex", "state_echo", "state_diff", "state_created",
    "fs_probe", "honeypot_hit", "all",
}
CLEANUP_TYPES = {"none", "canary_reseed", "plant_state_restore"}


def _load():
    return [(p, yaml.safe_load(p.read_text(encoding="utf-8")))
            for p in sorted(DEFS.rglob("*.yaml"))]


def test_the_definitions_are_where_the_chart_globs_them():
    """tenant-platform/templates/ui.yaml globs attacks/ and evals/ separately.

    Helm's .Files.Glob is filepath.Match: no brace alternation, no "**". A
    definition filed anywhere but these two directories renders into no
    ConfigMap key and reaches no console, silently.
    """
    assert (DEFS / "attacks").is_dir() and (DEFS / "evals").is_dir()
    stray = [p.relative_to(DEFS) for p in DEFS.rglob("*.yaml")
             if p.parent.name not in ("attacks", "evals")]
    assert stray == [], f"not reachable by the chart's globs: {stray}"


@pytest.mark.parametrize("path,doc", _load(), ids=lambda v: getattr(v, "name", ""))
def test_definition_is_well_formed(path, doc):
    for field in ("id", "kind", "title", "description", "severity",
                  "request", "goal", "polarity", "scoring"):
        assert doc.get(field), f"{path.name}: missing {field}"

    assert doc["kind"] in ("attack", "eval")
    assert doc["polarity"] in ("attack_blocked", "eval_succeeded")
    # The directory decides which ConfigMap key prefix it gets, so a file in
    # the wrong one is scored as the wrong kind.
    assert doc["kind"] == ("attack" if path.parent.name == "attacks" else "eval")
    assert doc["id"] == path.stem, "the id and the filename are both used as keys"

    goal = doc["goal"]
    assert goal.get("type") in GOAL_TYPES, f"{path.name}: unknown goal {goal.get('type')}"
    for sub in goal.get("of", []):
        assert sub.get("type") in GOAL_TYPES

    assert doc["cleanup"]["type"] in CLEANUP_TYPES if "cleanup" in doc else True

    req = doc["request"]
    turns = req.get("turns") if req.get("type") == "multi_turn" else [req.get("prompt")]
    assert turns and all(t and t.strip() for t in turns), f"{path.name}: empty prompt"

    if not doc.get("enabled", True):
        assert doc.get("disabled_reason"), (
            f"{path.name}: disabled without saying why. The console shows the "
            "reason, because a participant who cannot see that a case never "
            "runs will assume they are defended against it.")


def test_every_regex_compiles():
    """A bad pattern is only noticed when the case runs, which may be hours."""
    for path, doc in _load():
        for goal in [doc["goal"], *doc["goal"].get("of", [])]:
            if "pattern" in goal:
                re.compile(goal["pattern"])


def test_canary_names_match_exactly():
    """plants_canary and requires_canary are compared as dict keys.

    A stray path prefix on one side means the lookup never hits and the attack
    skips itself on every run, reporting a missing decoy that was in fact
    planted.
    """
    planted = {d["plants_canary"] for _, d in _load() if d.get("plants_canary")}
    required = {d["requires_canary"] for _, d in _load() if d.get("requires_canary")}
    assert required <= planted, f"no eval plants: {required - planted}"
