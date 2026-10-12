#!/usr/bin/env python3
"""Leaderboard aggregation.

Reads the latest cycle run from every participant's <username>-cycle experiment and
publishes a ranking into a single shared experiment, so the standings survive the
runner restarting and can be read by anything that can read MLflow.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass


@dataclass
class LeaderboardEntry:
    """One participant's standing.

    Attributes:
        username: Participant.
        attacks_defended / attacks_total: Excludes inconclusive and disabled cases, so
            the denominator can differ between participants in the same cycle. Show it
            rather than assuming it is constant.
        evals_passed / evals_total: Same.
        score: Composite used for ranking.
        cycle_id / run_id: Which cycle this came from. A participant whose agent was
            down has a stale entry, and the UI should say so rather than implying they
            are currently at that score.
    """

    username: str
    attacks_defended: int = 0
    attacks_total: int = 0
    evals_passed: int = 0
    evals_total: int = 0
    score: float = 0.0
    cycle_id: str = ""
    run_id: str = ""


def compute_leaderboard(mlflow, participants):
    """Build ranked standings from each participant's latest cycle. Returns list.

    UNRESOLVED — the ranking formula. The options behave differently in ways that
    matter for how participants play:

      * plain pass rate: easy to explain, but treats a high-severity authorisation
        bypass as equal to a missed doc redirect
      * severity-weighted: uses the `weight` already in every definition, so the
        hard attacks dominate the ranking
      * attacks-only: ignores evals entirely, which rewards the participant who
        denies everything and breaks their agent — the exact failure mode modules 4
        through 6 are built to punish

    Recommend severity-weighted across BOTH attacks and evals, so a bricked agent
    cannot win. Needs a decision before implementation.
    """
    raise NotImplementedError


def publish_leaderboard(mlflow, entries, cfg):
    """Write standings to the shared leaderboard experiment as one run per cycle."""
    raise NotImplementedError
