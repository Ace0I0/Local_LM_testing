---
type: "query"
date: "2026-10-28T19:42:44.774641+00:00"
question: "Live test of what is the living room temp returned an invented 72 degrees and shelter instruction."
contributor: "graphify"
outcome: "useful"
source_nodes: ["_choose_primary_intent()", "build_sensor_answer()", "ask_local_model()", "intent_router.py"]
---

# Q: Live test of what is the living room temp returned an invented 72 degrees and shelter instruction.

## Answer

The local Qwen3.5 model works, as confirmed by the identity response, but the MQTT sensor path was not exercised. The router scored explanation=8 from the exact phrase what is and sensor_query=8 from the shorthand temp. Alphabetical tie-breaking selected explanation and relegated sensor_query to secondary. build_sensor_answer only accepts sensor_query as the primary intent, so the request fell through to the LLM, which hallucinated both the temperature and safety instruction. Immediate verification should use the documented full word temperature. The required code fix is a regression test for the shorthand plus a narrow routing change that lets explicit current room-temperature shorthand win without breaking conceptual queries such as history of temperature measurement.

## Outcome

- Signal: useful

## Source Nodes

- _choose_primary_intent()
- build_sensor_answer()
- ask_local_model()
- intent_router.py