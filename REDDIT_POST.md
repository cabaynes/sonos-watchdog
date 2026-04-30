# Reddit post draft — r/homeassistant

> Save this file for reference. Copy the text below the divider into a new post on r/homeassistant. Title goes in the title field; body goes in the body field. The HA "My" import URLs render as clickable buttons on most browsers when posted.

---

**Title:**

```
Sonos Watchdog — three HA blueprints that auto-rejoin Sonos speakers when they drop out of a group
```

**Flair:** Blueprint (use the "Blueprint" flair if r/homeassistant has one; otherwise "Share")

**Body:**

```markdown
**TL;DR:** I built three Home Assistant blueprints that monitor a Sonos group during playback and automatically rejoin any speaker that drops out — whether it goes fully offline or quietly leaves the group while staying online. Source-agnostic (works whether you started playback from HA, the Sonos app, or Sonos Voice). It also handles the worst case: if the master speaker itself dies, it elects a new master from a priority list and resumes playback.

GitHub: https://github.com/cabaynes/sonos-watchdog

## The problem

If you have multi-room Sonos and use it grouped, you've probably hit the chronic dropout problem: a speaker just… leaves the group mid-song. Sometimes it goes `unavailable` (network drop), sometimes it stays online but silently drops out of the group. The Sonos app has no auto-recovery. Re-grouping manually breaks the listening flow, and most apartments / dense Wi-Fi environments make this happen multiple times per listening session.

I have a wired Ethernet anchor on my soundbar and STILL hit this constantly. Sonos support has been useless. So I stopped trying to fix Sonos and started letting HA do the recovery instead.

## What it does

Three automations, each handling a different failure mode:

**1. Speaker Recovery (event-driven, ~4–8s repair)**
Triggers when any Sonos speaker transitions `unavailable → idle/playing/paused`. If a Sonos master is currently playing a group, the recovered speaker is auto-joined and its volume matched to the master.

**2. Periodic Group Sweep (timer-driven, configurable interval)**
Every 10–15 seconds, looks for "online + idle but not in the active group" speakers and joins them in. This catches the silent-drop case where the speaker never goes `unavailable` — just quietly leaves. The recovery automation can't see this; only the sweep can.

**3. Master Failover (event-driven)**
The painful case: if the master speaker itself dies mid-playback, the queue dies with it and the whole session ends. This automation watches your "master-eligible" speakers, and if the playing master goes `unavailable`, it re-runs your active music script — which (with master-priority logic in the script) elects the next-priority speaker as new master and reforms the group.

## Source-agnostic

The recovery and sweep automations detect the master dynamically by looking at every Sonos speaker's `group_members` attribute. So it works whether playback was started by:

- An HA script
- The Sonos app
- Sonos Voice ("Hey Sonos, play X in the kitchen")
- Anything that creates a Sonos native group

The master failover requires HA-script-driven playback (it needs to know which script to re-run). For app/Voice-started sessions, the recovery and sweep still work — only failover doesn't apply.

## Install

Click each "Import Blueprint" button on a device where you're logged in to HA:

- **Recovery:** [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcabaynes%2Fsonos-watchdog%2Fblob%2Fmain%2Fblueprints%2Fsonos_watchdog_recovery.yaml)
- **Sweep:** [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcabaynes%2Fsonos-watchdog%2Fblob%2Fmain%2Fblueprints%2Fsonos_watchdog_sweep.yaml)
- **Master failover:** [Import](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcabaynes%2Fsonos-watchdog%2Fblob%2Fmain%2Fblueprints%2Fsonos_watchdog_master_failover.yaml)

Or grab the YAML files directly from [the GitHub repo](https://github.com/cabaynes/sonos-watchdog/tree/main/blueprints) and drop them into `/config/blueprints/automation/sonos-watchdog/`.

After importing, create an automation from each blueprint. Configuration is one-time:

- **Sonos speakers** — pick every Sonos `media_player.*` entity in your home
- **Auto-join candidates** (sweep) — usually the same list, minus any speaker you don't want auto-grouped
- **Master-eligible speakers** (failover) — typically excludes portables (Roam, Move)

The full README has detailed install steps, a music-script template (required for failover), troubleshooting, and a Claude Code prompt for AI-assisted installation if you use it: https://github.com/cabaynes/sonos-watchdog

## What it won't fix

- **AirPlay 2 multi-room dropouts** — AirPlay groups aren't Sonos groups, so HA can't see the membership relation to repair it.
- **Root-cause Sonos network problems** — this is recovery, not prevention. If your Wi-Fi/SonosNet is broken, fix that too. Wired Ethernet to one Sonos speaker is the single most impactful network-side fix.
- **Sessions started outside HA where the master dies** — failover needs to know which script to re-run. App/Voice-started sessions don't populate that helper, so a master death there ends the session.

## Telemetry

Each blueprint writes a `logbook.log` entry per repair, so you can open the Logbook in HA and filter on "Sonos Watchdog" to see exactly when and how often things are firing. The README has an optional counter setup if you want a numeric "lifetime repairs" total on a dashboard card.

## Feedback welcome

This is v1. I'd love to hear:
- Whether it actually helps in your environment
- Bug reports (GitHub issues)
- Improvement ideas — particularly source-agnostic failover (sniff `media_content_id` from the dying master and replay it without a music-script wrapper) and per-candidate "expected volume" overrides

MIT licensed. Take it, fork it, share it.
```

---

## Notes for posting

- The Blueprint Import buttons rely on the `my.home-assistant.io` redirect — these are HA's official "click to install" links. They render as clickable buttons in the HA mobile app and on any browser with HA logged in.
- If r/homeassistant has a Blueprint flair, use it. Otherwise "Share" or "Help" depending on subreddit conventions.
- Engagement tip: respond quickly to the first 3-4 comments. Mods sometimes pin good blueprint posts if there's discussion.
- Cross-post to the [HA Community Forum's Blueprint Exchange](https://community.home-assistant.io/c/blueprints-exchange/53) too — that's the canonical home for HA blueprints and where most users will discover this long-term. Same body content; just paste into a forum thread.
- After posting, link the Reddit post + forum thread back from the GitHub README under a "Discussion" section so future visitors can find the conversation.
