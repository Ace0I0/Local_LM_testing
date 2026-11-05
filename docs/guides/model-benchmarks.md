[Documentation index](../README.md) · [Project README](../../README.md)

# Compare local models

The GGUF file and llama-server both run locally. Artemis talks to the
loopback HTTP endpoint; it does not send prompts to an internet service.
Benchmark one model at a time so the models do not compete for CPU or RAM.

Start llama-server with a model, then record its run:

    python scripts/benchmark_llms.py run --label qwen2.5-1.5b

Stop the server, restart it with the next GGUF, and repeat with
--label qwen3.5-2b and --label qwen3.5-4b. Each run uses the same
18 prompts, one warm-up, and three measured repetitions by default.
If the server is elsewhere, pass its full chat-completions URL:

    python scripts/benchmark_llms.py run \
      --label qwen3.5-2b \
      --url http://SERVER_ADDRESS:8080/v1/chat/completions

Compare the three timestamped JSON results:

    python scripts/benchmark_llms.py compare \
      benchmark-results/qwen2.5-1.5b-*.json \
      benchmark-results/qwen3.5-2b-*.json \
      benchmark-results/qwen3.5-4b-*.json

The Markdown report shows errors, automated response checks, wall time,
token usage, llama.cpp prompt and generation TPS when supplied by the
server, calculated end-to-end output TPS, and every raw answer. Generated
results remain under the ignored benchmark-results directory.
