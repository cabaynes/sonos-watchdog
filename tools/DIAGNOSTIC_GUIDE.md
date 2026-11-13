# Diagnosing Sonos Dropouts — A Step-by-Step Guide

If you have chronic Sonos audio dropouts and want to figure out the
real cause instead of guessing, this guide walks you through using the
tools in this directory to do a methodical diagnosis. The same
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
cd sonos-watchdog/tools
pip3 install --user -r requirements.txt
```

The recorder needs to be reachable from your Sonos speakers via HTTP
(it spins up a small listener for UPnP NOTIFY callbacks). Most
home networks Just Work; if your Mac/PC is on a guest VLAN or has a
restrictive firewall, move it onto the main network for the test.

## Step 1 — Run the event recorder

```bash
python3 event_recorder.py
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
python3 sonos_health.py
```

You'll get a table like:

```
Speaker          IP              Link        MHz  PHY err/s  Strongest neighbours
------------------------------------------------------------------------------------------------
Bathroom         192.168.1.20    SonosNet   2462        522  Bedroom 59/64 good, Kitchen 50/49 weak
Living Room      192.168.1.21    WIRED      2462       2265  Kitchen 68/57 ok, ...
Roam             192.168.1.22    WiFi       5785        433  -
...
Playing groups:
  Living Room leads ['Kitchen', 'Living Room', 'Office']  wired-led: yes
```

Friendly neighbour names come from an optional `labels.local.json` (radio MAC → name);
without it you see the last part of each MAC.

This tells you:

- **Which speakers are on SonosNet vs WiFi** (Sonos's mesh vs your
  home WiFi)
- **What channel SonosNet is using** (channel 2412 = ch 1, 2437 = ch 6,
  2462 = ch 11)
- **Mesh signal quality** between speakers, in both directions
  (FROM/TO; higher is better; 60+ is good, <45 is poor)
- **PHY error rates** per second (higher = more radio corruption /
  interference; compare speakers, there's no official threshold)
- **Which speaker leads each playing group**, and whether it's wired

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

While each source is playing, check the recorder log:

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
python3 sonos_health.py
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

If you've confirmed the master-relay bottleneck pattern (any service +
multi-speaker), your options are:

1. **Use a low-bandwidth source for whole-house listening.** Spotify
   320 kbps Ogg Vorbis or Sonos Radio — both confirmed reliable on
   7-speaker groups.
2. **Keep a wired speaker as the leader** of big groups (start the
   group from the wired room). Avoid AirPlay to several speakers:
   Sonos groups them and one relays to the rest, so it is *not* a
   bypass (see FINDINGS.md, "What we learned since").
3. **For native in-app lossless** (any service): cap groups at
   ≤3 speakers.
4. **For native Sonos Apple Music**: cap at 3 speakers regardless of
   quality tier (Apple Music's relay overhead is heavier than other
   services even at non-lossless tiers).
5. **Lower the streaming service's quality** if you want bigger
   native Sonos groups (Apple Music app → Audio → not Lossless;
   Spotify → Media Quality → Very High not Lossless).

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

The recorder lets you verify what Sonos is actually receiving in 30
seconds, without taking the service's word for it.

### Procedure

The reliable indicator is **the streaming app's UI badge in the Sonos
or controller app** — not the URL `flags=` field. We initially
assumed the URI's `flags=` parameter encoded quality, but follow-up
testing showed it doesn't reliably change with quality. Use UI badges
+ audible behavior + (if needed) bandwidth correlation in the recorder.

1. **Verify the UI badge.** While playing on Sonos:
   - **Sonos app**: tap the Now Playing bar. A "Lossless" badge
     appears below the track title when lossless content is playing.
   - **Spotify app's connect picker**: a "Lossless" badge appears
     below the playback controls when streaming lossless to a Sonos
     target.
   - If you don't see a "Lossless" badge, you're not getting lossless
     regardless of what the URL says.

2. **For the comparison test**, enable lossless via the
   service-specific procedure (Spotify requires both a global Audio
   Streaming setting AND a per-Sonos "Change Quality Settings" toggle
   inside the Spotify Connect picker — see Sonos's official
   instructions). Then:

   - Note current behavior: dropouts on N-speaker group? Badge
     showing?
   - Toggle the per-Sonos quality setting back to a non-lossless tier
   - Skip a track on Sonos to force a fresh stream
   - Verify the badge disappears
   - Note new behavior: dropouts gone?

3. **Optional: correlate with the recorder log** to confirm timing of
   stream changes via `python3 tail_events.py 30`. Look for fresh
   `avTransport seq` events with new track URIs. The URI's `sid=`
   field identifies the service. The `flags=` field has *some*
   semantic meaning but isn't a reliable quality indicator.

### Known patterns observed

| URL pattern | sid= | Service | Notes |
|---|---|---|---|
| `x-sonos-spotify:spotify:track:...` | 12 | Spotify | Quality controlled by per-Sonos "Change Quality Settings" toggle. Lossless on 6+ speakers triggers master-relay dropouts. |
| `x-sonos-http:song...` | 204 | Apple Music | Generic master-relay; dropouts on 4+ speaker groups regardless of quality tier |
| `x-sonos-http:sonos:...DZR:...` | — | Sonos Radio | Chunked HLS; reliable on full-house groups |

Other services not yet characterized — please contribute findings via
PRs or issues.

### Implication for the Apple Music workaround

The TL;DR workaround in [`../FINDINGS.md`](../FINDINGS.md) recommends
Spotify via Sonos for full-house multi-room. Important nuance based on
2026-05-01 testing:

- **Spotify at 320 kbps ("Very High", non-lossless)** — confirmed
  reliable on 7-speaker groups. The dedicated `x-sonos-spotify:`
  protocol path handles this bandwidth fine.
- **Spotify Lossless** — Sonos DOES pull lossless when properly
  enabled (per-Sonos "Change Quality Settings" toggle inside the
  Spotify Connect picker), but lossless on 6+ speaker groups
  produces the same master-relay dropout pattern as Apple Music.
  ~1 Mbps × 6 unicast streams saturates the master regardless of how
  optimized the relay code path is.

For genuine lossless multi-room on full-house groups (6+ speakers),
your reliable options are:

- ~~AirPlay 2 from iPhone~~ — withdrawn: AirPlay to several Sonos
  speakers forms a relaying Sonos group (FINDINGS.md).
- **Tidal / Qobuz / Amazon Music HD** as a Sonos music service —
  given the bandwidth principle, expect any service's lossless tier
  to hit the same wall on 6+ speakers regardless of the underlying
  protocol path. Test with the recorder to confirm.

For lossless on small groups (≤3 speakers), any of these services'
lossless tiers should work fine.

## Other patterns this toolkit can diagnose

Even if you don't reproduce the Apple Music finding, the tools are
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

- The tools only see what the speakers themselves report. It can't
  detect issues upstream of the master (e.g., a flaky internet
  connection between Apple's CDN and the master speaker).
- Mesh-signal scores are Sonos's proprietary metric, not standard RSSI
  in dBm (roughly 0–62 in practice). Treat it as relative within your
  own setup, not absolute.
- Silent in-group dropouts can't be detected: the group keeps
  reporting `PLAYING` with an advancing position, and 2026 firmware's
  diagnostic pages have no audio-buffer counters. `watch_group.py`
  flags what *is* visible (stalls, leaves, reconnects, slow answers).
- UPnP subscriptions can lapse silently over long runs. The recorder
  is meant for a session of testing, not to run for weeks.
