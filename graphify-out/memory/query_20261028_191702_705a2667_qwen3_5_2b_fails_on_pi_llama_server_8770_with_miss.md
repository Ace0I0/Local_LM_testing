---
type: "query"
date: "2026-10-28T19:17:02.827581+00:00"
question: "Qwen3.5 2B fails on Pi llama-server 8770 with missing tensor blk.24.ssm_conv1d.weight."
contributor: "graphify"
outcome: "corrected"
correction: "Build 8770 has initial Qwen3.5 support but is too old for current NextN/MTP GGUF metadata; a newer loader is required."
source_nodes: ["llama-server", "Local LLM Benchmark", "ask_local_model()"]
---

# Q: Qwen3.5 2B fails on Pi llama-server 8770 with missing tensor blk.24.ssm_conv1d.weight.

## Answer

The error is a Qwen3.5 NextN/MTP loader mismatch, not RAM pressure or command syntax. The GGUF advertises a trailing prediction layer, and llama.cpp build 8770 incorrectly treats that layer as a normal SSM block, demanding blk.24.ssm_conv1d.weight. Upstream later changed loading so MTP tensors are only loaded when requested. First verify the published model SHA-256 and ensure /home/pi/llama.cpp is clean. Then fast-forward llama.cpp and compile llama-server in a separate build-current directory, preserving the old build. Retry the same model with the new binary and thinking disabled.

## Outcome

- Signal: corrected
- Correction: Build 8770 has initial Qwen3.5 support but is too old for current NextN/MTP GGUF metadata; a newer loader is required.

## Source Nodes

- llama-server
- Local LLM Benchmark
- ask_local_model()