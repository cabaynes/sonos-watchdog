#!/usr/bin/env python3
"""One-shot WiFi/mesh health test for every Sonos speaker.

Re-discovers each speaker at its CURRENT ip (unlike the long-running
daemon, which caches IPs at startup and goes stale after DHCP changes),
then reads each speaker's network diagnostics directly and prints a
human-readable health report:

  - connection fabric: SonosNet mesh (from the wired Arc) vs home WiFi
    (from the router), and the channel/band in use
  - PHY error rate (radio-level packet corruption since last reset)
  - per-neighbor mesh RSSI in both directions (SonosNet speakers)
  - WiFi RSSI to the router (standard-WiFi speakers, e.g. Roam/Move)
"""
import re
import sys
import requests
import soco

KNOWN_RADIO_MACS = {
    "F0:F6:C1:77:20:28": "Living Room (Arc)",
    "5C:AA:FD:FD:76:4B": "Kitchen",
    "5C:AA:FD:FD:74:71": "Office",
    "78:28:CA:C7:B0:A3": "Bathroom",
    "94:9F:3E:DF:5D:D1": "Bedroom",
    "94:9F:3E:BA:0D:35": "Record player",
    "5C:AA:FD:D7:9C:69": "Sonos Move",
    "94:9F:3E:A7:3F:63": "HT Sub",
    "78:28:CA:14:45:6D": "HT Surround #1",
    "78:28:CA:14:2F:DF": "HT Surround #2",
}


def label_mac(mac):
    return KNOWN_RADIO_MACS.get(mac.upper(), f"?({mac[-8:]})")


def q(rssi):
    if rssi is None:
        return "?"
    if rssi >= 60:
        return "✅good"
    if rssi >= 50:
        return "🟡 ok"
    if rssi >= 45:
        return "🟠weak"
    return "🔴poor"


def get(ip, path):
    try:
        return requests.get(f"http://{ip}:1400{path}", timeout=5).text
    except Exception as e:
        return f"__ERR__ {e}"


def parse_mesh(text):
    out = {"channel_mhz": None, "phy": None, "neighbors": []}
    ch = re.search(r"channel\s+(\d+)", text)
    if ch:
        out["channel_mhz"] = int(ch.group(1))
    phy = re.search(r"PHY errors since last reading/reset:\s*(\d+)", text)
    if phy:
        out["phy"] = int(phy.group(1))
    for m in re.finditer(
        r"Node\s+([0-9A-F:]{17})\s*-\s*FROM\s+(\d+)\s*:\s*TO\s+(\d+)", text
    ):
        out["neighbors"].append(
            {"mac": m.group(1), "from": int(m.group(2)), "to": int(m.group(3))}
        )
    return out


def parse_wireless(text):
    out = {}
    for tag in ("ConnectionTypeString", "WifiModeString", "Rssi",
                "Channel", "Freq", "Noise"):
        m = re.search(rf"<{tag}>([^<]+)</{tag}>", text)
        if m:
            out[tag] = m.group(1)
    # plain-text fallbacks
    if "Rssi" not in out:
        m = re.search(r"RSSI[:\s=]+(-?\d+)", text)
        if m:
            out["Rssi"] = m.group(1)
    return out


def main():
    print("Discovering speakers (fresh, current IPs)...", flush=True)
    zones = list(soco.discover(timeout=8) or [])
    if not zones:
        print("No speakers discovered. Are you on the home WiFi?")
        sys.exit(1)
    zones.sort(key=lambda z: z.player_name)
    print(f"Found {len(zones)}: {[z.player_name for z in zones]}\n")

    print(f"{'Speaker':16s} {'IP':14s} {'Fabric':10s} {'Ch':5s} {'PHY':>6s}  Signal / neighbors")
    print("-" * 100)
    for z in zones:
        ip = z.ip_address
        wl = parse_wireless(get(ip, "/status/wireless"))
        mesh = parse_mesh(get(ip, "/status/proc/ath_rincon/status"))
        wmode = wl.get("WifiModeString", "")
        conn = wl.get("ConnectionTypeString", "")
        on_mesh = bool(mesh["neighbors"])
        if "wired" in conn.lower() or "ethernet" in conn.lower():
            fabric = "WIRED"
        elif on_mesh or wmode in ("0", "SonosNet"):
            fabric = "SonosNet"
        else:
            fabric = "WiFi"
        ch = mesh["channel_mhz"] or wl.get("Channel") or "-"
        phy = mesh["phy"]
        phy_s = "-" if phy is None else str(phy)
        if on_mesh:
            nb = sorted(mesh["neighbors"], key=lambda n: -n["to"])[:3]
            sig = ", ".join(f"{label_mac(n['mac'])} {n['from']}/{n['to']}{q(n['to'])}" for n in nb)
        else:
            rssi = wl.get("Rssi")
            sig = f"router RSSI {rssi} dBm" if rssi else f"conn={conn or '?'} mode={wmode or '?'} (no mesh data)"
        print(f"{z.player_name:16s} {ip:14s} {fabric:10s} {str(ch):5s} {phy_s:>6s}  {sig}")

    print("\nMesh RSSI scale 0-62 (Sonos units): ✅>=60  🟡50-59  🟠45-49  🔴<45")
    print("PHY = radio packet errors since last reset; steadily climbing = RF trouble.")


if __name__ == "__main__":
    main()
