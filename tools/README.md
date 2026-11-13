# Sonos Watchdog — Diagnostic Daemon

A standalone Python service that talks to Sonos speakers **directly**
(local UPnP + SOAP, no Home Assistant in the loop) for forensic
analysis of multi-room audio behavior.

**This daemon is the diagnostic toolkit that produced
[`../FINDINGS.md`](../FINDINGS.md)** — the documented Apple Music
master-relay diagnosis. If you have chronic Sonos dropouts and want to
figure out the real cause, see
[`DIAGNOSTIC_GUIDE.md`](DIAGNOSTIC_GUIDE.md) for the step-by-step
methodology to reproduce the finding (or find a different one) on
your own setup.

This complements the HA blueprints in [`../blueprints/`](../blueprints/) —
the blueprints handle UPnP-visible speaker drops via HA polling, the
daemon handles sub-second event-driven monitoring + mesh signal
diagnostics for the dropout patterns the blueprints can't see.

## What it does

- Subscribes to UPnP events on every discovered Sonos device
  (`ZoneGroupTopology`, `AVTransport`, `RenderingControl`)
- Polls `/status/proc/ath_rincon/status` and `/status/wireless` on
  every speaker every 30 seconds for mesh signal strength, PHY error
  rates, and channel info
- Logs everything to a structured JSONL event log for forensic
  analysis
- Includes helper scripts to pretty-print the log and produce a
  human-readable mesh signal report

## Why a separate daemon?

| | HA blueprints (existing) | Daemon (this) |
|---|---|---|
| Detection | Polled, ~5-10s latency | UPnP push, <100ms |
| Recovery | HA service call → integration → SOAP (3 hops) | Direct SOAP (1 hop) |
| Visibility | HA logbook, sparse | Full UPnP event stream + mesh diagnostics |
| Independence | Dies with HA | Independent process |

## What gets logged

Each event becomes one line in `logs/events-YYYYMMDD.jsonl`. Record
kinds:

- `discovery` — list of Sonos zones found at startup
- `topology_snapshot` — current group memberships (every 5 min)
- `upnp_event` — any state change pushed by a speaker. Subscribed
  services: `zoneGroupTopology`, `avTransport`, `renderingControl`
- `mesh_poll` — per-speaker mesh signal + PHY error counters,
  scraped from `/status/proc/ath_rincon/status` and
  `/status/wireless`. Polled every 30s.

## Run

```bash
# one-time setup
pip3 install --user -r requirements.txt

# run
python3 sonos_watchdog.py
```

Press Ctrl+C to stop. JSONL log accumulates in `logs/`.

## Tail the log

```bash
# last 100 events, formatted
python3 tail_events.py 100

# follow live
python3 tail_events.py -f
```

## Snapshot current mesh signal report

```bash
python3 mesh_report.py
```

Prints a table of every speaker's mesh signal strength to its peers,
plus PHY error rates from the most recent poll.

## Run as a background service (macOS)

For continuous operation, use the included `launchd` plist template:

```bash
# Edit sonos-watchdog.plist.example — replace YOURNAME and PATH placeholders
# Save as com.<yourname>.sonos-watchdog.plist
cp com.<yourname>.sonos-watchdog.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.<yourname>.sonos-watchdog.plist

# Stop with:
launchctl unload ~/Library/LaunchAgents/com.<yourname>.sonos-watchdog.plist
```

## Run as a background service (Linux / NAS)

A simple `systemd` unit works:

```ini
[Unit]
Description=Sonos Watchdog diagnostic daemon
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/sonos-watchdog/daemon
ExecStart=/usr/bin/python3 /path/to/sonos-watchdog/daemon/sonos_watchdog.py
Restart=on-failure
User=youruser

[Install]
WantedBy=multi-user.target
```

For Docker / containerized deployment, you'd need to use host
networking (`--network host`) so UPnP NOTIFY callbacks from the
speakers reach the listener.

## Why mesh polling matters

UPnP events tell you a dropout *happened*. Mesh polling tells you
*why* — by correlating PHY error rate + per-link RSSI with dropout
events, you can distinguish RF-caused drops from upstream-pipeline
buffer starvation (the failure mode that produced the Apple Music
finding). UPnP alone can't make that distinction.

The mesh data Sonos exposes that almost nothing else surfaces:

- Per-mesh-neighbor RSSI in both directions (FROM/TO)
- PHY error counts (delta since last read)
- SonosNet vs WiFi connection mode per speaker
- Channel + frequency band actually in use
- Bonded HT satellite presence (via `ZoneGroupTopology` SOAP, not
  visible in SSDP discovery)

## Use cases

1. **Diagnosing your own dropouts** — see
   [`DIAGNOSTIC_GUIDE.md`](DIAGNOSTIC_GUIDE.md) for the full recipe
2. **Pre-purchase planning** — running the daemon for a week before
   adding more speakers tells you whether your current setup has
   headroom
3. **Network upgrade validation** — measure mesh signal + PHY errors
   before and after switching SonosNet channels, moving the router,
   or hardwiring a speaker
4. **Post-firmware-update monitoring** — watch for state-change
   patterns that change after a Sonos firmware update

## Things this daemon is NOT

- A 24/7 production monitoring system — it's a diagnostic tool, not a
  recovery tool. Use the HA blueprints in `../blueprints/` for
  recovery.
- A replacement for Sonos's own diagnostics submission — if you have
  a real hardware issue, file a Sonos support ticket too.
- A way to control your speakers — discovery and event listening
  only; no SOAP commands sent.

## License

Same as the parent repo — public domain. Take it, adapt it, share it.
