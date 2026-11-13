"""Parsers for the speakers' diagnostic pages (fixtures captured from real speakers, MACs/IPs scrubbed)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
FIX = Path(__file__).parent / "fixtures"

import labels  # noqa: E402
from parsers import fabric, parse_mesh, parse_wireless, phy_rate  # noqa: E402


def read(name):
    return (FIX / name).read_text()


def test_parse_mesh_neighbors_and_channel():
    m = parse_mesh(read("mesh_mesh.xml"))
    assert m["channel_mhz"] == 2462
    assert isinstance(m["phy"], int)
    assert m["neighbors"][0] == {"mac": "AA:BB:CC:00:00:01", "from": 54, "to": 61}


def test_fabric_wifi_speaker_with_stale_zero_neighbors():
    mesh, wl = parse_mesh(read("move_mesh.xml")), parse_wireless(read("move_wireless.xml"))
    assert mesh["neighbors"] and all(n["to"] == 0 for n in mesh["neighbors"])
    assert fabric(wl, mesh) == "WiFi"


def test_fabric_wired():
    assert fabric(parse_wireless(read("wired_wireless.xml")), parse_mesh(read("wired_mesh.xml"))) == "WIRED"


def test_fabric_sonosnet():
    assert fabric(parse_wireless(read("mesh_wireless.xml")), parse_mesh(read("mesh_mesh.xml"))) == "SonosNet"


def test_phy_rate():
    assert phy_rate(4500, 45) == 100.0


def test_labels_missing_file_returns_empty(tmp_path):
    assert labels.load(tmp_path / "nope.json") == {}


def test_labels_reads_local_file(tmp_path):
    p = tmp_path / "labels.local.json"
    p.write_text(json.dumps({"aa:bb:cc:00:00:01": "Kitchen"}))
    assert labels.load(p) == {"AA:BB:CC:00:00:01": "Kitchen"}
