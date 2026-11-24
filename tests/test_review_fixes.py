"""Fixes from the final review (2026-11-23): who owns the session, forgetting, restarts, queued runs."""
from conftest import BATH, BED, K, LR, O, ROAM, SPEAKERS7, make_state, make_trigger, render_bp

NOW = 1_763_900_000
MIN = 60


def h(*members, start=NOW - 600):
    return f"{start}|" + ",".join(members)


def grp(group, state="playing", since=NOW - 300):
    return {s: make_state(state, group=group, content="x-sonos-spotify:x", last_changed=since) for s in group}


def test_leaver_playing_alone_does_not_take_over(blueprint, speakers7):
    """C1: Kitchen left the group to play on its own; its settle must not rewrite the session."""
    st = {**grp([LR, O, ROAM]), **grp([K])}
    trig = make_trigger("settled", K, to_state=st[K], from_state=make_state("playing", group=[LR, K, O, ROAM]))
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, O, ROAM), trigger=trig, now=NOW)
    assert v["record"] is False
    assert v["log_events"] == []


def test_session_master_is_the_group_holding_the_leader_whatever_the_order(blueprint):
    """C1/probe D: with Kitchen listed first and playing alone, the session is still Living Room's."""
    order = [K, LR, O, ROAM, BED, BATH]
    st = {**grp([LR, O]), **grp([K]), ROAM: make_state("idle", group=[ROAM])}
    v = render_bp(blueprint, order, st, helper_value=h(LR, K, O, "!" + ROAM), trigger={"id": "sweep"}, now=NOW)
    assert v["session_master"] == LR
    assert v["missing"] == [ROAM]


def test_second_listener_does_not_replace_session(blueprint, speakers7):
    """I1: a podcast in the Bedroom while the Living Room session plays."""
    st = {**grp([LR, K, O]), **grp([BED])}
    trig = make_trigger("grew_or_started", BED, to_state=st[BED])
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, O), trigger=trig, now=NOW)
    assert v["new_session"] is False
    assert v["record"] is False
    assert v["log_events"] == []


def test_returning_offline_leader_keeps_its_mark(blueprint, speakers7):
    """I2: the old leader Kitchen went offline; Living Room now leads the rest; Kitchen comes back."""
    st = {**grp([LR, O, ROAM]), K: make_state("idle", group=[K])}
    trig = make_trigger("grew_or_started", LR, to_state=st[LR])
    v = render_bp(blueprint, speakers7, st, helper_value=h("!" + K, LR, O, ROAM), trigger=trig, now=NOW)
    assert v["new_session"] is False
    assert v["missing"] == [K]


def test_forget_after_quiet_period_on_sweep(blueprint, speakers7):
    """I3: forgetting works from the sweep using state age, so it survives HA restarts."""
    st = grp([LR, K], state="paused", since=NOW - 16 * MIN)
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, start=NOW - 3600), trigger={"id": "sweep"}, now=NOW)
    assert v["do_forget"] is True
    assert v["log_events"] == [{"event": "session_end", "subject": LR, "detail": "duration_s=3600"}]


def test_no_forget_before_quiet_period(blueprint, speakers7):
    st = grp([LR, K], state="paused", since=NOW - 5 * MIN)
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K), trigger={"id": "sweep"}, now=NOW)
    assert v["do_forget"] is False


def test_helper_respects_its_own_max_length(blueprint, speakers7):
    st = grp(SPEAKERS7)
    trig = make_trigger("grew_or_started", SPEAKERS7[0], to_state=st[SPEAKERS7[0]])
    v = render_bp(blueprint, speakers7, st, helper_value="", trigger=trig, now=NOW, helper_max=100)
    assert len(v["helper_value"]) <= 100
    assert any("helper full" in e["detail"] for e in v["log_events"])


def test_restored_unavailable_not_logged_on_startup(blueprint, speakers7):
    st = grp([LR, K])
    trig = make_trigger("came_online", O, to_state=make_state("idle", group=[O]),
                        from_state=make_state("unavailable", last_changed=NOW - 120, restored=True))
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K), trigger=trig, now=NOW)
    assert v["log_events"] == []


def test_restored_unavailable_not_marked_on_settle(blueprint, speakers7):
    st = {**grp([LR, K]), O: make_state("unavailable", restored=True)}
    trig = make_trigger("settled", LR, to_state=st[LR], from_state=make_state("playing", group=[LR, K, O]))
    v = render_bp(blueprint, speakers7, st, helper_value=h(LR, K, O), trigger=trig, now=NOW)
    assert v["new_offline"] == []


def test_queued_runs_recompute_decisions_when_they_start(blueprint):
    """I4: automation-level variables are rendered at trigger time; the run must re-render them."""
    first, second = blueprint["actions"][0], blueprint["actions"][1]
    assert first["variables"] == blueprint["variables"]
    assert second == {"condition": "template", "value_template": "{{ act }}"}
