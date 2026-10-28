#!/usr/bin/env python3
"""Attack and evaluation runner — entrypoint and cycle loop.

Runs one attack/eval cycle against every participant every CYCLE_INTERVAL_SECONDS,
logs the outcome to that participant's own MLflow cycle experiment, and republishes
the leaderboard.

Why an in-process loop and not a CronJob: the same reason mcp-token-refresh.py gives
for the token refresher — "runs as an in-process background loop instead of an external
CronJob". A single long-running Deployment is also what lets one process hold the
per-participant plant-state snapshots across the attack/cleanup pair without persisting
them anywhere.

Single replica, no leader election. Two replicas would double every participant's attack
traffic and race each other's plant-state restores.

SCAFFOLD: structure and contracts only. No function below has an implementation.
"""

import sys

import cleanup
import config
import defs_loader
import discovery
import executor
import leaderboard
import mlflow_client
import plant_state


def run_cycle(cfg, attack_defs, eval_defs, clients):
    """Run one full cycle across every participant.

    Ordering within a participant matters and is not incidental:

      1. Evals that declare `plants_canary` run first, so the artifacts the destructive
         attacks target exist before those attacks run.
      2. Attacks run next. An attack whose canary-planting eval failed is skipped, not
         scored — scoring it would credit the participant for a deletion that could not
         have happened.
      3. Remaining evals run last, after cleanup, so they see restored state.

    Participants are independent; a failure against one must not abort the cycle for
    the rest. Each participant's result set is logged as its own MLflow run even when
    partially failed, so a participant whose agent is down still gets a scored cycle
    rather than silently vanishing from the leaderboard.
    """
    raise NotImplementedError


def run_participant_cycle(cfg, participant, attack_defs, eval_defs, clients):
    """Run the attack and eval set against one participant, returning CycleResult.

    The attack/cleanup pair for destructive cases is:

        snapshot = plant_state.snapshot(...)      # before the probe, if the def needs it
        result   = executor.run_attack(...)
        if result.attack_succeeded and attack.cleanup.type != "none":
            cleanup.run_cleanup(attack.cleanup, snapshot, ...)

    Cleanup failure is logged and the cycle continues. It does not abort the remaining
    cases, but it does mark the rest of this participant's results this cycle as
    lower-confidence: state the later cases depend on is known to be dirty.
    """
    raise NotImplementedError


def main(argv=None):
    """Parse config, load definitions, then loop until killed.

    `--once` runs a single cycle and exits, for local iteration against one namespace —
    mirroring the seed/loop split in mcp-token-refresh.py.
    """
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
