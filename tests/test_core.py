"""Session detection, the record rule, and repair targeting (spec: The design / record rule)."""
from conftest import BATH, BED, K, LR, O, ROAM, make_state, make_trigger, render_bp

GROUP4 = [LR, K, O, ROAM]


def render(blueprint, speakers7, states, helper_value="", trigger=None, now=1_000_000):
    return render_bp(blueprint, speakers7, states, helper_value, trigger, now)


def playing_group(group, **extra):
    st = {s: make_state("playing", group=group) for s in group}
    st.update(extra)
    return st


def test_two_speaker_drop_master_found(blueprint, speakers7):
    states = {LR: make_state("playing", group=[LR]), K: make_state("paused", group=[K])}
    v = render(blueprint, speakers7, states, helper_value=f"{LR},{K}")
    assert v["session_master"] == LR
    assert v["missing"] == [K]


def test_paused_member_counts_as_missing(blueprint, speakers7):
    states = playing_group([LR, K, ROAM], **{O: make_state("paused", group=[O])})
    v = render(blueprint, speakers7, states, helper_value=",".join(GROUP4))
    assert v["missing"] == [O]


def test_busy_speaker_never_missing(blueprint, speakers7):
    # Bedroom plays its own thing; Bathroom is grouped under someone else's (paused) session.
    states = playing_group([LR, K], **{
        BED: make_state("playing", group=[BED]),
        BATH: make_state("paused", group=[O, BATH]),
        O: make_state("paused", group=[O, BATH]),
    })
    v = render(blueprint, speakers7, states, helper_value=",".join([LR, K, BED, BATH, O]))
    assert v["session_master"] == LR
    assert v["missing"] == []


def test_online_leaver_dropped_on_settle(blueprint, speakers7):
    states = playing_group([LR, K, ROAM], **{O: make_state("paused", group=[O])})
    trig = make_trigger("settled", LR, to_state=states[LR], from_state=make_state("playing", group=GROUP4))
    v = render(blueprint, speakers7, states, helper_value=",".join(GROUP4), trigger=trig)
    assert v["new_members"] == [LR, K, ROAM]
    assert v["departed_online"] == [O]
    assert v["departed_offline"] == []
    assert v["record"] is True


def test_offline_leaver_kept_on_settle(blueprint, speakers7):
    states = playing_group([LR, K, ROAM], **{O: make_state("unavailable")})
    trig = make_trigger("settled", LR, to_state=states[LR], from_state=make_state("playing", group=GROUP4))
    v = render(blueprint, speakers7, states, helper_value=",".join(GROUP4), trigger=trig)
    assert v["new_members"] == [LR, K, ROAM, O]
    assert v["departed_offline"] == [O]
    assert v["departed_online"] == []


def test_ungroup_to_one_room_records_solo(blueprint, speakers7):
    states = {LR: make_state("playing", group=[LR]),
              K: make_state("paused", group=[K]), O: make_state("paused", group=[O]),
              ROAM: make_state("paused", group=[ROAM])}
    trig = make_trigger("settled", LR, to_state=states[LR], from_state=make_state("playing", group=GROUP4))
    v = render(blueprint, speakers7, states, helper_value=",".join(GROUP4), trigger=trig)
    assert v["new_members"] == [LR]
    after = render(blueprint, speakers7, states, helper_value=LR)
    assert after["missing"] == []


def test_new_preset_replaces_session(blueprint, speakers7):
    states = {K: make_state("playing", group=[K, BED]), BED: make_state("playing", group=[K, BED])}
    trig = make_trigger("grew_or_started", K, to_state=states[K])
    v = render(blueprint, speakers7, states, helper_value=",".join(GROUP4), trigger=trig)
    assert v["new_members"] == [K, BED]
    assert v["record"] is True


def test_shrink_not_recorded_before_settle(blueprint, speakers7):
    states = playing_group([LR, K, ROAM], **{O: make_state("paused", group=[O])})
    trig = make_trigger("grew_or_started", LR, to_state=states[LR])
    v = render(blueprint, speakers7, states, helper_value=",".join(GROUP4), trigger=trig)
    assert v["record"] is False


def test_restart_mid_session_no_action(blueprint, speakers7):
    v = render(blueprint, speakers7, playing_group(GROUP4), helper_value=",".join(GROUP4))
    assert v["session_master"] == LR
    assert v["missing"] == []


def test_no_session_no_master(blueprint, speakers7):
    v = render(blueprint, speakers7, {}, helper_value="")
    assert v["session_master"] is None
    assert v["missing"] == []


def test_idle_sweep_does_not_act(blueprint, speakers7):
    """A sweep with nothing to do must not run actions (else HA logs 'triggered' every 10 s)."""
    trig = {"id": "sweep"}
    v = render(blueprint, speakers7, playing_group(GROUP4), helper_value=",".join(GROUP4), trigger=trig)
    assert v["act"] is False
