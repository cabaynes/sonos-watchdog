#!/usr/bin/env python3
"""Print current mesh signal report — pulls latest mesh_poll record per speaker."""
import json
from pathlib import Path
from collections import OrderedDict


LOG_DIR = Path(__file__).parent / "logs"


# MAC -> friendly label for known household devices. The mesh table reports
# the radio MAC, which is the device MAC + 1 in the last byte.
KNOWN_RADIO_MACS = {
    "F0:F6:C1:77:20:28": "Living Room (Arc)",
    "5C:AA:FD:FD:76:4B": "Kitchen",
    "5C:AA:FD:FD:74:71": "Office",
    "78:28:CA:C7:B0:A3": "Bathroom",
    "94:9F:3E:DF:5D:D1": "Bedroom",
    "94:9F:3E:BA:0D:35": "Record player",
    "5C:AA:FD:D7:9C:69": "Sonos Move (radio)",
    # Bonded HT satellites (these don't show in SSDP discovery)
    "94:9F:3E:A7:3F:63": "HT Sub",
    "78:28:CA:14:45:6D": "HT Surround #1",
    "78:28:CA:14:2F:DF": "HT Surround #2",
}


def latest_log():
    files = sorted(LOG_DIR.glob("events-*.jsonl"))
    return files[-1] if files else None


def latest_polls():
    """Return latest mesh_poll record per speaker."""
    path = latest_log()
    if not path:
        return {}
    polls = OrderedDict()
    with open(path) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("kind") == "mesh_poll":
                polls[rec.get("zone")] = rec
    return polls


def label_mac(mac: str) -> str:
    return KNOWN_RADIO_MACS.get(mac.upper(), f"unknown ({mac})")


def quality_emoji(rssi_to: int) -> str:
    if rssi_to >= 60:
        return "✅"
    if rssi_to >= 50:
        return "🟡"
    if rssi_to >= 45:
        return "🟠"
    return "🔴"


def main():
    polls = latest_polls()
    if not polls:
        print("No mesh_poll records yet — daemon may not have run a polling cycle.")
        return

    print(f"=== Mesh signal report (latest poll per speaker) ===\n")
    print(f"{'Speaker':18s} {'Conn':22s} {'Ch (MHz)':9s} {'PHY/30s':>10s}  Top mesh neighbors")
    print("-" * 110)

    for zone, rec in polls.items():
        m = rec.get("mesh", {}) or {}
        w = rec.get("wireless", {}) or {}
        ch = m.get("channel_mhz", "?")
        phy = m.get("phy_errors_delta", "?")
        conn = w.get("connection", "?")
        nbrs = m.get("mesh_neighbors", []) or []
        # Sort by signal quality (rssi_to high to low)
        nbrs_sorted = sorted(nbrs, key=lambda n: -n.get("rssi_to", 0))[:3]
        nbr_str = ", ".join(
            f"{label_mac(n['mac'])[:18]} {n['rssi_from']}/{n['rssi_to']}{quality_emoji(n['rssi_to'])}"
            for n in nbrs_sorted
        )
        print(f"{zone:18s} {conn:22s} {str(ch):9s} {str(phy):>10s}  {nbr_str}")

    print()
    print("Legend:")
    print("  rssi_from / rssi_to = mesh link quality FROM neighbor / TO neighbor (higher = better)")
    print(f"  ✅ ≥60 (good)  🟡 50-59 (ok)  🟠 45-49 (weak)  🔴 <45 (poor)")


if __name__ == "__main__":
    main()
