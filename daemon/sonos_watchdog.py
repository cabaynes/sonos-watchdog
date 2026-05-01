#!/usr/bin/env python3
"""
Sonos Watchdog daemon - Phase 1 (observation only).

Subscribes to UPnP events on every discovered Sonos device and polls
each speaker's mesh signal/PHY-error counters periodically. Every event
and every poll is logged to a structured JSONL file for forensic
analysis of dropouts.

Phase 2 will add reactive recovery (rejoin on drop).
Phase 3 will add proactive pre-emption (drop weak-link speakers).
"""
import json
import logging
import re
import signal
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty

import requests
import soco
from soco.events import event_listener


LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

POLL_INTERVAL_SEC = 30
RESUB_TIMEOUT_SEC = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s %(message)s",
)
log = logging.getLogger("sonos-watchdog")
logging.getLogger("soco").setLevel(logging.WARNING)

SHUTDOWN = threading.Event()
SUBSCRIPTIONS = []
WRITE_LOCK = threading.Lock()


def event_log_path():
    return LOG_DIR / f"events-{datetime.now().strftime('%Y%m%d')}.jsonl"


def write_record(record: dict):
    record.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with WRITE_LOCK:
        with open(event_log_path(), "a") as f:
            f.write(json.dumps(record, default=str) + "\n")


def event_drainer(zone_name: str, zone_ip: str, service_name: str, sub):
    log.info(f"drainer started: {zone_name}/{service_name}")
    while not SHUTDOWN.is_set():
        try:
            event = sub.events.get(timeout=0.5)
        except Empty:
            continue
        try:
            variables = dict(event.variables) if event.variables else {}
        except Exception:
            variables = {"_decode_error": True}
        write_record({
            "kind": "upnp_event",
            "zone": zone_name,
            "ip": zone_ip,
            "service": service_name,
            "seq": getattr(event, "seq", None),
            "variables": variables,
        })
        # Single-line console summary
        keys = list(variables.keys())[:5]
        log.info(f"event {zone_name} {service_name} seq={getattr(event, 'seq', '?')} vars={keys}")
    log.info(f"drainer stopping: {zone_name}/{service_name}")


def parse_mesh_status(text: str) -> dict:
    """Parse /status/proc/ath_rincon/status XML payload."""
    out = {}
    ch = re.search(r"channel\s+(\d+)", text)
    if ch:
        out["channel_mhz"] = int(ch.group(1))
    phy = re.search(r"PHY errors since last reading/reset:\s*(\d+)", text)
    if phy:
        out["phy_errors_delta"] = int(phy.group(1))
    out["mesh_neighbors"] = []
    for m in re.finditer(
        r"Node\s+([0-9A-F:]{17})\s*-\s*FROM\s+(\d+)\s*:\s*TO\s+(\d+)\s*:\s*STP\s+(\w+)\s*:\s*MODEL\s+([\d.]+)\s*:\s*KEY\s+(\d+)",
        text,
    ):
        out["mesh_neighbors"].append({
            "mac": m.group(1),
            "rssi_from": int(m.group(2)),
            "rssi_to": int(m.group(3)),
            "stp": m.group(4),
            "model": m.group(5),
            "key": int(m.group(6)),
        })
    return out


def parse_wireless(text: str) -> dict:
    out = {}
    m = re.search(r"<ConnectionTypeString>([^<]+)</ConnectionTypeString>", text)
    if m:
        out["connection"] = m.group(1)
    m = re.search(r"<WifiModeString>([^<]+)</WifiModeString>", text)
    if m:
        out["wifi_mode"] = m.group(1)
    return out


def poll_mesh(zone):
    """Poll mesh signal + PHY error counters for one zone."""
    try:
        rp = requests.get(
            f"http://{zone.ip_address}:1400/status/proc/ath_rincon/status",
            timeout=4,
        )
        mesh = parse_mesh_status(rp.text)
    except Exception as e:
        mesh = {"_error": str(e)}
    try:
        rw = requests.get(
            f"http://{zone.ip_address}:1400/status/wireless",
            timeout=4,
        )
        wireless = parse_wireless(rw.text)
    except Exception as e:
        wireless = {"_error": str(e)}
    write_record({
        "kind": "mesh_poll",
        "zone": zone.player_name,
        "ip": zone.ip_address,
        "mesh": mesh,
        "wireless": wireless,
    })


def poll_loop(zones):
    log.info(f"mesh poller started, interval={POLL_INTERVAL_SEC}s")
    while not SHUTDOWN.is_set():
        for zone in zones:
            if SHUTDOWN.is_set():
                break
            try:
                poll_mesh(zone)
            except Exception as e:
                log.warning(f"mesh poll failed for {zone.player_name}: {e}")
        for _ in range(POLL_INTERVAL_SEC):
            if SHUTDOWN.is_set():
                break
            time.sleep(1)
    log.info("mesh poller stopping")


def snapshot_topology(zones):
    """Write a topology snapshot record."""
    coord = zones[0]
    groups = []
    try:
        for g in coord.all_groups:
            groups.append({
                "coord": g.coordinator.player_name,
                "members": sorted(m.player_name for m in g.members),
            })
    except Exception as e:
        groups = [{"_error": str(e)}]
    write_record({"kind": "topology_snapshot", "groups": groups})
    log.info(f"topology: {groups}")


def subscribe_all(zones):
    services = ["zoneGroupTopology", "avTransport", "renderingControl"]
    threads = []
    for zone in zones:
        for svc_name in services:
            try:
                svc = getattr(zone, svc_name)
                sub = svc.subscribe(auto_renew=True, requested_timeout=RESUB_TIMEOUT_SEC)
                SUBSCRIPTIONS.append(sub)
                t = threading.Thread(
                    target=event_drainer,
                    args=(zone.player_name, zone.ip_address, svc_name, sub),
                    daemon=True,
                    name=f"drain-{zone.player_name[:10]}-{svc_name[:6]}",
                )
                t.start()
                threads.append(t)
            except Exception as e:
                log.error(f"subscribe failed: {zone.player_name}/{svc_name}: {e}")
    return threads


def shutdown_handler(signum, frame):
    log.info(f"signal {signum} received, shutting down...")
    SHUTDOWN.set()
    for sub in SUBSCRIPTIONS:
        try:
            sub.unsubscribe()
        except Exception:
            pass
    try:
        event_listener.stop()
    except Exception:
        pass


def main():
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    log.info(f"event log: {event_log_path()}")
    log.info("discovering Sonos zones...")
    zones = list(soco.discover(timeout=5) or [])
    if not zones:
        log.error("no zones discovered, exiting")
        sys.exit(1)
    zones.sort(key=lambda z: z.player_name)
    write_record({
        "kind": "discovery",
        "zones": [
            {"name": z.player_name, "ip": z.ip_address, "uid": z.uid}
            for z in zones
        ],
    })
    log.info(f"discovered {len(zones)} zones: {[z.player_name for z in zones]}")

    snapshot_topology(zones)

    log.info("subscribing to UPnP events...")
    drain_threads = subscribe_all(zones)
    log.info(f"{len(SUBSCRIPTIONS)} active subscriptions")

    poller = threading.Thread(
        target=poll_loop, args=(zones,), daemon=True, name="mesh-poller"
    )
    poller.start()

    log.info(f"watchdog running. event log: {event_log_path()}")
    log.info("press Ctrl+C to stop")

    last_snapshot = time.time()
    while not SHUTDOWN.is_set():
        time.sleep(1)
        # Periodic full topology snapshot every 5 minutes
        if time.time() - last_snapshot > 300:
            snapshot_topology(zones)
            last_snapshot = time.time()


if __name__ == "__main__":
    main()
