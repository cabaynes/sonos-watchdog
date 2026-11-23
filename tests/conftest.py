import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from harness import State, load_blueprint, render_vars  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT = ROOT / "blueprints" / "sonos_watchdog.yaml"

LR, K, O, ROAM, BED, BATH, MOVE = (f"media_player.{n}" for n in
                                   ("living_room", "kitchen", "office", "roam", "bedroom", "bathroom", "move"))
SPEAKERS7 = [LR, K, O, ROAM, BED, BATH, MOVE]
HELPER = "input_text.sonos_intended_speakers"


def make_state(state, group=None, content=None, last_changed=0.0, **attrs):
    a = dict(attrs)
    if group is not None:
        a["group_members"] = list(group)
    if content is not None:
        a["media_content_id"] = content
    return State(state, a, last_changed)


def ts(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def make_trigger(trig_id, entity_id, to_state=None, from_state=None):
    def as_dict(s):
        if s is None:
            return None
        return {"state": s.state, "attributes": s.attributes, "last_changed": ts(s.last_changed),
                "entity_id": entity_id}
    return {"id": trig_id, "entity_id": entity_id, "to_state": as_dict(to_state), "from_state": as_dict(from_state)}


@pytest.fixture
def speakers7():
    return list(SPEAKERS7)


@pytest.fixture
def blueprint():
    return load_blueprint(BLUEPRINT)


def render_bp(blueprint, speakers, states, helper_value="", trigger=None, now=1_000_000, devices=None, **inputs):
    """Render the watchdog blueprint's variables; unspecified speakers default to idle and solo."""
    states = dict(states)
    states[HELPER] = make_state(helper_value)
    for s in speakers:
        states.setdefault(s, make_state("idle", group=[s]))
    base = {"speakers": speakers, "intended_helper": HELPER, "settle_seconds": 60, "recovery_seconds": 3,
            "forget_minutes": 15, "log_notify": "", "counter_sessions": "", "counter_left": "",
            "counter_offline": "", "counter_repairs": "", "wired_speakers": [],
            "handover_command": "", "handover_after_pause": 30}
    base.update(inputs)
    return render_vars(blueprint, base, states, trigger=trigger, now=now, devices=devices)
