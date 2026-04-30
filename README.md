# Sonos Watchdog

A two-automation Home Assistant system that **automatically reconnects Sonos speakers** when they drop out of an actively playing group. Works with playback started by HA scripts, the Sonos app, Sonos Voice — anything that creates a Sonos native group.

## The problem this solves

Sonos's grouped multi-room playback is famously flaky in some environments — speakers drop mid-song, fall out of the group silently, or go briefly unreachable on Wi-Fi. Even with a wired Ethernet anchor (which usually helps), some apartments and dense Wi-Fi environments still see chronic dropouts. Manual re-grouping via the Sonos app is annoying and breaks the listening flow.

This watchdog runs entirely in HA and:

1. **Detects** when a candidate speaker either (a) recovers from `unavailable` or (b) is silently missing from the active group
2. **Auto-rejoins** it to the current playing master
3. **Matches volume** to the master's current level

It's source-agnostic — it doesn't matter whether you started the music from an HA script, the Sonos app, or Sonos Voice. As long as a Sonos speaker is playing as a group master, the watchdog watches the rest.

## Architecture

**Three** complementary automations, each handling a different failure mode:

### 1. Speaker Recovery (event-driven)

| | |
|---|---|
| **Trigger** | Any monitored Sonos speaker transitions `unavailable → idle/playing/paused` |
| **Latency** | 4–8 seconds end-to-end (HA event delivery + 3s tuning delay + Sonos join + Sonos sync) |
| **Catches** | Wi-Fi dropouts, brief network blips, speaker reboots |
| **Misses** | Silent drops where the speaker stays online but leaves the group |

### 2. Periodic Group Sweep (timer-driven)

| | |
|---|---|
| **Trigger** | Every N seconds (default 15) |
| **Latency** | Up to your sweep interval (worst case) |
| **Catches** | Silent drops, residual fragmentation after a multi-speaker recovery race |
| **Misses** | Master itself dying (no group to repair) |

### 3. Master Failover (event-driven)

| | |
|---|---|
| **Trigger** | A monitored speaker that's currently the playing master goes `unavailable` |
| **Latency** | ~5 seconds before re-run + however long the music script takes (~3s) = ~8 seconds total to playback resuming on the new master |
| **Catches** | The case where the master itself dies — without this, the queue dies with it and the whole session ends |
| **Misses** | Cases where no music script was tracking itself (i.e. someone started playback via the Sonos app or Sonos Voice — no record for the failover to re-run) |

Together they cover every common Sonos dropout mode.

## How master failover works

When you start music via an HA script, that script writes its own name to the helper `input_text.sonos_active_script` (e.g. `"play_todays_country"`). The failover automation watches every "master-eligible" speaker for an `unavailable` transition. When one dies AND was the active master AND the helper has a script name, it waits 5 seconds and calls `script.turn_on` on that script.

The targeted music script must have its own master-priority logic — it walks a priority list (e.g. living-room → kitchen → office → bathroom → bedroom) and picks the first speaker that's not unavailable. Since the previous master is now unavailable, the script naturally promotes the next-priority speaker.

If you start playback from the Sonos app or Sonos Voice, the helper isn't populated, and failover is skipped — those sessions die with their master. There's no clean way around this without HA injecting itself into every Sonos session, which would defeat the source-agnostic principle.

## Master detection

The watchdog detects "the current master" dynamically using a Jinja template that looks for any Sonos speaker satisfying:

```python
state == 'playing'
and group_members[0] == self    # speaker is the coordinator of its group
and len(group_members) > 1      # group has more than just the master itself
```

If multiple groups are playing simultaneously (rare), the last one in iteration order wins. The "auto-join candidates" list controls which speakers get pulled into a playing group — exclude any speaker you don't want auto-grouped (e.g. a kid's bedroom).

## Installation

### Option A: Install via Blueprint UI (recommended)

1. Go to **Settings → Automations & Scenes → Blueprints** in HA
2. Click **Import Blueprint**
3. Paste the URL to `blueprints/sonos_watchdog_recovery.yaml` (or import the file manually if you've cloned this repo)
4. Repeat for `blueprints/sonos_watchdog_sweep.yaml` and `blueprints/sonos_watchdog_master_failover.yaml`
5. Click **Create Automation** on each blueprint
6. Configure:
   - **Sonos speakers** — pick every Sonos `media_player.*` entity in your home (used for master detection in recovery and sweep)
   - **Auto-join candidates** (sweep only) — usually the same list, minus any speaker you don't want auto-grouped
   - **Master-eligible speakers** (failover only) — Sonos speakers that can be the master of a playing group, typically excluding portables (Roam, Move)
   - **Recovery delay** (recovery only) — default 3s; bump to 5–8s if Wi-Fi is slow
   - **Sweep interval** (sweep only) — 10–15s recommended
   - **Failover delay** (failover only) — default 5s, lets the network settle after master death

### Required helper for master failover

The failover blueprint needs an `input_text` helper to know which music script to re-run. Create it via:

**Settings → Devices & Services → Helpers → Create Helper → Text** — name it `sonos_active_script`, leave initial value blank.

Or via YAML:
```yaml
input_text:
  sonos_active_script:
    name: Sonos Active Music Script
    initial: ""
    max: 100
```

Each of your music scripts must populate this helper at the start of its sequence. See the **Music script structure** section below.

### Music script structure (failover prerequisite)

For master failover to work, your music scripts need two properties:

1. They write their own name to `input_text.sonos_active_script` at the start
2. They contain master-priority logic — pick a master at runtime from a priority list, falling back to the next available speaker if the preferred one is unavailable

Example skeleton:

```yaml
play_my_playlist:
  alias: My Playlist
  mode: single
  variables:
    favorite_id: "FV:2/3"  # your Sonos Favorite ID
    target_volume: 0.20
    master_priority:        # ordered, top to bottom
      - media_player.living_room
      - media_player.kitchen
      - media_player.office
      - media_player.bathroom
      - media_player.bedroom
    master: >-
      {%- set ns = namespace(m=none) -%}
      {%- for s in master_priority -%}
        {%- if ns.m is none and not is_state(s, 'unavailable') -%}
          {%- set ns.m = s -%}
        {%- endif -%}
      {%- endfor -%}
      {{ ns.m }}
    all_candidates:
      - media_player.kitchen
      - media_player.office
      - media_player.living_room
      # ... etc, all your Sonos speakers
    members: >-
      {{ all_candidates | reject('eq', master) | reject('is_state', 'unavailable') | list }}
  sequence:
    - action: input_text.set_value
      target:
        entity_id: input_text.sonos_active_script
      data:
        value: "play_my_playlist"   # ← MUST match this script's key
    - action: media_player.join
      data:
        group_members: "{{ members }}"
      target:
        entity_id: "{{ master }}"
    - action: media_player.volume_set
      data:
        volume_level: "{{ target_volume }}"
      target:
        entity_id: "{{ [master] + members }}"
    - action: media_player.play_media
      target:
        entity_id: "{{ master }}"
      data:
        media_content_id: "{{ favorite_id }}"
        media_content_type: favorite_item_id
```

Adapt the priority list, candidates, favorite ID, and volume to your setup.

### Option B: Use the Claude Code prompt

If you use [Claude Code](https://claude.ai/claude-code) to manage your HA instance, the `claude-code-prompt.md` in this folder is a copy-paste template that walks Claude through discovering your Sonos speakers, asking which ones should be candidates, and installing both blueprints in your config.

## Telemetry — see how often the watchdog actually fires

Each blueprint writes a `logbook.log` entry every time it repairs something. Open **Logbook** in HA and filter on `Sonos Watchdog` to see a chronological history of every recovery, sweep, and failover event with timestamps and details.

For a numeric counter (so you can see "watchdog has fired 47 times this month" at a glance), add this to your `configuration.yaml`:

```yaml
counter:
  sonos_watchdog_repairs:
    name: Sonos Watchdog Repairs
    icon: mdi:counter
    initial: 0
    step: 1
```

Then in each watchdog automation's actions, add an increment step:

```yaml
- action: counter.increment
  target:
    entity_id: counter.sonos_watchdog_repairs
```

Add a Sensor card on a dashboard pointing at `counter.sonos_watchdog_repairs` to see the running total. Restart HA after first adding the counter (counter helpers don't reload via API).

## Soft assumptions worth knowing

- **Speakers playing on their own are left alone.** The sweep only auto-joins candidates whose state is `idle`. If someone is using the bedroom Sonos for a podcast, the watchdog won't yank it into the kitchen group.
- **Your candidate speakers should have similar volume preferences.** The watchdog matches the recovered speaker's volume to the master's current level. If your bedroom usually plays at 5% and the kitchen at 30%, auto-join will set bedroom to 30% — which might be jarring.
- **The 3-second recovery delay is tuned for typical Sonos.** Some setups need 5–8 seconds before speakers will accept control commands post-reconnect. If you see "join failed" entries in your logs immediately after recoveries, bump the delay.
- **Multiple simultaneous masters aren't supported.** If you have two separate Sonos groups playing at once (rare), only the most recently iterated one will get watchdog coverage. Sonos generally discourages this anyway.

## Troubleshooting

- **Recovery doesn't fire** → check that the speaker actually transitions through `unavailable` and not some other state. Some Sonos integrations report `unknown` or stay in `idle` during dropouts. Look at the entity's state history in HA.
- **Sweep fires but doesn't join** → look at the trace; the `missing` list might be empty because all candidates are `unavailable` rather than `idle`. The sweep deliberately ignores `unavailable` speakers (they need recovery first).
- **Speaker rejoins but at wrong volume** → the master's volume can drift mid-listen. The watchdog matches the master's volume **at the moment of rejoin**, not the volume at script start. This is intentional but worth knowing.
- **Race conditions between recovery + sweep** → both can fire close to each other. `media_player.join` is idempotent so duplicate calls are harmless.

## What this won't fix

- **Sessions started outside HA (Sonos app, Sonos Voice, AirPlay).** The recovery edge and sweep automations work for these because they read live `group_members` state. But master failover only works for sessions started by an HA music script that writes its own name to `input_text.sonos_active_script`. If a Sonos-app session's master dies, the failover has nothing to re-run.
- **AirPlay 2 multi-room dropouts.** AirPlay 2 multi-room is an Apple-side group, not a Sonos group. From HA's perspective, each Sonos speaker is just receiving an AirPlay stream — no `group_members` link to detect.
- **Root-cause Sonos network problems.** This is a recovery system, not a prevention system. If your underlying Wi-Fi/SonosNet is unstable, fix that too — wired Ethernet to one speaker (enabling SonosNet mesh) is the single most impactful network-side fix.

## Contributing

Improvements welcome. Particularly useful additions:
- Per-candidate "expected volume" override (so quiet rooms stay quiet at their preferred level)
- AirPlay 2 multi-room equivalent (much harder — would need to track AirPlay session state)
- Source-agnostic failover (sniff `media_content_id` from the dying master in real time, replay it on the new master without a music-script wrapper)

## License

Public domain. Take it, adapt it, share it.
