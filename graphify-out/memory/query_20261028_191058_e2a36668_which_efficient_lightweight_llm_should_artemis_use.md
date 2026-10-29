---
type: "query"
date: "2026-10-28T19:10:58.237246+00:00"
question: "Which efficient lightweight LLM should Artemis use through llama-server, with models swappable when needed?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Local LLM Benchmark", "llama-server", "ask_local_model()", "token_budget.py"]
---

# Q: Which efficient lightweight LLM should Artemis use through llama-server, with models swappable when needed?

## Answer

Expanded from graph vocabulary: [artemis, local, llm, model, benchmark, server, prompt, response, token]. Choose Qwen3.5 2B Q4_K_M as the default Artemis model on the Raspberry Pi 5 16GB. It balances approximately 1.31GB quantized model size with materially better official language benchmark results than Qwen3 1.7B, while remaining far lighter than 4B and larger models. Keep Artemis context at 8192 tokens. Use Qwen3 1.7B Q4_K_M only as a compatibility fallback if the installed llama.cpp build is too old for qwen3_5. Model switching is done by stopping llama-server and restarting it with a different GGUF path; the Artemis API endpoint remains unchanged. Verify the Pi llama.cpp version before downloading.

## Outcome

- Signal: useful

## Source Nodes

- Local LLM Benchmark
- llama-server
- ask_local_model()
- token_budget.py