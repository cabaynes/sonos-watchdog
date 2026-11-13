#!/usr/bin/env python3
"""Watch one speaker's group for a few minutes and flag visible trouble.

Flags, with timestamps:
  NOTPLAY    the leader's transport left PLAYING
  STALL      PLAYING but the track position isn't advancing
  LEFT       the watched speaker left the group
  RECONNECT  an AirPlay session restarted (its session token changed)
  SLOW       the leader took over 2 s to answer (network trouble)

It cannot see the silent dropouts where a satellite stays in the group but plays nothing:
the leader reports PLAYING and an advancing position throughout (see FINDINGS.md).

Usage:  python3 watch_group.py --speaker "Kitchen" [--seconds 180] [--every 3]
"""
import argparse
import re
import sys
import time

import soco


def secs(pos):
    try:
        parts = [int(x) for x in (pos or "").split(":")]
    except ValueError:
        return None
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts))) if parts else None


def airplay_token(uri: str):
    m = re.search(r"airplay:([0-9a-fA-F]+)", uri or "")
    return m.group(1) if m else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Watch a Sonos group for visible trouble.")
    ap.add_argument("--speaker", required=True, help="room name as shown in the Sonos app")
    ap.add_argument("--seconds", type=int, default=180)
    ap.add_argument("--every", type=float, default=3)
    args = ap.parse_args(argv)

    zones = {z.player_name: z for z in (soco.discover(timeout=8) or [])}
    sp = zones.get(args.speaker)
    if not sp:
        print(f"{args.speaker!r} not found. Speakers: {sorted(zones)}")
        return 1
    leader = sp.group.coordinator
    uri = leader.get_current_track_info().get("uri") or ""
    print(f"group: {sorted(m.player_name for m in sp.group.members if m.is_visible)}  leader: {leader.player_name}")
    print(f"source: {uri[:60]}\nwatching {args.seconds} s, every {args.every} s — only trouble and heartbeats shown\n")

    t0, prev_pos, prev_tok, bad, n = time.time(), None, airplay_token(uri), 0, 0
    while time.time() - t0 < args.seconds:
        q = time.time()
        try:
            leader = sp.group.coordinator
            state = leader.get_current_transport_info().get("current_transport_state")
            info = leader.get_current_track_info()
            members = [m.player_name for m in sp.group.members]
        except Exception:
            state, info, members = "ERR", {}, []
        lat, el = time.time() - q, int(time.time() - t0)
        pos, tok = secs(info.get("position")), airplay_token(info.get("uri"))
        flags = []
        if state not in ("PLAYING", None):
            flags.append(f"NOTPLAY({state})")
        if state == "PLAYING" and pos is not None and prev_pos is not None and pos - prev_pos <= 0:
            flags.append("STALL")
        if members and args.speaker not in members:
            flags.append("LEFT")
        if prev_tok and tok and tok != prev_tok:
            flags.append("RECONNECT")
        if lat > 2:
            flags.append(f"SLOW({lat:.1f}s)")
        if flags:
            bad += 1
            print(f"  t={el:>4}s  {' '.join(flags)}", flush=True)
        elif n % 10 == 0:
            print(f"  t={el:>4}s  ok ({state}, position {info.get('position')})", flush=True)
        prev_pos, prev_tok, n = pos, tok, n + 1
        time.sleep(args.every)
    print(f"\n{bad} of {n} samples flagged. A STALL right after a track change is normal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
