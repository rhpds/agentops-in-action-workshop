#!/usr/bin/env python3
"""Runner configuration, from environment variables.

Stdlib only, like the other scripts in this repo. Everything is injected by the
Deployment in bootstrap-infra/templates/attack-eval-runner.yaml.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass, field


@dataclass
class RunnerConfig:
    """Everything the runner needs to know, resolved once at startup.

    Attributes:
        cycle_interval_seconds: Seconds between cycles. Default 300 (five minutes).
        participant_label: Namespace label identifying a participant namespace.
            `rhdp.redhat.com/participant`, set by bootstrap-tenant's namespace.yaml.
        defs_dir: Where the attack/eval YAML is mounted from the ConfigMap.
        mlflow_tracking_uri: Shared MLflow. The same instance the bridge writes traces to.
        cycle_experiment_suffix: Appended to the username to name the per-participant
            cycle experiment. `-cycle` by default, giving `<username>-cycle`. The UI
            resolves the same name from MLFLOW_CYCLE_EXPERIMENT — change one and you
            must change the other, the same coupling ui.yaml already documents for
            MLFLOW_EXPERIMENT.
        leaderboard_experiment: Experiment in the shared namespace holding leaderboard
            standings.
        shared_namespace: Where the runner itself runs. Used for its own MLflow writes.
        once: Run a single cycle and exit.
        request_timeout_seconds: Per-turn timeout talking to a participant's agent. A
            sandboxed agent that is denied network access can hang rather than fail fast,
            and one participant's hung agent must not stall the cycle for everyone else.
    """

    cycle_interval_seconds: int = 300
    participant_label: str = "rhdp.redhat.com/participant"
    defs_dir: str = "/config/defs"
    mlflow_tracking_uri: str = ""
    cycle_experiment_suffix: str = "-cycle"
    leaderboard_experiment: str = "agentops-leaderboard"
    shared_namespace: str = ""
    once: bool = False
    request_timeout_seconds: int = 120
    disabled_case_ids: list = field(default_factory=list)


def load_config(argv=None):
    """Build a RunnerConfig from environment and argv. Returns RunnerConfig."""
    raise NotImplementedError
