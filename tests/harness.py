"""Render a blueprint's `variables:` the way Home Assistant does, against fixture states.

Only the parts of HA's template environment the blueprint uses are stubbed. Results are
parsed into native Python types with `ast.literal_eval`, mirroring HA's native-type rendering.
"""
import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import jinja2
import yaml


@dataclass(frozen=True)
class Input:
    name: str


@dataclass
class State:
    state: str
    attributes: dict = field(default_factory=dict)
    last_changed: float = 0.0


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!input", lambda loader, node: Input(loader.construct_scalar(node)))


def load_blueprint(path) -> dict:
    return yaml.load(Path(path).read_text(), Loader=_Loader)


def _native(text: str):
    s = text.strip()
    if s in ("None", "none", ""):
        return None if s != "" else ""
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return text


def _env(states: dict, now: float, devices: dict) -> jinja2.Environment:
    env = jinja2.Environment(undefined=jinja2.ChainableUndefined, extensions=["jinja2.ext.loopcontrols"])

    def st(eid):
        s = states.get(eid)
        return s.state if s else "unknown"

    def is_state(eid, value):
        cur = st(eid)
        return cur in value if isinstance(value, (list, tuple)) else cur == value

    def state_attr(eid, attr):
        s = states.get(eid)
        return s.attributes.get(attr) if s else None

    def as_timestamp(value, default=None):
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def device_id(eid):
        return eid if eid in devices else None

    def device_attr(dev, key):
        return (devices.get(dev) or {}).get(key)

    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    env.globals.update(
        states=st, is_state=is_state, state_attr=state_attr, now=lambda: now_dt,
        as_timestamp=as_timestamp, device_id=device_id, device_attr=device_attr, none=None,
    )
    env.filters.update(as_timestamp=as_timestamp)
    env.tests.update(is_state=is_state)
    return env


def _render(value, env, ctx):
    if isinstance(value, Input):
        return ctx["__inputs__"][value.name]
    if isinstance(value, str):
        if "{{" not in value and "{%" not in value:
            return value
        return _native(env.from_string(value).render(**ctx))
    if isinstance(value, list):
        return [_render(v, env, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _render(v, env, ctx) for k, v in value.items()}
    return value


def render_vars(blueprint: dict, inputs: dict, states: dict, trigger=None, now: float = 0.0,
                names=None, devices=None) -> dict:
    """Render `blueprint['variables']` in order; return {name: native value} (all, or only `names`)."""
    env = _env(states, now, devices or {})
    ctx = {"__inputs__": inputs, "trigger": trigger or {}}
    out = {}
    for name, value in (blueprint.get("variables") or {}).items():
        out[name] = _render(value, env, ctx)
        ctx[name] = out[name]
    return {k: out[k] for k in names} if names else out
