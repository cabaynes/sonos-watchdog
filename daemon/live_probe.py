#!/usr/bin/env python3
"""Snapshot recent group/transport activity from the daemon log + probe
live playback health (is position actually advancing, or stalled?)."""
import re, json, time, glob
from datetime import datetime, timezone, timedelta
import soco

cutoff = datetime.now(timezone.utc) - timedelta(minutes=20)
print("=== daemon log: last ~20 min (group changes + transport states) ===")
rows = []
for path in sorted(glob.glob("logs/events-*.jsonl"))[-2:]:
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
                t = datetime.fromisoformat(r.get("ts"))
            except Exception:
                continue
            if t < cutoff:
                continue
            if r.get("kind") == "topology_snapshot":
                multi = [f"{g['coord']}<-{[m for m in g['members'] if m != g['coord']]}"
                         for g in r.get("groups", []) if len(set(g.get("members", []))) > 1]
                rows.append((t, "GROUP", "; ".join(multi) if multi else "(all standalone)"))
            elif r.get("kind") == "upnp_event" and r.get("service") == "avTransport":
                v = r.get("variables", {}) or {}
                st = v.get("transport_state") or v.get("TransportState")
                if st:
                    rows.append((t, "STATE", f"{r.get('zone')} -> {st}"))
for t, k, msg in rows[-30:]:
    print(t.astimezone().strftime("%H:%M:%S"), f"{k:6s}", msg)

print("\n=== live state now ===")
zones = {z.player_name: z for z in (soco.discover(timeout=8) or [])}
seen = set()
print("current groups:")
for z in zones.values():
    g = z.group
    if g.uid in seen:
        continue
    seen.add(g.uid)
    members = sorted(m.player_name for m in g.members)
    print(f"  {g.coordinator.player_name} <- {members}")

for name in ("Office", "Roam"):
    z = zones.get(name)
    if not z:
        print(f"\n{name}: NOT FOUND in discovery")
        continue
    coord = z.group.coordinator
    try:
        state = coord.get_current_transport_info().get("current_transport_state")
    except Exception as e:
        state = f"err {e}"
    print(f"\n{name}: coordinator={coord.player_name}  state={state}")
    try:
        ti0 = coord.get_current_track_info()
        time.sleep(6)
        ti1 = coord.get_current_track_info()
        uri = (ti0.get("uri") or "")[:55]
        print(f"  track   : {ti0.get('title')!r}")
        print(f"  uri     : {uri}")
        print(f"  position: {ti0.get('position')} -> {ti1.get('position')}  (must advance if truly playing)")
    except Exception as e:
        print(f"  track err: {e}")
