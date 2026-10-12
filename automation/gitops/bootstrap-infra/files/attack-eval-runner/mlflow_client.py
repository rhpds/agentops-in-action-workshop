#!/usr/bin/env python3
"""MLflow REST client.

stdlib urllib, not the mlflow package — mirroring the mlflow_experiment_id / mlflow_token
helpers already in bridge-supervisor.sh, which talk to the same REST surface from bash.
Keeping this dependency-free is what lets the runner ship as a ConfigMap-mounted script
rather than needing its own image build.

TWO EXPERIMENTS PER PARTICIPANT, deliberately:

  <username>          The existing inference experiment. The runner NEVER writes here.
                      Attack and eval prompts land in it anyway, as ordinary traced
                      Hermes traffic, because that is what they are.

  <username>-cycle    One summary run per cycle, written by the runner. Low volume —
                      twelve runs an hour — so it stays readable, and keeps the cycle
                      rollups from burying the participant's own traces.

The cycle run cross-references traces in the inference experiment by id rather than
copying anything, so there is no duplicated data and nothing to keep in sync.

Authorisation is the same X-MLflow-Workspace header the bridge uses, which is why the
runner needs a Role in each tenant namespace (tenant-platform/templates/
attack-runner-rbac.yaml) rather than anything cluster-wide on MLflow itself.

SCAFFOLD: contracts only.
"""


class MLflowClient:
    """Minimal MLflow REST client scoped to one workspace."""

    def __init__(self, tracking_uri, workspace_namespace=None):
        raise NotImplementedError

    def get_or_create_experiment(self, name):
        """Resolve an experiment by name, creating it if absent. Returns experiment_id.

        Get-then-create races another writer creating the same experiment; treat an
        already-exists error as success and re-resolve, the way the bridge does.
        """
        raise NotImplementedError

    def log_cycle_summary(self, participant, cycle_id, results, cleanup_results):
        """Write one cycle's results as a single run in <username>-cycle.

        Shape, which the UI's status endpoint and leaderboard.py both read:

          params   participant, cycle_id, defs_revision
          metrics  attack.<id>   1.0 defended, 0.0 attack succeeded
                   eval.<id>     1.0 passed,   0.0 failed
                   cleanup.<attack-id>.attempted / .succeeded   0.0 / 1.0
                   score         composite, for leaderboard ranking
          tags     trace_ref.<id>  run id in the participant's inference experiment
                   inconclusive.<id>  reason, when a case could not be judged

        Inconclusive cases are logged as tags, NOT as a 0.0 metric. A metric of zero
        means "this failed"; a case the runner could not judge must not be recorded as
        a failure, or a participant gets penalised for the runner's own blind spots.
        """
        raise NotImplementedError

    def get_latest_cycle_run(self, experiment_name):
        """Most recent run in a cycle experiment. Returns a run dict or None.

        The UI status endpoint needs the same query; its `run_id` is the cursor the
        frontend compares against to decide whether an alert is new.
        """
        raise NotImplementedError

    def search_runs(self, experiment_id, filter_string=None, max_results=1, order_by=None):
        """Thin wrapper over the search-runs endpoint."""
        raise NotImplementedError
