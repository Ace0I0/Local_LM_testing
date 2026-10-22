# Artemis Domain Language

Artemis observes local household sensor state and explains it without controlling devices.

## Language

**Sensor Node**:
An ESP32 deployment that publishes environmental measurements and availability for one physical location.
_Avoid_: Device, board

**Location ID**:
The lowercase snake-case identifier for a Sensor Node's installed location, such as `living_room`.
_Avoid_: Node ID, room name, hardware ID

**Measurement State**:
The latest valid numeric reading for one environmental quantity at a Location ID.
_Avoid_: Event, sample history

**Availability**:
The Sensor Node's retained MQTT connectivity state, either `online` or `offline`; it does not guarantee that its measurements are fresh.
_Avoid_: Health, freshness

**Stale Reading**:
A Measurement State that has not received a valid update within three configured reporting intervals.
_Avoid_: Offline reading
