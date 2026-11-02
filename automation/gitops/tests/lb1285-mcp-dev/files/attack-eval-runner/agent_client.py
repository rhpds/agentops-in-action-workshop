#!/usr/bin/env python3
"""Talking to a participant's Hermes agent.

The runner reaches the agent ONLY through the same OpenAI-compatible chat endpoint the
participant's own UI uses. It has no privileged side channel into the sandbox, which is
deliberate and load-bearing: every effect an attack has is an effect the agent itself
was willing to produce when asked. It also means planting canary files needs no write
path — an eval simply asks the agent to write one.

ENDPOINT CONTRACT — read from manifests, NOT verified against a running agent. Confirm
before implementing:

  * tenant-platform/templates/ui.yaml sets AGENT_PROTOCOL: openai,
    AGENT_MODEL: hermes-agent, AGENT_URL -> Service `hermes-agent`
  * openshell runtime: port 8787 (tenant-openshell/values.yaml bridge.port). No bearer
    token — the relay strips Authorization and the gateway authenticates with mTLS.
  * pod runtime: port from agent.hermes.port, and the OpenAI-compatible endpoint needs
    the API_SERVER_KEY bearer from the hermes-env Secret.

The asymmetry is why ParticipantNamespace.agent_runtime exists, and why discovery.py
flags that nothing currently tells the runner which runtime a namespace uses.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass, field


@dataclass
class AgentTurnResult:
    """What came back from one chat turn.

    Attributes:
        text: The agent's reply.
        started_at / finished_at: Bracket the turn, used to find its trace.
        trace_id: Resolved after the fact by resolve_trace_id, not returned inline.
        transport_error: Set when the turn never completed — a timeout, a refused
            connection, a 5xx. Distinct from "the agent replied but refused": a
            transport error means the case could not be evaluated at all and must be
            scored as inconclusive rather than as a pass or a fail.
    """

    text: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    trace_id: str = None
    transport_error: str = None
    raw: dict = field(default_factory=dict)


class HermesAgentClient:
    """Chat client for one participant's agent."""

    def __init__(self, cfg, participant):
        raise NotImplementedError

    def send_turn(self, prompt):
        """Send one prompt, returning AgentTurnResult."""
        raise NotImplementedError

    def send_turns(self, prompts):
        """Send a multi-turn sequence in one conversation, returning the final result.

        Conversation continuity matters for the account-takeover case, where the second
        turn only makes sense in the context of the first.
        """
        raise NotImplementedError

    def resolve_trace_id(self, turn_result):
        """Find the MLflow trace for a completed turn. Returns a run/trace id or None.

        Hermes does not return its own trace id inline, which is why ui.yaml has the
        console do a follow-up MLflow lookup for exactly this. Same trick here: search
        the participant's inference experiment for the most recent run in the turn's
        time window.

        Inherently racy — the trace is exported asynchronously and may not have landed
        when this runs. Needs a bounded retry, and assertions that depend on trace
        evidence must treat "no trace yet" as inconclusive rather than as a pass.
        """
        raise NotImplementedError
