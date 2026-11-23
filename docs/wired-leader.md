# Wired speaker leads (optional)

In a Sonos group, one speaker leads: it fetches the music and streams it to the others.
When a group includes a speaker on Ethernet, that speaker makes the better leader, because
its streams to the rest start from the wire instead of from another speaker's radio. Sonos
picks the leader itself (usually the room you started from), so it often isn't the wired one.

With this set up, the watchdog moves the lead to your wired speaker **whenever the group
has been paused for 30 seconds** (adjustable). It uses Sonos's own handover, so the song,
position and queue stay exactly as they were.

**Why only during a pause:** moving the lead while music plays put a group audibly out of
sync until it was rebuilt. The same handover during a pause kept every room in sync, in
both directions, and when play was pressed in the middle of a handover the press was simply
ignored (tested November 2026; see FINDINGS.md).

## Setup

1. Add this to `configuration.yaml` and restart Home Assistant:

   ```yaml
   rest_command:
     sonos_delegate:
       url: "http://{{ ip }}:1400/MediaRenderer/AVTransport/Control"
       method: post
       content_type: 'text/xml; charset="utf-8"'
       headers:
         SOAPACTION: '"urn:schemas-upnp-org:service:AVTransport:1#DelegateGroupCoordinationTo"'
       timeout: 15
       payload: >-
         <?xml version="1.0" encoding="utf-8"?><s:Envelope
         xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
         s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:DelegateGroupCoordinationTo
         xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><NewCoordinator>{{ uid }}</NewCoordinator><RejoinGroup>1</RejoinGroup></u:DelegateGroupCoordinationTo></s:Body></s:Envelope>
   ```

2. In your Sonos Watchdog automation, pick your Ethernet speaker(s) under **Wired speakers**
   and enter `rest_command.sonos_delegate` as the **Handover command**.

The watchdog fills in `ip` (the current leader's address) and `uid` (the wired speaker's
Sonos ID) from Home Assistant's device registry. Each move is logged as `leader_moved`.

## What it won't do

- Move the lead while music is playing, or while the Arc plays TV or line-in audio.
- Move it to a wired speaker that's offline.
- Anything at all if the handover command is left empty — then the log only records, at
  each session start, whether the leader was wired (`wired=yes/no`).

During a handover (about 2 seconds) the old leader may briefly report "playing" with no
song. That's normal and settles by itself.
