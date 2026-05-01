#!/usr/bin/env python3
"""Pretty-print the latest events from the daemon JSONL log."""
import json
import sys
import time
from pathlib import Path
from datetime import datetime


LOG_DIR = Path(__file__).parent / "logs"


def latest_log():
    files = sorted(LOG_DIR.glob("events-*.jsonl"))
    return files[-1] if files else None


def fmt_event(rec: dict) -> str:
    ts = rec.get("ts", "?")
    try:
        ts = datetime.fromisoformat(ts).strftime("%H:%M:%S.%f")[:-3]
    except Exception:
        pass
    kind = rec.get("kind", "?")
    if kind == "upnp_event":
        zone = rec.get("zone", "?")
        svc = rec.get("service", "?")
        seq = rec.get("seq", "?")
        v = rec.get("variables", {})
        # Highlight key state changes
        hi = []
        for k in ("transport_state", "current_track_uri", "zone_group_state",
                  "volume", "mute", "current_play_mode", "current_track_meta_data"):
            if k in v:
                val = str(v[k])[:60]
                hi.append(f"{k}={val}")
        return f"{ts}  {zone:14s} {svc:18s} seq={seq:>4} {' '.join(hi) if hi else list(v.keys())}"
    if kind == "mesh_poll":
        zone = rec.get("zone", "?")
        m = rec.get("mesh", {})
        phy = m.get("phy_errors_delta", "?")
        ch = m.get("channel_mhz", "?")
        nbrs = len(m.get("mesh_neighbors", []))
        return f"{ts}  {zone:14s} mesh             ch={ch} phy_err={phy} mesh_nbrs={nbrs}"
    if kind == "topology_snapshot":
        groups = rec.get("groups", [])
        s = "; ".join(f"{g.get('coord')}=>{g.get('members')}" for g in groups)
        return f"{ts}  TOPOLOGY: {s}"
    if kind == "discovery":
        names = [z["name"] for z in rec.get("zones", [])]
        return f"{ts}  DISCOVERY: {len(names)} zones: {names}"
    return f"{ts}  {kind}: {rec}"


def follow(path: Path):
    with open(path) as f:
        f.seek(0, 2)  # end
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.2)
                continue
            try:
                rec = json.loads(line)
                print(fmt_event(rec))
            except Exception as e:
                print(f"parse-err: {e} :: {line!r}")


def cat(path: Path, n: int):
    with open(path) as f:
        lines = f.readlines()
    for line in lines[-n:]:
        try:
            rec = json.loads(line)
            print(fmt_event(rec))
        except Exception:
            print(line.rstrip())


def main():
    path = latest_log()
    if not path:
        print(f"No event log found in {LOG_DIR}")
        sys.exit(1)
    if "-f" in sys.argv:
        cat(path, 50)
        print(f"--- following {path} ---")
        follow(path)
    else:
        n = 100
        for a in sys.argv[1:]:
            if a.lstrip("-").isdigit():
                n = int(a.lstrip("-"))
        cat(path, n)


if __name__ == "__main__":
    main()
