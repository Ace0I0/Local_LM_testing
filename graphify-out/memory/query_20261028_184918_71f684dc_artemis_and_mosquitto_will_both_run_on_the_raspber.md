---
type: "query"
date: "2026-10-28T18:49:18.668794+00:00"
question: "Artemis and Mosquitto will both run on the Raspberry Pi; SSH access is available for testing or coding."
contributor: "graphify"
outcome: "useful"
source_nodes: ["MqttSensorClient", "Mosquitto Setup Wizard", "Broker Acceptance Checks", "Artemis Local LLM Voice Assistant"]
---

# Q: Artemis and Mosquitto will both run on the Raspberry Pi; SSH access is available for testing or coding.

## Answer

Expanded from graph vocabulary: [artemis, mosquitto, mqtt, broker, setup, client, sensor, password, sam, test]. Because Artemis and Mosquitto share the Pi, the existing 127.0.0.1 broker default is correct and no MQTT-host code change is needed. The next action is a read-only SSH audit of Mosquitto, MQTT port 1883, retained sensor messages, repository state, Python environment, SAM, llama-server, and available model files. Then install only missing dependencies, run the test suite, and perform a live Artemis sensor-question test before benchmarking models. Do not copy secrets.h or change firmware unless the live topic contract fails.

## Outcome

- Signal: useful

## Source Nodes

- MqttSensorClient
- Mosquitto Setup Wizard
- Broker Acceptance Checks
- Artemis Local LLM Voice Assistant