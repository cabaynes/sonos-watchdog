#!/usr/bin/env python3
"""One-shot Sonos network health check.

For every speaker: how it is connected (wired / SonosNet mesh / Wi-Fi), the radio channel,
the live PHY-error rate (radio packet corruption), and its strongest mesh neighbours. Then,
for each playing group, which speaker leads it and whether that leader is wired.

Run on the same network as the speakers:  python3 sonos_health.py [--gap 30]
"""
import argparse
import sys
import time

import requests
import soco

import labels
from parsers import fabric, parse_mesh, parse_wireless, phy_rate

UPNP_OFF = ("port 1400 refused — UPnP looks switched off "
            "(Sonos app → Account → Privacy & Security → Connection Security)")


def fetch(ip: str, path: str):
    try:
        r = requests.get(f"http://{ip}:1400{path}", timeout=5)
        return r.text if r.ok else None
    except requests.RequestException:
        return None


def quality(rssi: int) -> str:
    return "good" if rssi >= 60 else "ok" if rssi >= 50 else "weak" if rssi >= 45 else "poor"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gap", type=float, default=30, help="seconds between the two PHY-counter reads")
    args = ap.parse_args(argv)

    zones = sorted(soco.discover(timeout=8) or [], key=lambda z: z.player_name)
    if not zones:
        print("No Sonos speakers found. Are you on the same network?")
        return 1
    names = labels.load()

    first = {z.ip_address: fetch(z.ip_address, "/status/proc/ath_rincon/status") for z in zones}
    print(f"Found {len(zones)} speakers. Measuring radio errors for {args.gap:.0f} s...\n")
    time.sleep(args.gap)

    fabrics = {}
    print(f"{'Speaker':16s} {'IP':15s} {'Link':9s} {'MHz':>5s} {'PHY err/s':>10s}  Strongest neighbours")
    print("-" * 96)
    for z in zones:
        ip = z.ip_address
        mesh_txt, wl_txt = fetch(ip, "/status/proc/ath_rincon/status"), fetch(ip, "/status/wireless")
        if first[ip] is None or mesh_txt is None or wl_txt is None:
            print(f"{z.player_name:16s} {ip:15s} {UPNP_OFF}")
            continue
        mesh, wl = parse_mesh(mesh_txt), parse_wireless(wl_txt)
        fabrics[z.player_name] = fab = fabric(wl, mesh)
        rate = "-" if mesh["phy"] is None else f"{phy_rate(mesh['phy'], args.gap):.0f}"
        nbrs = [n for n in sorted(mesh["neighbors"], key=lambda n: -n["to"]) if n["to"] > 0][:3]
        nb = ", ".join(f"{names.get(n['mac'], n['mac'][-8:])} {n['from']}/{n['to']} {quality(n['to'])}" for n in nbrs)
        print(f"{z.player_name:16s} {ip:15s} {fab:9s} {str(mesh['channel_mhz'] or '-'):>5s} {rate:>10s}  {nb or '-'}")

    print("\nPlaying groups:")
    seen, any_playing = set(), False
    for z in zones:
        try:
            g = z.group
            if g.uid in seen:
                continue
            seen.add(g.uid)
            c = g.coordinator
            if c.get_current_transport_info().get("current_transport_state") != "PLAYING":
                continue
        except Exception as e:  # a speaker can drop mid-scan
            print(f"  (could not read {z.player_name}'s group: {e})")
            continue
        any_playing = True
        members = sorted(m.player_name for m in g.members if m.is_visible)
        wired_members = [m for m in members if fabrics.get(m) == "WIRED"]
        led = "yes" if fabrics.get(c.player_name) == "WIRED" else ("no — " + ", ".join(wired_members) +
                                                                   " is wired" if wired_members else "no wired member")
        print(f"  {c.player_name} leads {members}  wired-led: {led}")
    if not any_playing:
        print("  nothing playing")
    print("\nPHY err/s: radio packet errors per second. Compare speakers with each other; there is no official threshold.")
    print("Mesh link quality is Sonos's 0–62 scale: good ≥60, ok 50–59, weak 45–49, poor <45.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
