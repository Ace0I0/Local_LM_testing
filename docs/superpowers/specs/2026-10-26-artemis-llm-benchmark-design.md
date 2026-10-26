# Artemis LLM Benchmark Design

## Intent

Create a repeatable way to compare local GGUF models for Artemis before Raspberry Pi access is available. The benchmark must exercise Artemis's real prompt-building path, record performance and usage data honestly, preserve raw responses for quality review, and compare runs made at different times against the same prompt suite.

The first comparison targets Qwen2.5 1.5B Q4_K_M, Qwen3.5 2B Q4_K_M, and Qwen3.5 4B Q4_K_M. Model downloading and `llama-server` lifecycle management remain manual so the harness does not assume a machine, model directory, or installation method.

## Goals

- Run a fixed, versioned suite of 18 representative Artemis prompts against one OpenAI-compatible local endpoint at a time.
- Reuse the active Artemis router, knowledge selection, system prompt, response-token budget, and generation temperature.
- Perform one warm-up request and three recorded requests per prompt by default.
- Save raw responses, errors, wall time, token usage, llama.cpp timings, prompt throughput, generation throughput, end-to-end output throughput, finish reason, and request settings.
- Generate a Markdown comparison across independently saved model runs.
- Detect leaked reasoning tags, Markdown, excessive response length, and prompt-specific required or forbidden content without using another LLM as a judge.
- Use only the Python standard library and the project's existing dependencies.

## Non-goals

- Downloading, starting, stopping, or supervising model servers.
- Running multiple models simultaneously.
- Replacing `llama-server` with embedded Python bindings.
- Claiming true time-to-first-token from a non-streaming request.
- Producing a single subjective quality score or using public leaderboards as the acceptance test.
- Benchmarking deterministic MQTT sensor answers, which intentionally bypass the LLM.

## Chosen approach

Use one Python CLI with `run` and `compare` subcommands. `run` connects to one configurable `/v1/chat/completions` endpoint and writes a timestamped JSON result under `benchmark-results/`. The operator restarts `llama-server` with each downloaded model and repeats the command. `compare` verifies that the input runs used the same prompt-suite identity and prompt digest, then writes a Markdown report containing aggregate measurements and the raw model responses grouped by prompt.

This sequential approach avoids RAM and CPU contention between models and works with the project's existing local HTTP boundary. It also works with three distinct endpoints when those are available, because each `run` invocation accepts its own URL.

## Data and validation

The committed prompt file contains a suite identifier, version, and 18 cases. Each case has a stable ID, user text, maximum word count, optional phrases of which at least one must appear, and optional forbidden phrases. Generic checks reject `<think>` or similar reasoning markup and Markdown formatting.

Each result records the prompt-suite SHA-256 digest, model label, API model value, endpoint, UTC timestamp, repeat count, client platform, request settings, normalized metrics, raw server `usage` and `timings` objects, response text, automated checks, and any error. Secrets and complete system prompts are not written to results.

Generation TPS comes from llama.cpp's reported prediction rate when present. End-to-end output TPS is separately calculated from completion tokens divided by wall time. Missing server metrics remain null rather than being presented as measured values.

## Safety and repository behavior

Model labels must be safe filenames. Invalid prompt files and incompatible comparison inputs fail with clear messages. One failed request is recorded and does not discard other results. Generated `benchmark-results/` files are ignored by Git because responses may contain local knowledge and machine details.

## Acceptance

- Mocked tests prove request construction, metric normalization, failure recording, constraint checks, prompt-suite compatibility checks, and comparison output.
- The existing unit suite continues to pass.
- `--help` documents a sequential three-model workflow.
- No live server or Raspberry Pi is required to run the tests.

## Alternatives considered

- Running three servers together was rejected because resource contention would make Pi measurements misleading.
- Embedding llama.cpp through Python bindings was rejected because it adds a native dependency and couples Artemis to the inference runtime.
- Separate runner and comparison programs were rejected because one small CLI is easier to operate and test.
