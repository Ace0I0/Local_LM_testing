---
type: "query"
date: "2026-10-28T18:40:40.552877+00:00"
question: "Now that ESP32 Wi-Fi and Home Assistant temperature/humidity work, should work continue on ESP32 code or move to the LLM/SLM side?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["MqttSensorClient", "build_sensor_answer()", "Local LLM Benchmark", "Artemis Local LLM Voice Assistant"]
---

# Q: Now that ESP32 Wi-Fi and Home Assistant temperature/humidity work, should work continue on ESP32 code or move to the LLM/SLM side?

## Answer

Expanded from original query via vocab: [sensor, mqtt, client, state, answer, assistant, llm, local, model, benchmark, question, routing]. Move to the Artemis application side, with one end-to-end MQTT integration gate before model benchmarking. Leave the ESP32 firmware unchanged unless it fails to publish retained temperature, humidity, and online status on the existing Artemis topics every 60 seconds. The missing local secrets.h is expected and only matters when flashing from this laptop. Set up a virtual environment and install requirements on the Artemis host, then verify the existing read-only MQTT consumer answers live sensor questions. The client currently defaults to a broker at 127.0.0.1, so run Artemis with the broker or make the host configurable if the broker remains on another laptop. Sensor answers intentionally bypass the LLM. After that path works, run the existing local-model benchmark before adding summaries or voice features.

## Outcome

- Signal: useful

## Source Nodes

- MqttSensorClient
- build_sensor_answer()
- Local LLM Benchmark
- Artemis Local LLM Voice Assistant