"""Only speakers marked as having gone offline are ever rejoined (live test 2026-11-23 found the
sweep could pull back a speaker the user removed, before the settle decision ran)."""
from conftest import BED, K, LR, O, ROAM, make_state, make_trigger, render_bp

GROUP4 = [LR, K, O, ROAM]
NOW = 1_763_900_000


def h(*members, start=NOW - 600):
    return f"{start}|" + ",".join(members)


def playing(group, **extra):
    st = {s: make_state("playing", group=group, content="x-sonos-spotify:x") for s in group}
    st.update(extra)
    return st


def test_online_leaver_not_repaired_before_settle(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("paused", group=[O])})
    v = render_bp(blueprint, speakers7, st, helper_value=h(*GROUP4), trigger={"id": "sweep"}, now=NOW)
    assert v["missing"] == []
    assert v["do_repair"] is False


def test_marked_speaker_is_missing(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("idle", group=[O])})
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, "!" + O, ROAM), trigger={"id": "sweep"}, now=NOW)
    assert v["stored"]["offline"] == [O]
    assert v["stored"]["members"] == GROUP4
    assert v["missing"] == [O]
    assert v["log_events"] == [{"event": "repair", "subject": O, "detail": f"path=sweep; leader={LR}"}]


def test_went_offline_marks_session_member(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("unavailable")})
    trig = make_trigger("went_offline", O, to_state=st[O], from_state=make_state("playing", group=GROUP4))
    v = render_bp(blueprint, speakers7, st, helper_value=h(*GROUP4), trigger=trig, now=NOW)
    assert v["record"] is True
    assert v["helper_value"] == h(LR, K, "!" + O, ROAM)
    assert v["log_events"] == [{"event": "speaker_offline", "subject": O, "detail": "in_session=yes"}]


def test_went_offline_outside_session_no_record(blueprint, speakers7):
    st = playing(GROUP4, **{BED: make_state("unavailable")})
    trig = make_trigger("went_offline", BED, to_state=st[BED])
    v = render_bp(blueprint, speakers7, st, helper_value=h(*GROUP4), trigger=trig, now=NOW)
    assert v["record"] is False


def test_settle_keeps_marked_speaker_that_is_back_but_not_rejoined(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("idle", group=[O])})
    trig = make_trigger("settled", LR, to_state=st[LR], from_state=make_state("playing", group=GROUP4))
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, "!" + O, ROAM), trigger=trig, now=NOW)
    assert O in v["new_members"]
    assert v["departed_online"] == []


def test_marked_speaker_back_in_group_unmarks_and_logs(blueprint, speakers7):
    st = playing(GROUP4)
    trig = make_trigger("grew_or_started", LR, to_state=st[LR])
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, "!" + O, ROAM), trigger=trig, now=NOW)
    assert v["record"] is True
    assert "!" not in v["helper_value"]
    assert {"event": "speaker_back", "subject": O, "detail": f"leader={LR}"} in v["log_events"]


def test_came_online_logs_speaker_online(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("idle", group=[O])})
    trig = make_trigger("came_online", O, to_state=st[O], from_state=make_state("unavailable", last_changed=NOW - 300))
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, "!" + O, ROAM), trigger=trig, now=NOW)
    assert v["log_events"] == [{"event": "speaker_online", "subject": O, "detail": "offline_s=300"}]


def test_came_online_blip_not_logged(blueprint, speakers7):
    st = playing(GROUP4)
    trig = make_trigger("came_online", O, to_state=st[O], from_state=make_state("unavailable", last_changed=NOW - 2))
    v = render_bp(blueprint, speakers7, st, helper_value=h(*GROUP4), trigger=trig, now=NOW)
    assert v["log_events"] == []
    assert v["act"] is False


def test_sweep_waits_for_recovery_delay_after_speaker_returns(blueprint, speakers7):
    """Don't join a speaker that came back a second ago — it may not accept commands yet."""
    st = playing([LR, K, ROAM], **{O: make_state("idle", group=[O], last_changed=NOW - 1)})
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, "!" + O, ROAM), trigger={"id": "sweep"}, now=NOW)
    assert v["missing"] == []
    st[O] = make_state("idle", group=[O], last_changed=NOW - 10)
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, "!" + O, ROAM), trigger={"id": "sweep"}, now=NOW)
    assert v["missing"] == [O]
