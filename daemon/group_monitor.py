#!/usr/bin/env python3
"""Watch the group that contains Office (coordinator-aware) for drops.
Flags: position stall, state leaving PLAYING, Office dropping out of the
group, or the speaker going unreachable (SLOW)."""
import re, time, soco

GAP, N = 4, 30  # ~120s

def secs(p):
    if not p or p in ("NOT_IMPLEMENTED", ""):
        return None
    try:
        a = [int(x) for x in p.split(":")]
    except Exception:
        return None
    return a[0]*3600+a[1]*60+a[2] if len(a) == 3 else (a[0]*60+a[1] if len(a) == 2 else None)

zones = {z.player_name: z for z in (soco.discover(timeout=8) or [])}
off = zones.get("Office")
if not off:
    print("Office not found"); raise SystemExit
coord = off.group.coordinator
print("group       :", sorted(m.player_name for m in off.group.members),
      "| coordinator:", coord.player_name)
uri = coord.get_current_track_info().get("uri") or ""
src = "AirPlay" if "airplay" in uri else ("Spotify(native)" if "spotify" in uri else uri[:40])
print("source      :", src)
print(f"\nwatching the group ~{GAP*N}s, every {GAP}s. Only drops + heartbeats shown.\n")

prev = None; bad = 0; t0 = time.time()
for i in range(N):
    q = time.time()
    try: st = coord.get_current_transport_info().get("current_transport_state")
    except Exception: st = "ERR"
    try: pos = secs(coord.get_current_track_info().get("position"))
    except Exception: pos = None
    try: members = sorted(m.player_name for m in coord.group.members)
    except Exception: members = []
    lat = time.time() - q
    el = int(time.time() - t0)
    dp = (pos - prev) if (pos is not None and prev is not None) else None
    flags = []
    if st not in ("PLAYING", None): flags.append(f"NOTPLAY({st})")
    if st == "PLAYING" and dp is not None and dp <= 0: flags.append("STALL(silent)")
    elif st == "PLAYING" and dp is not None and dp < GAP*0.5: flags.append(f"STUTTER(+{dp}s)")
    if "Office" not in members: flags.append("OFFICE-LEFT-GROUP")
    if lat > 2: flags.append(f"SLOW({lat:.1f}s)")
    if flags:
        print(f"  t={el:>3}s  {' '.join(flags)}  members={members}", flush=True); bad += 1
    elif i % 5 == 0:
        print(f"  t={el:>3}s  ok (state={st}, pos={pos}, members={len(members)})", flush=True)
    prev = pos
    if i < N-1:
        time.sleep(GAP)
print(f"\n=== summary: {bad}/{N} bad samples over {int(time.time()-t0)}s ===")
