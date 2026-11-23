# Sonos Watchdog

A Home Assistant blueprint that keeps an eye on your Sonos groups, plus a few
diagnostic tools and a write-up of why Sonos multi-room playback drops out.

## What it does — and what it can't

**It fixes one thing:** a speaker that **drops off the network** while your group is
playing (a Wi-Fi blip, a reboot, a power cut) is put back into the group when it comes
back, usually within a few seconds.

**It logs what Home Assistant can see:** every listening session (who led it, which
speakers, the source), every speaker that leaves a playing group or goes offline, and
every repair, with optional long-term monthly totals.

**It cannot see the most common Sonos dropout:** a speaker that **stays in the group but
goes silent** for a few seconds at a time. When that happens the speakers keep reporting
"playing" and the group never changes, so neither this blueprint nor anything else in
Home Assistant can detect it, and an empty log does **not** mean there were no dropouts.
That kind is caused by the group's leader not keeping up with streaming to the others;
[FINDINGS.md](FINDINGS.md) explains it and what actually helps (lower-bitrate sources,
smaller groups, a wired speaker leading).

**What it deliberately won't do:**

- **Undo your own changes.** A speaker that leaves the group while still online — you
  ungrouped it, switched to a smaller group or preset, or took it to play something else —
  is left alone. Home Assistant can't tell that apart from a speaker quietly falling out,
  so the watchdog assumes it was you. It still logs it.
- **Touch volume.** Rejoined speakers keep their own volume.
- **Pull in a busy speaker.** A speaker playing something of its own, or grouped with
  others, is never taken.
- **Change the group's leader while music plays.** We tried it: the group went out of
  sync until it was rebuilt. (During a pause it's safe, and the optional
  [wired-leader setting](docs/wired-leader.md) uses that.)

## Install

1. **Create the session helper.** Settings → Devices & services → Helpers → Create helper →
   **Text**. Name it `Sonos intended speakers` (entity `input_text.sonos_intended_speakers`)
   and set **Maximum length to 255**.
2. **Import the blueprint.** Settings → Automations & scenes → Blueprints → Import blueprint,
   and paste:
   `https://github.com/cabaynes/sonos-watchdog/blob/main/blueprints/sonos_watchdog.yaml`
3. **Create one automation from it.** Pick every Sonos speaker, pick the helper, keep the
   defaults, save.

That's the whole install. The settings:

| Setting | Default | What it means |
|---|---|---|
| Settle time | 60 s | How long a smaller group must stay smaller before the watchdog decides why a speaker left (offline → it will be brought back; still online → your change). |
| Wait after a speaker comes back | 3 s | Sonos speakers answer the network slightly before they accept commands. |
| Forget the session after | 15 min | With nothing playing for this long, the session is over. Pausing for a few minutes keeps it. |
| Wired speakers | none | Speakers on Ethernet. Each session's log line says whether one of them led; with the optional handover command, one takes the lead during pauses. |
| Handover command, hand over after | none, 30 s | See [docs/wired-leader.md](docs/wired-leader.md). |
| Log file, counters | none | Optional — see below. |

### Optional: a log file that outlives the logbook

Home Assistant's logbook keeps about 10 days. To keep every event:

1. Add the File integration (Settings → Devices & services → Add integration → **File**),
   choose **Notification**, and give it a path such as `/config/sonos_watchdog/log.csv`.
2. Allow that folder in `configuration.yaml`, then restart Home Assistant:

   ```yaml
   homeassistant:
     allowlist_external_dirs:
       - /config/sonos_watchdog
   ```

3. Pick the new `notify.…` entity as the blueprint's **Log file**.

Each event is one line: `time,event,subject,detail`, for example
`2026-11-12T19:04:11-08:00,speaker_left,media_player.office,offline; leader=media_player.living_room`.

| Event | Meaning |
|---|---|
| `session_start` / `session_end` | A group started playing / nothing has played for the forget time (with duration). |
| `session_change` | The session's group changed: grew, a speaker went offline, or one left on purpose. |
| `speaker_left` | A session speaker left the playing group — `offline` or `online`. |
| `speaker_offline` / `speaker_online` | Any watched speaker went unavailable / came back (with how long). |
| `speaker_back` | A speaker that went offline is back in the group — `by=sonos` (Sonos did it) or `by=watchdog`. |
| `repair` | The watchdog sent a join. |
| `leader_moved` | During a pause, the lead moved to a wired speaker. |

### Optional: monthly totals kept forever

Create four **Counter** helpers (sessions, speakers left, speakers offline, repairs) and pick
them in the blueprint. Counters alone are purged with the rest of the history after about
10 days. To keep long-term statistics, add a **Template sensor** helper for each one, with
the counter's state as the value and **State class: Total increasing**. Then a
**Statistics graph** card with period *Month* shows the totals month by month.

### Optional: a wired speaker always leads

See [docs/wired-leader.md](docs/wired-leader.md).

## Upgrading from v1 or v2

v1 had three blueprints (recovery, periodic sweep, master failover); v2 added a snapshot
automation. Delete those automations and the `input_text.sonos_active_script` helper
(master failover is gone: it needed every music script to register itself and couldn't
help sessions started from the Sonos app), then follow the install above. An existing
`input_text.sonos_intended_speakers` helper can be reused as is.

## Tools

[`tools/`](tools/) has small Python scripts that talk to the speakers directly on your
network: a one-shot health check (how each speaker is connected, radio errors, mesh
signal, who leads each playing group), a group watcher, and the event recorder used for
FINDINGS.md. See [tools/README.md](tools/README.md).

## Troubleshooting

- **Nothing in the log.** Check the automation is on and the helper's maximum length is 255.
  Then start music on a group and look for `session_start` in the logbook (filter on
  "Sonos Watchdog").
- **A speaker came back but wasn't rejoined.** It has to have been in the session and to
  have gone **offline** (unavailable in Home Assistant). If it left while still online,
  that's treated as your change. The `speaker_left` line says which.
- **Silent gaps in some rooms.** That's the in-group dropout this can't see. See
  [FINDINGS.md](FINDINGS.md).
- **Everything shows unavailable.** If you turned off UPnP in the Sonos app (Account →
  Privacy & Security → Connection Security), Home Assistant's Sonos integration and these
  tools can't reach the speakers.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q          # renders the blueprint's templates against test states
.venv/bin/yamllint blueprints/
```

## License

MIT — see [LICENSE](LICENSE).
