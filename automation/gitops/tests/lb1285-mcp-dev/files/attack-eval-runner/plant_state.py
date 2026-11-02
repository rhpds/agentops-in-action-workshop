#!/usr/bin/env python3
"""Snapshot and restore simulated plant state.

Used only by unauthorized-control-action, the one attack that mutates real state when it
succeeds. Snapshot before the probe, restore the same values after — rather than
restarting plant-api, which would reset the entire simulated plant and discard whatever
the participant happened to be testing.

plant-api is a single replica with Recreate strategy holding state in memory behind an
asyncio lock (see the comment in tenant-platform/templates/plant-api.yaml explaining why
it must stay at exactly one replica), so there is exactly one authoritative plant per
participant and no replica skew to reconcile.

IDENTITY: restore needs the control-mcp roles the participant's `operator` user
deliberately lacks — set_pump_speed, start_pump, open_valve. The runner therefore needs
its own Keycloak identity per realm with those roles granted. Recommend a distinct
`attack-runner` user rather than reusing `operator`: reusing it would make attack traffic
indistinguishable from the participant's own in every trace they inspect, which is
precisely what modules 4 and 5 are teaching them to tell apart. Provisioning lives with
the realm import — see tenant-platform/templates/mcp-gateway.yaml.

SCAFFOLD: contracts only.
"""

from dataclasses import dataclass, field


@dataclass
class PlantSnapshot:
    """Plant readings captured before a destructive probe.

    Only the values a given attack can disturb are captured, named by the `captures`
    list in that attack's cleanup spec. Restoring a narrow set is the whole point —
    a blanket restore would stamp on unrelated participant changes just as a restart does.
    """

    captured_at: float = 0.0
    pump_status: dict = field(default_factory=dict)
    valve_positions: dict = field(default_factory=dict)
    partial: bool = False


def snapshot(participant, captures):
    """Read current state for the named captures. Returns PlantSnapshot.

    Uses the read tools the operator role already holds (get_all_pump_status,
    get_valve_positions). If a read fails, the snapshot is marked partial and the caller
    must NOT run the destructive probe: firing an attack whose damage cannot be undone
    is worse than skipping the case and scoring it inconclusive.
    """
    raise NotImplementedError


def restore(participant, snapshot_obj):
    """Write the snapshotted values back. Returns True when fully restored.

    Only writes values that actually differ from current readings — plant telemetry
    drifts on its own tick (PLANT_TICK_SECONDS), so a blind rewrite of every field would
    fight the simulation rather than undo the attack.
    """
    raise NotImplementedError
