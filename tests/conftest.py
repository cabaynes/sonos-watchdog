import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from harness import State, load_blueprint  # noqa: E402

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
