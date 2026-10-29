---
type: "query"
date: "2026-10-28T19:03:29.704016+00:00"
question: "Artemis crashes with ConnectionRefusedError after entering test. What is the issue?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ask_local_model()", "run_interactive()", "MqttSensorClient", "intent_router.py"]
---

# Q: Artemis crashes with ConnectionRefusedError after entering test. What is the issue?

## Answer

Expanded from graph vocabulary: [test, router, current, status, local, model, server, request, error, sensor]. The input test was fuzzily misclassified as current_status, so it followed the normal LLM path instead of the deterministic sensor path. ask_local_model posts to 127.0.0.1:8080, but llama-server is not running and the Pi has no usable model GGUF, producing ConnectionRefusedError. The exception is uncaught, so it terminates the application. MQTT did not cause this failure. Restart Artemis and ask an explicit temperature, humidity, or conditions question to validate MQTT without a model. Separately, model download/startup and graceful URLError handling are later tasks.

## Outcome

- Signal: useful

## Source Nodes

- ask_local_model()
- run_interactive()
- MqttSensorClient
- intent_router.py