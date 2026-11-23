"""Session/speaker event logging, the helper's value format, and source detection (spec: Logging)."""
import pytest

from conftest import K, LR, O, ROAM, make_state, make_trigger, render_bp

GROUP4 = [LR, K, O, ROAM]
NOW = 1_762_970_000


def playing(group, content="x-sonos-spotify:spotify%3atrack%3aabc", **extra):
    st = {s: make_state("playing", group=group, content=content) for s in group}
    st.update(extra)
    return st


@pytest.mark.parametrize("content,expected", [
    ("x-sonos-spotify:spotify%3atrack%3a67FOO?sid=12&flags=8232", "Spotify"),
    ("x-sonos-http:song%3a123.mp4?sid=204&flags=73768", "Apple Music"),
    ("x-sonos-vli:RINCON_X01400:1,airplay:ab12", "AirPlay"),
    ("x-sonos-htastream:RINCON_X01400:spdif", "TV"),
    ("x-rincon-mp3radio://stream.example/live", "Radio"),
    ("x-sonos-http:sonos%3aDZR%3aN%3a1%3ahead%3a0", "Radio"),
    ("x-rincon-stream:RINCON_X01400", "Line-in"),
    ("", "Other"),
])
def test_source_mapping(blueprint, speakers7, content, expected):
    v = render_bp(blueprint, speakers7, playing([LR, K], content=content), helper_value=f"{NOW}|{LR},{K}")
    assert v["source"] == expected


def test_helper_value_format(blueprint, speakers7):
    st = playing([LR, K])
    trig = make_trigger("grew_or_started", LR, to_state=st[LR])
    v = render_bp(blueprint, speakers7, st, helper_value="", trigger=trig, now=NOW)
    assert v["helper_value"] == f"{NOW}|media_player.living_room,media_player.kitchen"


def test_legacy_helper_value(blueprint, speakers7):
    legacy = f"{LR},{K}"
    v = render_bp(blueprint, speakers7, {}, helper_value=legacy)
    assert v["stored"] == {"start": None, "members": [LR, K], "offline": []}
    paused = {LR: make_state("paused", group=[LR, K]), K: make_state("paused", group=[LR, K])}
    trig = make_trigger("went_quiet", LR, to_state=paused[LR])
    v = render_bp(blueprint, speakers7, paused, helper_value=legacy, trigger=trig, now=NOW)
    ends = [e for e in v["log_events"] if e["event"] == "session_end"]
    assert len(ends) == 1 and "duration=unknown" in ends[0]["detail"]


def test_helper_truncates_at_entity_boundary(blueprint):
    many = [f"media_player.speaker_with_a_long_name_{i:02d}"[:30] for i in range(12)]
    assert all(len(s) == 30 for s in many)
    st = {s: make_state("playing", group=many, content="x-sonos-spotify:x") for s in many}
    trig = make_trigger("grew_or_started", many[0], to_state=st[many[0]])
    v = render_bp(blueprint, many, st, helper_value="", trigger=trig, now=NOW)
    value = v["helper_value"]
    assert len(value) <= 255
    members = value.split("|", 1)[1].split(",")
    assert members[0] == many[0] and all(m in many for m in members)
    assert any("helper full" in e["detail"] for e in v["log_events"])


def test_events_on_offline_leave(blueprint, speakers7):
    """An offline drop is logged by speaker_offline (at 10 s), not as speaker_left; settle marks it."""
    st = playing([LR, K, ROAM], **{O: make_state("unavailable")})
    trig = make_trigger("settled", LR, to_state=st[LR], from_state=make_state("playing", group=GROUP4))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW - 600}|" + ",".join(GROUP4), trigger=trig, now=NOW)
    assert not any(e["event"] == "speaker_left" for e in v["log_events"])
    assert f"!{O}" in v["helper_value"]


def test_events_on_online_leave(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("paused", group=[O])})
    trig = make_trigger("settled", LR, to_state=st[LR], from_state=make_state("playing", group=GROUP4))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW - 600}|" + ",".join(GROUP4), trigger=trig, now=NOW)
    assert v["log_events"][0] == {"event": "speaker_left", "subject": O,
                                  "detail": "online; leader=media_player.living_room"}
    assert "why=left on purpose" in v["log_events"][1]["detail"]


def test_events_on_back_online_repair(blueprint, speakers7):
    st = playing([LR, K, ROAM], **{O: make_state("paused", group=[O])})
    trig = make_trigger("back_online", O, to_state=st[O], from_state=make_state("unavailable", last_changed=NOW - 120))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW - 600}|{LR},{K},!{O},{ROAM}", trigger=trig, now=NOW)
    assert v["log_events"] == [{"event": "repair", "subject": O, "detail": f"path=back_online; leader={LR}"}]


def test_back_online_already_rejoined_by_sonos(blueprint, speakers7):
    """Sonos put it back itself: no repair (speaker_back is logged by the group-change trigger)."""
    st = playing(GROUP4)
    trig = make_trigger("back_online", O, to_state=st[O], from_state=make_state("unavailable", last_changed=NOW - 30))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW - 600}|{LR},{K},!{O},{ROAM}", trigger=trig, now=NOW)
    assert v["do_repair"] is False
    assert not any(e["event"] == "repair" for e in v["log_events"])


def test_session_start_event(blueprint, speakers7):
    st = playing([LR, K])
    trig = make_trigger("grew_or_started", LR, to_state=st[LR])
    v = render_bp(blueprint, speakers7, st, helper_value="", trigger=trig, now=NOW)
    assert v["log_events"] == [{"event": "session_start", "subject": LR,
                                "detail": f"leader={LR}; members={LR};{K}; source=Spotify; wired=n/a"}]
    v = render_bp(blueprint, speakers7, st, helper_value="", trigger=trig, now=NOW, wired_speakers=[LR])
    assert v["log_events"][0]["detail"].endswith("wired=yes")
    v = render_bp(blueprint, speakers7, st, helper_value="", trigger=trig, now=NOW, wired_speakers=[O])
    assert v["log_events"][0]["detail"].endswith("wired=no")


def test_went_offline_logged(blueprint, speakers7):
    st = playing([LR, K], **{O: make_state("unavailable")})
    trig = make_trigger("went_offline", O, to_state=st[O], from_state=make_state("paused", group=[O]))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW}|{LR},{K}", trigger=trig, now=NOW)
    assert v["log_events"] == [{"event": "speaker_offline", "subject": O, "detail": "in_session=no"}]


def test_session_end_duration(blueprint, speakers7):
    paused = {LR: make_state("paused", group=[LR, K]), K: make_state("paused", group=[LR, K])}
    trig = make_trigger("went_quiet", LR, to_state=paused[LR])
    v = render_bp(blueprint, speakers7, paused, helper_value=f"{NOW - 3600}|{LR},{K}", trigger=trig, now=NOW)
    assert v["log_events"] == [{"event": "session_end", "subject": LR, "detail": "duration_s=3600"}]
    assert v["do_forget"] is True


def test_still_offline_speaker_not_relogged(blueprint, speakers7):
    """Office went offline earlier and is still in the session; a later group change must not log it again."""
    st = playing([LR, K], **{O: make_state("unavailable"), ROAM: make_state("paused", group=[ROAM])})
    trig = make_trigger("settled", LR, to_state=st[LR], from_state=make_state("playing", group=[LR, K, ROAM]))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW - 600}|" + ",".join(GROUP4), trigger=trig, now=NOW)
    left = [e["subject"] for e in v["log_events"] if e["event"] == "speaker_left"]
    assert left == [ROAM]


def test_short_offline_blip_not_logged(blueprint, speakers7):
    """A handover makes HA mark speakers unavailable for ~2 s; that must not log as offline/online."""
    st = playing(GROUP4)
    trig = make_trigger("back_online", O, to_state=st[O], from_state=make_state("unavailable", last_changed=NOW - 2))
    v = render_bp(blueprint, speakers7, st, helper_value=f"{NOW - 600}|" + ",".join(GROUP4), trigger=trig, now=NOW)
    assert v["log_events"] == []
    assert v["act"] is False


def test_went_offline_waits_out_blips(blueprint):
    trig = next(t for t in blueprint["triggers"] if t["id"] == "went_offline")
    assert trig["for"]["seconds"] >= 10
