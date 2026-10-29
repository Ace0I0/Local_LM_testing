---
type: "query"
date: "2026-10-28T19:13:18.286457+00:00"
question: "Can Pi llama-server build 8770 run the selected Qwen3.5 2B model, and what setup should follow?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["llama-server", "Local LLM Benchmark", "ask_local_model()", "token_budget.py"]
---

# Q: Can Pi llama-server build 8770 run the selected Qwen3.5 2B model, and what setup should follow?

## Answer

Pi llama.cpp version 8770 is newer than the Qwen3.5 model-loading fix confirmed in build 8149, so no rebuild is required. Download only the 1.31GB Qwen3.5-2B Q4_K_M text GGUF, verify SHA-256 a8b50de00b780c0f3c16f07cb041a1ecd678b6e22fd8cde91e57fe4b5031523b, and start llama-server on 127.0.0.1:8080 with context 8192, Jinja templates, and enable_thinking false. Do not download the mmproj image add-on because Artemis is text-only. Start in the foreground for the first test, then health-check and run Artemis or the benchmark from a second SSH session.

## Outcome

- Signal: useful

## Source Nodes

- llama-server
- Local LLM Benchmark
- ask_local_model()
- token_budget.py