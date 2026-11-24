# Reddit post draft — r/homeassistant

> Draft only. Whether and where to post it is the repo owner's call. Title goes in the title
> field, the body below in the body. Cross-posting to the HA Community Forum's
> [Blueprint Exchange](https://community.home-assistant.io/c/blueprints-exchange/53) is the
> long-term home for blueprints.

---

**Title:**

```
Sonos Watchdog v3 — a blueprint that puts dropped Sonos speakers back in the group, logs every session, and is honest about what it can't fix
```

**Flair:** Blueprint (or "Share")

**Body:**

```markdown
**TL;DR:** One Home Assistant blueprint. When a Sonos speaker in your playing group drops off the network and comes back, it goes back into the group. It logs every listening session, speaker drop and repair (optionally to a file and as monthly totals). And it says plainly what it *can't* do: the most common Sonos dropout — a speaker staying in the group but going silent — is invisible to Home Assistant.

GitHub: https://github.com/cabaynes/sonos-watchdog

## Two kinds of Sonos dropout

1. **A speaker leaves the group** — it falls off the network (Wi-Fi blip, reboot, power cut). Home Assistant sees it go `unavailable`. **This blueprint fixes that one.**
2. **A speaker stays in the group but goes silent** for seconds at a time. Everything still reports "playing", so no automation can see it. I spent a while diagnosing this one: it's the group's leader failing to keep up with streaming to the others, worse with lossless and big groups. The write-up (FINDINGS.md in the repo) has what actually helps: Spotify at 320 kbps instead of lossless for big groups, smaller groups, a wired speaker leading.

## What v3 does

- Remembers which speakers belong to the session you started (from the Sonos app, a preset, Sonos Voice, anything).
- If one goes offline and comes back, it's rejoined within seconds of Home Assistant noticing — which, for a speaker that lost power, took about 5 minutes after it booted in my test (Sonos itself never regrouped it).
- If one leaves while still online, it assumes **you** did that (ungrouped it, switched preset) and leaves it alone.
- Never touches volume and never pulls in a speaker that's busy playing something else.
- Logs `session_start`, `speaker_left` (offline or online), `speaker_back`, `repair`, `session_end` with who led and the source.

## Install

Create a text helper (max length 255), then import:

[Import blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcabaynes%2Fsonos-watchdog%2Fblob%2Fmain%2Fblueprints%2Fsonos_watchdog.yaml)

and create one automation from it. Optional log file and monthly-totals setup is in the README.

Upgrading from v1/v2 (three blueprints + master failover): delete those automations; the README has the steps.

## Feedback welcome

Especially: whether your drops are the "left the group" kind or the "silent in the group" kind (the log will tell you how many of the first kind you get), and data from other setups for FINDINGS.md.

MIT licensed.
```
