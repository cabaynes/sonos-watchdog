# Claude Code prompt — install Sonos Watchdog

Paste the prompt below into a Claude Code session running in your Home Assistant project
folder. It has Claude check API access, find your Sonos speakers, create the helper, install
the blueprint and create the automation — asking you before anything it can't undo.

## Prerequisites

- Home Assistant REST API access: a long-lived access token (HA → your profile → Security →
  Long-lived access tokens), usually kept in a `.env` file as `HA_URL` and `HA_TOKEN`.
- The Sonos integration already set up in Home Assistant.

## The prompt

Copy everything between the `---` markers.

---

I want to install the **Sonos Watchdog** blueprint in my Home Assistant. Read
https://github.com/cabaynes/sonos-watchdog/blob/main/README.md first. The blueprint is
https://raw.githubusercontent.com/cabaynes/sonos-watchdog/main/blueprints/sonos_watchdog.yaml

Please:

1. Check API access (`GET /api/` should return `{"message":"API running."}`). Never print my token.
2. List my Sonos `media_player` entities (use `integration_entities('sonos')` via `POST /api/template`) as a table of entity id, name and state, and ask me to confirm the list.
3. Create the text helper `input_text.sonos_intended_speakers` with maximum length 255 (or reuse it if it exists — check first).
4. Install the blueprint (the UI "Import blueprint" with the URL above, or the websocket `blueprint/import` + `blueprint/save` commands).
5. Create one automation from it with my confirmed speakers and the helper, defaults for everything else, then confirm the new automation's state is `on`.
6. Ask me whether I also want the optional log file and monthly totals from the README, and set them up only if I say yes (the log file needs one line in `configuration.yaml` and a restart — ask before restarting).
7. If I have automations from v1/v2 of Sonos Watchdog (recovery, sweep, master failover, snapshot), list them and ask before disabling or deleting any.

Run `POST /api/config/core/check_config` before any reload or restart, and ask me before
deleting or overwriting anything.

---

## Testing it

Start music on a group, unplug one speaker for about 30 seconds, plug it back in. Within a
few seconds of it coming back it should rejoin, and the logbook (filter "Sonos Watchdog")
shows `speaker_offline`, `speaker_left … offline`, `speaker_online` and `repair` or
`speaker_back`.
