#!/usr/bin/env python3
"""Participant namespace discovery.

The runner is cluster-scoped and finds its own targets rather than being told about
them: bootstrap-tenant creates exactly as many tenants as RHDP provisions, with no
fixed list anywhere (see the comment in bootstrap-tenant/templates/applications.yaml),
so anything static would drift.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass


@dataclass
class ParticipantNamespace:
    """One participant's namespace and how to reach their agent.

    Attributes:
        username: From the `rhdp.redhat.com/participant` label value.
        namespace: `<username>-agentops`.
        agent_runtime: "openshell" or "pod". Determines both the agent's port and
            whether a bearer token is needed.

            UNRESOLVED: nothing on the namespace carries this today. The namespace
            object only has the participant label; the runtime is a Helm value
            (platform.hermesRuntime in bootstrap-tenant/values.yaml) that never reaches
            a cluster object the runner can read. Either bootstrap-tenant needs to add
            a label, or discovery needs to infer it from which Deployments exist
            (hermes-openshell-bridge vs hermes-agent). Inferring is possible but races
            a participant mid-rollout.
    """

    username: str
    namespace: str
    agent_runtime: str = "openshell"


def list_participant_namespaces(cfg):
    """List every participant namespace. Returns list[ParticipantNamespace].

    Called once per cycle rather than cached: participants can be provisioned while the
    lab is running, and a runner that cached the list at startup would never see them.
    """
    raise NotImplementedError
