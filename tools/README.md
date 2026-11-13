# Sonos diagnostic tools

Small Python scripts that talk to Sonos speakers directly on your network (the local
UPnP/SOAP interface on port 1400), with no Home Assistant in the loop. They produced
[`../FINDINGS.md`](../FINDINGS.md). Each one runs, reports, and exits, except the
recorder, which runs until you stop it.

## Setup

```bash
cd sonos-watchdog/tools
pip3 install --user -r requirements.txt
```

Run them from a computer on the same network as the speakers. If you've turned off UPnP in
the Sonos app (Account → Privacy & Security → Connection Security), the speakers won't
answer.

## The tools

| Script | What it tells you |
|---|---|
| `sonos_health.py [--gap 30]` | For every speaker: wired / SonosNet mesh / Wi-Fi, radio channel, radio errors per second, strongest mesh neighbours. Then which speaker leads each playing group and whether it's wired. |
| `watch_group.py --speaker NAME [--seconds 180]` | Watches one speaker's group and flags visible trouble: playback stopping, position stalling, the speaker leaving the group, AirPlay reconnects, slow answers. |
| `event_recorder.py` | Records every group, transport and volume event plus mesh readings every 30 s to `logs/events-YYYYMMDD.jsonl`. Run it while you reproduce a problem, Ctrl+C to stop. |
| `tail_events.py [N] [-f]` | Pretty-prints the recorder's latest log (or follows it with `-f`). |

**What none of them can see:** a speaker that stays in the group but goes silent. The
group keeps reporting "playing" with an advancing position, and current firmware exposes
no audio-buffer counters. See FINDINGS.md.

## Friendly names (optional)

Mesh neighbours are listed by radio MAC. To see names instead, create
`labels.local.json` here (it's git-ignored):

```json
{"AA:BB:CC:DD:EE:FF": "Kitchen", "AA:BB:CC:DD:EE:01": "Living Room"}
```

A speaker's radio MAC is usually its device MAC plus one in the last byte.

## Step-by-step diagnosis

[`DIAGNOSTIC_GUIDE.md`](DIAGNOSTIC_GUIDE.md) walks through reproducing the FINDINGS.md
comparison on your own speakers.

## License

MIT, like the rest of the repository.
