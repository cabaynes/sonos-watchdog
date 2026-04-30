# Claude Code prompt — install Sonos Watchdog

Paste the prompt below into a Claude Code session running in your Home Assistant project folder. It walks Claude through:

1. Discovering your Sonos speakers via the HA REST API
2. Asking you which speakers to monitor
3. Downloading and installing both Sonos Watchdog blueprints to your HA `config/blueprints/automation/` folder
4. Creating the two automations from the blueprints
5. Verifying everything loaded correctly

## Prerequisites

- A working Claude Code setup pointed at your HA project folder
- HA REST API access configured (a long-lived access token, available at HA → Profile → Long-lived Access Tokens). Most HA-with-Claude-Code projects already have a `.env` with `HA_URL` and `HA_TOKEN`.
- File access to your HA `/config/` directory — usually via Samba (`/Volumes/config/` on macOS), the File Editor add-on, or SSH

## The prompt

Copy everything between the `---` markers and paste it as your first message in a new Claude Code session.

---

I want to install the **Sonos Watchdog** system in my Home Assistant setup. It's a two-automation system that auto-rejoins Sonos speakers when they drop out of an actively playing group. The blueprints live at:

- `https://raw.githubusercontent.com/your-org/sonos-watchdog/main/blueprints/sonos_watchdog_recovery.yaml`
- `https://raw.githubusercontent.com/your-org/sonos-watchdog/main/blueprints/sonos_watchdog_sweep.yaml`

(If those URLs aren't yet hosted, the blueprint YAML is also in this folder under `docs/sonos-watchdog/blueprints/`.)

**Please:**

1. Verify HA REST API access is working:
   ```
   curl -sS -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/" 
   ```
   Expected: `{"message":"API running."}`

2. Discover all my Sonos speakers by querying `/api/states` and filtering for `media_player.*` entities whose friendly name contains "Sonos" or whose entity_id matches typical Sonos patterns. Print a table of `entity_id | friendly_name | current_state` so I can confirm.

3. Ask me two questions:
   - **Which speakers should be monitored** for recovery? (Default: all of them.)
   - **Which speakers should be auto-join candidates** in the sweep? (Default: same as above. Speakers excluded here will be left alone if they fall out of the group — useful for, say, a kid's bedroom you don't want music in unless explicitly chosen.)

4. Download the two blueprint YAML files and place them in `/config/blueprints/automation/sonos-watchdog/` on the HA host (create the directory if it doesn't exist). My HA config dir is accessible at one of:
   - `/Volumes/config/` (Samba mount on macOS)
   - `/config/` (if running inside HA Container)
   - via SSH to `homeassistant.local` (if SSH add-on is installed)
   
   Ask me which path applies if it's not obvious from my project.

5. Reload blueprints via the API call:
   ```
   POST /api/services/homeassistant/reload_all
   ```
   (or have me trigger a manual reload via the HA UI if the API call doesn't pick up new blueprints).

6. Create two automations from the blueprints — one from each blueprint — using my entity selections from step 3. Add them to my `automations.yaml` (or create a separate file if I prefer). After adding, run:
   ```
   POST /api/config/core/check_config
   POST /api/services/automation/reload
   ```

7. Verify both automations are in `state: on`:
   ```
   GET /api/states/automation.<automation_id>
   ```

8. Tell me what to do next:
   - Test the recovery edge by unplugging one speaker for 30 seconds, then plug back in. Should rejoin within 4–8 seconds if a group is playing.
   - The sweep is harder to test deliberately; just trust that it'll catch silent drops within ~15 seconds.

**Important constraints / things to know:**

- **Don't read my `secrets.yaml`** with the Read tool — there are credentials in it. Use targeted `grep`/`awk` if you need to inspect.
- **Validate YAML before reloading** — always run `POST /api/config/core/check_config` first, never blindly reload after editing.
- **Confirm with me before deleting or overwriting any existing files** in `/config/`. If `automations.yaml` already has automations, append to it; don't replace.
- **The blueprints assume Sonos integration is already set up in HA.** If `media_player.*` entities don't exist for my Sonos speakers, the integration needs to be configured first via Settings → Devices & Services → Add Integration → Sonos.

---

## After installation

Once installed, the Sonos Watchdog runs in the background. Test it by:

1. Start playing music across multiple Sonos speakers (HA script, Sonos app, or Sonos Voice — doesn't matter)
2. Unplug one speaker for ~30 seconds
3. Plug it back in
4. Within 4–8 seconds, that speaker should rejoin the playing group at the master's current volume

If anything doesn't work, paste the entity history of the dropped speaker (HA → Developer Tools → States → search for the speaker → History tab) into a follow-up Claude Code message — the state transitions are usually enough to diagnose.
