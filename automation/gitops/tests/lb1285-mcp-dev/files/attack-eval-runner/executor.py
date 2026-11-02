#!/usr/bin/env python3
"""Running one case and deciding whether it passed.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass, field


@dataclass
class CaseResult:
    """Outcome of one attack or eval.

    Attributes:
        case_id: The definition's id.
        passed: True when the participant is defended (attack) or the agent worked
            (eval). None when inconclusive.
        attack_succeeded: Attacks only. True when the bad thing happened — this is what
            triggers cleanup, and it is NOT simply `not passed`: an inconclusive result
            is neither a pass nor grounds for cleanup.
        inconclusive_reason: Set when the case could not be judged — transport error,
            missing trace, or a skipped canary dependency. Scored as neither pass nor
            fail; a participant is not penalised for the runner's own blind spots.
        assertion_results: Per-assertion detail, for the UI's results panel.
        trace_id: Cross-reference into the participant's inference experiment.
    """

    case_id: str
    passed: bool = None
    attack_succeeded: bool = False
    inconclusive_reason: str = None
    assertion_results: list = field(default_factory=list)
    trace_id: str = None


def run_attack(client, case, context):
    """Run one attack, returning CaseResult."""
    raise NotImplementedError


def run_eval(client, case, context):
    """Run one eval, returning CaseResult."""
    raise NotImplementedError


def evaluate_assertions(case, turn_result, trace):
    """Apply a case's assertions, combining per pass_condition.

    Response-text assertions can be judged from the turn alone. Trace-based ones
    (tool_denied, network_denied, fs_denied, fs_written) need the exported trace, and
    return inconclusive rather than passing when it has not landed yet.

    UNVERIFIED: the span attributes these read — tool call names, denial outcomes,
    outbound hosts — are emitted by the hermes_otel plugin and are documented nowhere in
    this repo. Capture a real trace and pin the attribute names down before implementing,
    rather than guessing a convention that silently never matches.

    A tool_denied assertion in particular must distinguish three cases: the tool was
    called and rejected (pass), the tool was never attempted because the model chose
    otherwise (pass, but weaker evidence — the policy was not actually exercised), and
    the tool was called and succeeded (fail).
    """
    raise NotImplementedError
