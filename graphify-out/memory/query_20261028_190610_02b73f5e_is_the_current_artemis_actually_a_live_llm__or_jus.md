---
type: "query"
date: "2026-10-28T19:06:10.488466+00:00"
question: "Is the current Artemis actually a live LLM, or just hardcoded responses?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["build_sensor_answer()", "ask_local_model()", "intent_router.py", "make_sam_wav()"]
---

# Q: Is the current Artemis actually a live LLM, or just hardcoded responses?

## Answer

Expanded from graph vocabulary: [artemis, assistant, sensor, answer, local, llm, model, router, sam, response]. The Pi application is hybrid. Its router is rule-based fuzzy matching. Sensor questions use live MQTT values but deterministic response templates, so values are live while wording is mostly fixed. Normal non-sensor questions assemble a prompt and call a local LLM through llama-server. That generative path is currently unavailable because no model is loaded and llama-server is stopped. Unrecognized input can use a fixed fallback, and SAM only converts text to speech. The Codex chat assistant is separate from the Pi Artemis program.

## Outcome

- Signal: useful

## Source Nodes

- build_sensor_answer()
- ask_local_model()
- intent_router.py
- make_sam_wav()