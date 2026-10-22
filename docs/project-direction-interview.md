# Artemis Project Direction Interview

Last updated: 2026-10-21

This is the living record of the decisions guiding Artemis. New interview answers should be added here before implementation plans are written.

## Current direction

Artemis will become a local-first home helper running on a Raspberry Pi 5. The first version will observe basic smart-home sensors over a local MQTT network, explain current conditions, summarize changes, and report unusual readings. It will not control devices.

## Questions and decisions

### 1. What should Artemis primarily become?

**Answer:** A local LLM home helper that can eventually use contextual information such as weather, time, and location.

**Decision:** Prioritize practical household assistance over the existing EAS/lore experience or physical robotics.

### 2. May Artemis use the internet?

**Answer:** Selected internet access may eventually provide live weather and news, but the first version should remain local and offline.

**Decision:** Defer internet integrations. Future online tools must use approved sources rather than treating model knowledge as current information.

### 3. May Artemis control devices?

**Answer:** The first version should observe and report only, with autonomous control remaining a possibility for later versions.

**Decision:** Version one receives read-only access. Do not implement device-control commands or automation authority.

### 4. What local input should be supported first?

**Answer:** Basic sensors, because those are the devices currently available in the home.

**Decision:** Defer camera analysis. Start with readings such as temperature, humidity, motion, door/window state, or air quality, depending on the available hardware.

### 5. How should sensors communicate?

**Answer:** MQTT as the communication backbone, Mosquitto as the broker, and Home Assistant as the primary dashboard.

**Decision:** Sensors publish locally to Mosquitto. Home Assistant displays and organizes their state. Artemis subscribes only to approved sensor topics as a read-only consumer.

### 6. Where should the services run?

**Answer:** Run Artemis, Mosquitto, and Home Assistant on one Raspberry Pi 5 initially. A spare older Mac mini is available but is not part of the first deployment.

**Decision:** Optimize the prototype for a single Raspberry Pi 5 with 16 GB of RAM. Avoid depending on a second computer, while keeping service boundaries clear enough to move components later.

### 7. Which sensors should be supported first?

**Answer:** Temperature and humidity are the two main priorities. Air-quality sensing, particularly airborne particle measurements, is also wanted if suitable sensors are available.

**Decision:** Build the first sensor flow around temperature and relative humidity. Treat particulate air-quality readings as the next sensor category, not a requirement for the initial milestone.

### 8. How should Artemis report sensor information?

**Answer:** Provide readings on request, generate a current summary every day, and allow a live view of current information.

**Decision:** Support three presentation paths: conversational queries through Artemis, a scheduled daily household summary, and a live Home Assistant dashboard backed by the same MQTT readings.

### 9. Where should summaries and live information appear?

**Answer:** A display connected to the Raspberry Pi should host a local dashboard for live readings and summaries. Voice output should remain inactive until the user asks Artemis something.

**Decision:** Use the Pi-connected display as the always-available interface, initially showing the local Home Assistant dashboard. Show daily summaries on the display. Treat speech as request-triggered output rather than an automatic announcement channel.

### 10. How should a user initiate a request?

**Answer:** Users should be able to say the wake word "Artemis" or use a physical push-to-talk button.

**Decision:** Support two explicit local activation paths. Wake-word detection opens a voice session after hearing "Artemis." The physical button opens the same session without requiring the wake word. Microphone capture and speech recognition should remain local.

### 11. What microphone hardware is available?

**Answer:** No microphone is available yet, so push-to-talk should be used first.

**Decision:** Defer wake-word detection. Prioritize the physical push-to-talk flow when voice input is added, while allowing sensor collection and the display dashboard to proceed without microphone hardware. A microphone will still be required to capture speech during push-to-talk.

### 12. What input hardware can support the first milestone?

**Answer:** A keyboard is already connected to the Raspberry Pi, and USB microphones are available but have not been tested with the Pi.

**Decision:** Keep keyboard input as the reliable fallback. Test an existing USB microphone for the first push-to-talk implementation before buying different audio hardware. Wake-word detection remains a later enhancement.

### 13. What form does the existing sensor hardware take?

**Answer:** The sensors are bare electronic modules that must be soldered to ESP32 boards.

**Decision:** Treat each ESP32 as a peripheral sensor node that reads its attached modules and publishes measurements to the local MQTT broker. The Raspberry Pi remains the host for Artemis, Mosquitto, Home Assistant, and the display. This does not make the Artemis repository an ESP32-focused project.

### 14. How should the ESP32 sensor nodes be configured?

**Answer:** ESPHome with MQTT is the preferred approach.

**Decision:** Use ESPHome configurations rather than custom Arduino or PlatformIO firmware. Each node should publish sensor readings to Mosquitto using a consistent topic and payload convention.

### 15. Where should ESPHome configurations live?

**Answer:** In a separate sensor-node repository.

**Decision:** Keep ESPHome and ESP32 configuration outside this repository. This Artemis repository will document and consume the MQTT topic contract while remaining focused on the local LLM, sensor interpretation, summaries, and user interface.

## Confirmed constraints

- Local and offline for the first version
- One Raspberry Pi 5 with 16 GB of RAM
- Basic sensors before cameras
- Temperature and relative humidity before air-quality monitoring
- ESP32-based peripheral sensor nodes publishing readings to the Raspberry Pi
- ESPHome with MQTT rather than custom ESP32 firmware
- ESPHome configurations maintained in a separate sensor-node repository
- MQTT communication through Mosquitto
- Home Assistant as the primary dashboard
- Artemis has read-only sensor access
- On-demand answers, daily summaries, and a live sensor dashboard
- Raspberry Pi-connected display as the default always-on interface
- No unsolicited spoken announcements
- Physical push-to-talk before local "Artemis" wake-word activation
- Keyboard input as a fallback and an existing USB microphone as the first voice-input candidate
- Internet data and autonomous control are future work

## Open decisions

- Which temperature/humidity sensor models and connection protocol to use
- Which particulate measurements and sensor hardware to support later
- MQTT topic naming and payload format
- What history Artemis should retain for daily summaries
- Which conditions count as unusual or alert-worthy
- How users will ask Artemis for sensor information
- What time the daily display summary should refresh
- Whether an existing USB microphone works reliably with the Raspberry Pi
- Which local speech-recognition engine to use
- Whether the existing EAS personality remains a selectable mode
