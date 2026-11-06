#!/usr/bin/env python3
"""Load and validate attack/eval definitions.

Schema is documented in ../attack-eval-defs/SCHEMA.md — that file is the contract, this
module is its parser. Keep them in step.

NOTE ON DEPENDENCIES: this is the one module that cannot be pure stdlib, since the
definitions are YAML. Either the base image ships PyYAML, or the ConfigMap is rendered
to JSON at template time and this parses JSON instead. Decide before implementation —
the rest of the runner is stdlib-only and it would be a shame to pull in a package for
one loader.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass, field


@dataclass
class Assertion:
    """One check against a turn's response and trace.

    `type` is one of: tool_denied, network_denied, fs_denied, fs_written,
    guardrail_verdict, response_contains, response_not_contains, legitimate_success.
    Remaining fields are type-specific and carried in `params`.
    """

    type: str
    params: dict = field(default_factory=dict)


@dataclass
class CleanupSpec:
    """How to undo a successful attack.

    `type` selects a primitive implemented in cleanup.py — none, canary_reseed, or
    plant_state_restore. Deliberately a closed enum, not a script: see SCHEMA.md for
    why these files must not become a place arbitrary code runs.
    """

    type: str = "none"
    captures: list = field(default_factory=list)
    verify: Assertion = None


@dataclass
class TestCase:
    """One attack or eval. Mirrors SCHEMA.md field for field.

    `polarity` is what makes attacks and evals scorable on one scale: attack_blocked
    means "passing = the bad thing did not happen", eval_succeeded means "passing = the
    good thing did happen".
    """

    id: str
    kind: str
    title: str
    description: str
    severity: str
    request: dict
    assertions: list
    pass_condition: str
    polarity: str
    scoring: dict
    enabled: bool = True
    maps_to_module: str = ""
    scenario: int = None
    tags: list = field(default_factory=list)
    plants_canary: str = ""
    cleanup: CleanupSpec = None


def load_definitions(defs_dir):
    """Load every definition under defs_dir. Returns (attacks, evals).

    Disabled cases are returned too, flagged rather than dropped, so the runner can
    report "defined but not executable" distinctly from "not defined" — the state
    account-takeover-guardrails is in until NeMo Guardrails exists.
    """
    raise NotImplementedError


def validate_case(doc, source_path):
    """Validate one parsed document, raising on anything malformed.

    Strict on purpose. A typo in a metric_name silently starts a new MLflow metric
    series and breaks a participant's history without erroring anywhere.
    """
    raise NotImplementedError


def render_templates(case, cycle_id):
    """Return a copy of `case` with {{ cycle_id }} substituted throughout.

    Applies to request prompts/turns, plants_canary, and assertion path params — the
    canary filename has to match in all three or the attack targets a file the eval
    never created.
    """
    raise NotImplementedError
