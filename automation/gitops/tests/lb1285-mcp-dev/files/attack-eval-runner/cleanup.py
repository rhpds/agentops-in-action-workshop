#!/usr/bin/env python3
"""Undoing a successful attack.

Runs only when an attack actually succeeded — the participant was not defended and real
damage was done. Four of the seven attacks are pure information or behaviour probes and
need nothing here.

The primitives are a closed enum, selected by `cleanup.type` in the definition YAML.
Definitions carry parameters, never code: those files are meant for lab content authors
to extend, and that surface must not become a place arbitrary code runs unattended
against a live participant's cluster every five minutes.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass

import plant_state


@dataclass
class CleanupResult:
    """What cleanup did, logged per attack alongside the attack's own metric.

    Attributes:
        attempted: Whether cleanup ran at all.
        succeeded: Whether verification confirmed it worked. None when unverified.
        detail: Human-readable outcome for the UI's results panel.
    """

    attempted: bool = False
    succeeded: bool = None
    detail: str = ""


def run_cleanup(cleanup_spec, context):
    """Dispatch on cleanup_spec.type, then verify. Returns CleanupResult.

    Verification re-checks the world rather than trusting the primitive's return value —
    "did the pump actually go back" is a different question from "did the restore call
    return 200". The `verify` block in the definition reuses the assertion vocabulary
    for exactly this.

    A cleanup failure never aborts the cycle. It is logged, and the participant's
    remaining results for that cycle are flagged lower-confidence, since state that
    later cases depend on is known to be dirty.
    """
    raise NotImplementedError


def _none(spec, context):
    """Nothing to undo. Records that this was a deliberate no-op."""
    raise NotImplementedError


def _canary_reseed(spec, context):
    """Nothing to restore — the destroyed artifact was a runner-planted decoy.

    The next cycle's write-report eval plants a fresh canary as its normal output, so
    there is no repair step at all. This primitive exists to record that fact, so the
    metric distinguishes "no cleanup needed by design" from "cleanup not implemented" —
    two very different things to see on a dashboard.
    """
    raise NotImplementedError


def _plant_state_restore(spec, context):
    """Write back the values captured before the probe. Delegates to plant_state.restore."""
    raise NotImplementedError
