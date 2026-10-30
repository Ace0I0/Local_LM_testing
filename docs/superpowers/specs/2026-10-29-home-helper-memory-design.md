# Home Helper Memory Design

## Intent

Replace Artemis's EAS/analog-horror identity and knowledge base with a
local-first household helper appropriate for the Raspberry Pi, Home Assistant,
and read-only environmental sensors.

## Goals

- Make the default identity calm, practical, concise, and privacy-aware.
- Keep factual sensor state authoritative and separate from model phrasing.
- Give general questions a small, truthful local knowledge base.
- Remove fictional agencies, hazards, creatures, contacts, locations, and
  emergency-broadcast language completely.

## Non-goals

- User-selectable modes or a mode-switching UI.
- Device control, cloud services, personal-profile storage, or fabricated home
  facts.
- Changing MQTT topics, sensor validation, the Qwen endpoint, or SAM settings.

## Approaches

1. Replace the hardcoded EAS mode with one hardcoded Home Helper mode and
   replace the lore files and their routing map. Chosen because one current
   persona is the smallest complete fit for the present terminal interface.
2. Keep EAS as an optional mode. Rejected: the old identity would remain in
   active code and routing despite the request to remove it completely.
3. Remove all knowledge loading. Rejected: Artemis would lose its grounded
   capability description and its selective-context architecture.

## Design

memory/modes/home_helper.json becomes the sole loaded mode. It instructs
Artemis to speak plainly, distinguish live sensor facts from general guidance,
state uncertainty, avoid claiming device-control authority, and avoid
inventing household details.

memory/identity.json describes Artemis as a local home helper. The knowledge
directory contains only:

- home_helper_overview.txt: current capabilities, limits, and local-first
  privacy behavior;
- sensor_guidance.txt: temperature and relative-humidity terminology,
  availability and freshness meanings, without alert thresholds or advice;
- safety_boundaries.txt: brief real-world escalation boundaries for immediate
  danger and medical emergencies.

The router and token budget use these three filenames, with intent names
renamed away from EAS terminology. The controller defaults, debug text, README,
and tests use Home Helper naming. active_mode.txt, the three old mode JSON
files, and every eas_*.txt file are deleted.

## Safety and Privacy

Artemis never invents home occupants, addresses, contacts, devices, rooms, or
historical measurements. It does not replace emergency or medical services,
does not claim to control devices, and does not send user prompts or sensor
data to external services.
