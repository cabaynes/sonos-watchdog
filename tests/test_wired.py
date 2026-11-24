"""Wired speaker takes the lead during a pause (spec: Wired speaker leads; gate passed 2026-11-23)."""
from conftest import K, LR, O, ROAM, make_state, make_trigger, render_bp

GROUP4 = [K, LR, O, ROAM]  # Kitchen leads
NOW = 1_763_900_000
DEVICES = {
    K: {"configuration_url": "http://192.0.2.12:1400/support/review",
        "identifiers": {("sonos", "RINCON_KITCHEN01400")}},
    LR: {"configuration_url": "http://192.0.2.16:1400/support/review",
         "identifiers": {("sonos", "RINCON_LIVINGROOM01400")}},
}
HANDOVER = {"wired_speakers": [LR], "handover_command": "rest_command.sonos_delegate", "handover_after_pause": 30}


def paused_group(group, content="x-sonos-spotify:spotify%3atrack%3aabc", **extra):
    st = {s: make_state("paused", group=group, content=content) for s in group}
    st.update(extra)
    return st


def render(blueprint, speakers7, states, trig_entity, tid="paused_long", **inputs):
    trig = make_trigger(tid, trig_entity, to_state=states.get(trig_entity))
    merged = dict(HANDOVER)
    merged.update(inputs)
    return render_bp(blueprint, speakers7, states, helper_value=f"{NOW - 600}|" + ",".join(GROUP4),
                     trigger=trig, now=NOW, devices=DEVICES, **merged)


def test_handover_target_when_leader_not_wired(blueprint, speakers7):
    v = render(blueprint, speakers7, paused_group(GROUP4), K)
    assert v["handover_target"] == LR
    assert v["do_handover"] is True
    assert {"event": "leader_moved", "subject": LR, "detail": f"from={K}; to={LR}"} in v["log_events"]


def test_handover_ip_uid_from_device_registry(blueprint, speakers7):
    v = render(blueprint, speakers7, paused_group(GROUP4), K)
    assert v["handover_ip"] == "192.0.2.12"
    assert v["handover_uid"] == "RINCON_LIVINGROOM01400"


def test_no_handover_when_wired_leads(blueprint, speakers7):
    group = [LR, K, O, ROAM]
    v = render(blueprint, speakers7, paused_group(group), LR)
    assert v["handover_target"] is None
    assert v["do_handover"] is False


def test_no_handover_when_wired_unavailable(blueprint, speakers7):
    st = paused_group([K, O, ROAM], **{LR: make_state("unavailable")})
    st[K] = make_state("paused", group=[K, LR, O, ROAM])
    v = render(blueprint, speakers7, st, K)
    assert v["handover_target"] is None


def test_no_handover_while_playing(blueprint, speakers7):
    st = {s: make_state("playing", group=GROUP4, content="x-sonos-spotify:x") for s in GROUP4}
    v = render(blueprint, speakers7, st, K)
    assert v["do_handover"] is False


def test_no_handover_from_a_member(blueprint, speakers7):
    """Every member reports 'paused'; only the leader's trigger may hand over."""
    v = render(blueprint, speakers7, paused_group(GROUP4), O)
    assert v["do_handover"] is False


def test_no_handover_without_command(blueprint, speakers7):
    v = render(blueprint, speakers7, paused_group(GROUP4), K, handover_command="")
    assert v["handover_target"] == LR
    assert v["do_handover"] is False
    assert not any(e["event"] == "leader_moved" for e in v["log_events"])


def test_tv_session_source_and_no_handover(blueprint, speakers7):
    st = paused_group([K, LR], content="x-sonos-htastream:RINCON_LIVINGROOM01400:spdif")
    v = render(blueprint, speakers7, st, K)
    assert v["source"] == "TV"
    assert v["handover_target"] is None
