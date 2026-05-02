# Diagnosing Sonos Dropouts — A Step-by-Step Guide

If you have chronic Sonos audio dropouts and want to figure out the
real cause instead of guessing, this guide walks you through using the
daemon in this directory to do a methodical diagnosis. The same
methodology produced [`../FINDINGS.md`](../FINDINGS.md) — the Apple
Music master-relay diagnosis.

You will need:

- A computer on the same LAN as your Sonos speakers
- Python 3.8+
- ~10 minutes of setup, ~30 minutes of testing
- The ability to play music from at least 2 different sources
  (Apple Music, Spotify, Sonos Radio, etc.)

## Step 0 — Setup

```bash
git clone https://github.com/cabaynes/sonos-watchdog.git
cd sonos-watchdog/daemon
pip3 install --user -r requirements.txt
```

The daemon needs to be reachable from your Sonos speakers via HTTP
(it spins up a small listener for UPnP NOTIFY callbacks). Most
home networks Just Work; if your Mac/PC is on a guest VLAN or has a
restrictive firewall, move it onto the main network for the test.

## Step 1 — Run the daemon

```bash
python3 sonos_watchdog.py
```

You should see output like:

```
[INFO] discovering Sonos zones...
[INFO] discovered 8 zones: ['Bathroom', 'Bedroom', 'Kitchen', 'Living Room', ...]
[INFO] subscribing to UPnP events...
[INFO] 24 active subscriptions
[INFO] watchdog running. event log: logs/events-YYYYMMDD.jsonl
```

Leave it running. Every UPnP event from every Sonos device is now
being logged to the JSONL file in `logs/`, and mesh signal +
PHY-error counters are polled every 30 seconds.

## Step 2 — Map your full topology

Open a second terminal and run:

```bash
python3 mesh_report.py
```

You'll get a table like:

```
Speaker            Conn                   Ch (MHz)     PHY/30s  Top mesh neighbors
----------------------------------------------------------------------------------
Bathroom           SonosNet (wireless)    2412           37729  Bedroom 59/62, ...
Living Room        SonosNet (Ethernet)    2412           93594  HT Surround #2 67/58, ...
Office             SonosNet (wireless)    2412           47922  Living Room 52/63, ...
...
```

This tells you:

- **Which speakers are on SonosNet vs WiFi** (Sonos's mesh vs your
  home WiFi)
- **What channel SonosNet is using** (channel 2412 = ch 1, 2437 = ch 6,
  2462 = ch 11)
- **Mesh signal quality** between speakers, in both directions
  (FROM/TO; higher is better; 60+ is good, <45 is poor)
- **PHY error rates** per 30 seconds (higher = more radio
  retransmissions / interference)

## Step 3 — Form a problem-sized group

Use the Sonos app to put **all your problem speakers** in one group.
If you don't have a chronic dropout pattern, skip to Step 4 with any
multi-speaker group.

The minimum group size to reproduce the Apple Music master-relay
issue is around **4 speakers**. Smaller groups generally handle
master-relay fine.

## Step 4 — Play 3 sources back-to-back

The crucial test. For each source, play for at least **60 seconds**
and listen carefully for dropouts. Note the time you started each
source.

### Test A — Apple Music

In the Sonos app: Browse → Apple Music → pick any track → play to your
group.

Listen for ~60 seconds. Note any dropouts.

### Test B — Sonos Radio

In the Sonos app: Browse → Sonos Radio → pick any station → play to
your group.

Listen for ~60 seconds. Note any dropouts.

### Test C — Spotify (if you have it)

Two ways:

- **Via Sonos app:** Browse → Spotify → pick a track → play to group
- **Via Spotify Connect:** Open Spotify on your phone → tap the device
  picker → choose your Sonos group → play

Both are worth trying separately if you have the time.

## Step 5 — Read the URL schemes

While each source is playing, check the daemon log:

```bash
python3 tail_events.py 30
```

Look for lines like:

```
22:20:45.365  Living Room    avTransport seq=4  PLAYING  current_track_uri=x-sonos-http:song%3a1883177267.mp4?sid=204&...
```

The `current_track_uri` is the giveaway. Match it against this table:

| URL pattern | Source | Architecture | Expected reliability |
|---|---|---|---|
| `x-sonos-http:song...sid=204` | Apple Music | Generic master-relay | Drops in groups ≥4 |
| `x-sonos-http:sonos:...DZR:...:head/middle/tail:` | Sonos Radio | Chunked HLS | Reliable |
| `x-sonos-spotify:spotify:track:...` | Spotify (Sonos app) | Dedicated protocol | Reliable |
| `x-spotify-connect:` (or similar) | Spotify Connect | Spotify's own protocol | Reliable |
| `x-rincon-stream:` | Line-in / Sonos Connect | Direct PCM | Reliable |
| `x-rincon-mp3radio:` | TuneIn / generic stream | Direct stream | Usually reliable |
| `x-sonosapi-radio:` | Sonos's older radio path | Variable | Variable |
| `x-file-cifs:` | SMB share / local library | Direct fetch | Reliable |

If your **only dropouts** are on `x-sonos-http:song...sid=204` Apple
Music URIs and **all other URI types play cleanly**, you've reproduced
the Apple Music master-relay finding.

## Step 6 — Check the negative evidence

Equally important — confirm the dropouts have nothing to do with the
network. While Apple Music is dropping, run:

```bash
python3 mesh_report.py
```

If your mesh signal scores haven't degraded compared to baseline (Step
2) and PHY error rates are similar or **lower** than at idle, then the
network is fine. The dropouts are happening upstream of SonosNet.

You can also grep the log for any topology / state changes during the
audible dropout window:

```bash
grep '"kind":"upnp_event"' logs/events-*.jsonl | grep -v '"service":"renderingControl"' | tail -50
```

If you see no topology changes and no transport-state changes during
the dropouts, that's confirmation the failure is invisible to UPnP —
which means it's audio-stream buffer starvation, not group churn.

## Step 7 — Apply the workarounds

If you've confirmed the Apple Music master-relay pattern, your options
are:

1. **Use Spotify or Sonos Radio for whole-house listening.** They use
   different protocol paths and don't have the bottleneck.
2. **Use AirPlay 2 from your iPhone or Mac for whole-house Apple
   Music.** Each speaker gets its own independent stream from your
   controller — no master-relay involved.
3. **For native Sonos Apple Music, cap your groups at 3 speakers.**
   Smaller groups stay under the master's relay capacity.
4. **Lower Apple Music quality** (Apple Music app → Settings →
   Audio → set to High or Standard, not Lossless). Reduces relay
   load. Useful if you want occasional bigger Apple Music groups.

See the full discussion in [`../FINDINGS.md`](../FINDINGS.md).

## Bonus: verifying which quality tier your Sonos actually pulls

A common myth: "I set my phone's streaming quality to Lossless, so my
Sonos must be playing lossless." This is **almost always false**.

Sonos doesn't ask your controller phone what quality to use. It
authenticates as its own client to the streaming service and pulls
whatever quality tier the **service's Sonos integration is configured
to deliver** — which depends on (1) your account's entitlement, and
(2) whether Sonos's firmware has shipped support for that tier yet.

Sonos historically lags 6-12 months behind streaming services on
adding new lossless tiers (e.g., Apple Music Lossless took ~year+
after launch; Amazon Music HD took similar). So even when a service
adds lossless, you may still be getting the previous tier on Sonos.

The daemon lets you verify what Sonos is actually receiving in 30
seconds, without taking the service's word for it.

### Procedure

1. **Note your current playback URI** while music is playing:

```bash
python3 tail_events.py 5 | grep -E "(spotify|sonos-http|rincon|x-spot|x-file)"
```

You're looking for a line like:

```
HH:MM:SS  Living Room    avTransport seq=N  PLAYING  current_track_uri=x-sonos-spotify:spotify:track:...?sid=12&flags=8232&sn=6
```

The `flags=N` value is the encoding tier identifier (per-service).

2. **Toggle the quality setting** in the streaming service's controller
   app (e.g., Spotify → Settings → Audio Quality → Lossless).

3. **Force a fresh stream** by skipping the track on Sonos (or stopping
   and restarting playback).

4. **Re-check the URI**:

```bash
python3 tail_events.py 5 | grep -E "(spotify|sonos-http|rincon|x-spot|x-file)"
```

If `flags=` **changed**, the new tier reached Sonos. If `flags=` is
**identical**, Sonos is still pulling the previous tier and your phone's
toggle had no effect on what the speakers received.

### Known flag values

| URL pattern | flags= | Tier |
|---|---|---|
| `x-sonos-spotify:` | 8232 | Spotify Premium 320 kbps Ogg Vorbis (as of 2026-05-01) |

Other services not yet characterized — please contribute findings via
PRs or issues.

### Implication for the Apple Music workaround

The TL;DR workaround in [`../FINDINGS.md`](../FINDINGS.md) recommends
Spotify via Sonos for full-house multi-room. Be aware that Spotify on
Sonos is currently capped at 320 kbps Ogg Vorbis even if your Spotify
account has the lossless tier — Sonos firmware doesn't yet pull
Spotify lossless. You're getting the highest quality Spotify offered
prior to lossless, which is excellent quality but not lossless.

For genuine lossless multi-room you currently have to use either:

- **AirPlay 2 from iPhone with Apple Music Lossless** — Apple
  downsamples 24/192 hi-res to 16/44.1 ALAC for AirPlay 2, but you
  get true CD-quality lossless to each speaker independently.
- **Tidal / Qobuz / Amazon Music HD** as a Sonos music service —
  these may or may not hit the same Apple-Music-relay bottleneck.
  Use the procedure above to check the URL scheme and flags, and
  the methodology in Step 4 to test for dropouts on multi-speaker
  groups.

## Other patterns this toolkit can diagnose

Even if you don't reproduce the Apple Music finding, the daemon is
useful for:

### "Speakers drop out randomly during music"

Look at the JSONL log for `transport_state=TRANSITIONING` events on
satellites mid-track, or `zone_group_state` changes that drop a
member. These are real UPnP-visible drops and have different causes
(usually RF / WiFi hand-off / firmware bugs). Mesh signal + PHY error
correlation will tell you if it's RF.

### "Group startup is slow"

Time the events from `transport_state=STOPPED` → first
`transport_state=PLAYING` after issuing playback. Anything beyond ~5
seconds suggests the master is struggling to negotiate the group.
Often resolves with a master change or by reducing group size.

### "One specific speaker always drops first"

Look at that speaker's entries in the mesh signal report. If its
RSSI scores to its peers are noticeably lower, you have a physical /
RF problem at that speaker (placement, distance, walls, interference
near it). Move it, add a Boost, or accept that it'll drop.

### "Dropouts cluster around certain times"

Tail the log over a multi-hour window. If dropouts cluster around
microwave usage, neighbor activity, or specific WiFi events, that's
2.4 GHz interference. Try changing SonosNet to a different channel
(Sonos app → Settings → System → Network → SonosNet Channel).

## How to share your findings

If you reproduce the Apple Music master-relay finding (or find a
*different* dropout root cause):

- Open an issue on this repo with your URL schemes, mesh signal
  table, and what you heard
- Anonymized JSONL excerpts are welcome
- Especially valuable: data from setups with different speaker mixes,
  network configurations, or firmware versions

The body of evidence helps everyone.

## Limitations

- The daemon only sees what the speakers themselves report. It can't
  detect issues upstream of the master (e.g., a flaky internet
  connection between Apple's CDN and the master speaker).
- Mesh-signal scores are Sonos's proprietary metric, not standard RSSI
  in dBm. The 0-100 scale is informal; consider it relative within
  your own setup, not absolute.
- The daemon doesn't currently poll `RelativeTimePosition`. If you
  want to detect buffer-starvation stalls programmatically, add a
  poller for `avTransport.GetPositionInfo` on each satellite — if
  state=`PLAYING` but `RelTime` isn't advancing in real time, it's
  stalled.
- The `auto_renew=True` UPnP subscription parameter has occasional
  hiccups in `soco` ≤0.31. Long runs may need a daemon restart every
  few days. Production use should add a healthcheck that detects
  silent subscription failures.
