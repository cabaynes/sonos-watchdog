#!/usr/bin/env python3
"""Live-watch ONE speaker's AirPlay playback for ~3 min, fine-grained.

Flags three failure signatures, with timestamps:
  - STALL    : state=PLAYING but track position not advancing (silent audio)
  - NOTPLAY  : transport state left PLAYING (PAUSED/STOPPED/TRANSITIONING)
  - RECONNECT: the AirPlay session token changed = the stream dropped & re-established
  - SLOW     : the speaker took >2s to answer = network unreachable for a moment
Also reports mesh PHY-error rate (Office + Arc) across the window.
"""
import re, time
import requests, soco

TARGET = "Office"
GAP, N = 3, 60          # ~180s
SLOW = 2.0

def secs(p):
    if not p or p in ("NOT_IMPLEMENTED", ""):
        return None
    try:
        a = [int(x) for x in p.split(":")]
    except Exception:
        return None
    return a[0]*3600+a[1]*60+a[2] if len(a) == 3 else (a[0]*60+a[1] if len(a) == 2 else None)

def phy(ip):
    try:
        t = requests.get(f"http://{ip}:1400/status/proc/ath_rincon/status", timeout=5).text
        m = re.search(r"PHY errors since last reading/reset:\s*(\d+)", t)
        return int(m.group(1)) if m else None
    except Exception:
        return None

zones = {z.player_name: z for z in (soco.discover(timeout=8) or [])}
sp, arc = zones.get(TARGET), zones.get("Living Room")
if not sp:
    print(f"{TARGET} not found"); raise SystemExit

def token():
    try:
        return (re.search(r"airplay:([0-9a-fA-F]+)", sp.get_current_track_info().get("uri") or "") or [None, None])[1]
    except Exception:
        return None

print("source uri  :", (sp.get_current_track_info().get("uri") or "")[:60])
print(f"watching {TARGET} ~{GAP*N}s, sampling every {GAP}s. Only drops + heartbeats shown.\n")
o0, a0 = phy(sp.ip_address), (phy(arc.ip_address) if arc else None)
t0 = time.time()
prev_pos, prev_tok = None, token()
events = []
for i in range(N):
    q = time.time()
    try:
        st = sp.get_current_transport_info().get("current_transport_state")
    except Exception:
        st = "ERR"
    try:
        pos = secs(sp.get_current_track_info().get("position"))
    except Exception:
        pos = None
    tok = token()
    lat = time.time() - q
    el = int(time.time() - t0)
    dp = (pos - prev_pos) if (pos is not None and prev_pos is not None) else None
    flags = []
    if st not in ("PLAYING", None):
        flags.append(f"NOTPLAY({st})")
    if st == "PLAYING" and dp is not None and dp <= 0:
        flags.append("STALL(silent)")
    elif st == "PLAYING" and dp is not None and dp < GAP*0.5:
        flags.append(f"STUTTER(+{dp}s)")
    if prev_tok and tok and tok != prev_tok:
        flags.append(f"RECONNECT({prev_tok}->{tok})")
    if lat > SLOW:
        flags.append(f"SLOW({lat:.1f}s)")
    if flags:
        line = f"  t={el:>3}s  {' '.join(flags)}"
        print(line, flush=True); events.append((el, flags))
    elif i % 5 == 0:
        print(f"  t={el:>3}s  ok (state={st}, pos={pos})", flush=True)
    prev_pos, prev_tok = pos, tok
    if i < N-1:
        time.sleep(GAP)

dur = time.time() - t0
o1, a1 = phy(sp.ip_address), (phy(arc.ip_address) if arc else None)
print("\n=== summary ===")
print(f"window: {int(dur)}s, {N} samples")
print(f"drop/stutter/reconnect events: {len(events)}")
if o1 is not None: print(f"{TARGET} mesh PHY errors/sec: {o1/dur:.0f}")
if a1 is not None: print(f"Arc    mesh PHY errors/sec: {a1/dur:.0f}")
if events:
    print("event times (s):", ", ".join(str(e[0]) for e in events))
