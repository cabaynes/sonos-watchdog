#!/usr/bin/env python3
"""Measure live PHY-error RATE per speaker.

The /status/proc/ath_rincon/status counter is "errors since last
read/reset", so a single snapshot is meaningless. We read twice with a
fixed gap and report errors/second — the number that actually indicates
live radio corruption.
"""
import re
import time
import requests
import soco

GAP = 45


def phy(ip):
    try:
        t = requests.get(f"http://{ip}:1400/status/proc/ath_rincon/status", timeout=5).text
        m = re.search(r"PHY errors since last reading/reset:\s*(\d+)", t)
        c = re.search(r"channel\s+(\d+)", t)
        return (int(m.group(1)) if m else None, int(c.group(1)) if c else None)
    except Exception as e:
        return (None, f"err:{e}")


zones = sorted(soco.discover(timeout=8) or [], key=lambda z: z.player_name)
print(f"Priming counters on {len(zones)} speakers, waiting {GAP}s...\n")
first = {z.player_name: (z.ip_address, phy(z.ip_address)) for z in zones}
time.sleep(GAP)
print(f"{'Speaker':16s} {'Ch(MHz)':8s} {'errors/'+str(GAP)+'s':>12s} {'err/sec':>10s}  health")
print("-" * 64)
for z in zones:
    ip, (p1, ch) = first[z.player_name]
    p2, _ = phy(ip)
    if p1 is None or p2 is None:
        print(f"{z.player_name:16s} {str(ch):8s} {'(no data)':>12s}")
        continue
    d = p2  # second read = errors accumulated during GAP (first read reset it)
    rate = d / GAP
    health = "✅clean" if rate < 50 else ("🟡 busy" if rate < 500 else ("🟠noisy" if rate < 5000 else "🔴 saturated"))
    print(f"{z.player_name:16s} {str(ch):8s} {d:>12d} {rate:>10.1f}  {health}")
