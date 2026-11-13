from harness import Input, State, render_vars


def test_render_vars_native_types():
    bp = {"variables": {
        "a": "{{ [1,2] }}",
        "b": "{{ a | length }}",
        "c": "{{ none }}",
        "d": Input("x"),
    }}
    out = render_vars(bp, inputs={"x": "hi"}, states={}, trigger=None, now=0)
    assert out == {"a": [1, 2], "b": 2, "c": None, "d": "hi"}


def test_state_stubs():
    states = {"media_player.k": State("paused", {"group_members": ["media_player.k"]}, 0)}
    bp = {"variables": {
        "p": "{{ is_state('media_player.k', 'paused') }}",
        "g": "{{ state_attr('media_player.k', 'group_members') }}",
        "missing": "{{ states('media_player.nope') }}",
    }}
    out = render_vars(bp, inputs={}, states=states, trigger=None, now=0)
    assert out["p"] is True
    assert out["g"] == ["media_player.k"]
    assert out["missing"] == "unknown"
