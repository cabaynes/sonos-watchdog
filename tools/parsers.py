"""Parse the Sonos diagnostic pages on port 1400 (/status/proc/ath_rincon/status, /status/wireless)."""
import re

_NODE = re.compile(r"Node\s+([0-9A-Fa-f:]{17})\s*-\s*FROM\s+(\d+)\s*:\s*TO\s+(\d+)")


def parse_mesh(text: str) -> dict:
    """Channel (MHz), PHY-error count since the last read, and mesh neighbours with link quality."""
    ch = re.search(r"channel\s+(\d+)", text)
    phy = re.search(r"PHY errors since last reading/reset:\s*(\d+)", text)
    return {
        "channel_mhz": int(ch.group(1)) if ch else None,
        "phy": int(phy.group(1)) if phy else None,
        "neighbors": [{"mac": m.group(1).upper(), "from": int(m.group(2)), "to": int(m.group(3))}
                      for m in _NODE.finditer(text)],
    }


def parse_wireless(text: str) -> dict:
    out = {}
    for tag in ("ConnectionTypeString", "WifiModeString", "SonosNetDisabled", "Rssi", "Channel"):
        m = re.search(rf"<{tag}>([^<]+)</{tag}>", text)
        if m:
            out[tag] = m.group(1).strip()
    return out


def fabric(wireless: dict, mesh: dict) -> str:
    """'WIRED', 'SonosNet' or 'WiFi'. The speaker's own connection type wins over stale mesh entries."""
    conn = wireless.get("ConnectionTypeString", "").lower()
    mode = wireless.get("WifiModeString", "").upper()
    if "ethernet" in conn or "wired" in conn:
        return "WIRED"
    if conn.startswith("wifi") or mode == "STATION_MODE":
        return "WiFi"
    if "sonosnet" in conn or mode == "SONOSNET_MODE" or any(n["to"] > 0 for n in mesh.get("neighbors", [])):
        return "SonosNet"
    return "WiFi"


def phy_rate(count_after_gap: int, gap_s: float) -> float:
    """The PHY counter resets on every read, so a read after a gap is the errors during that gap."""
    return round(count_after_gap / gap_s, 1)
