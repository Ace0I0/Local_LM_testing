# Artemis LLM Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standard-library CLI that records comparable Artemis model runs and generates an auditable three-model report.

**Architecture:** A committed JSON prompt suite drives one model run at a time through Artemis's existing prompt builder and an OpenAI-compatible HTTP endpoint. Timestamped raw JSON runs remain local; a second CLI subcommand verifies suite compatibility and produces a Markdown comparison.

**Tech Stack:** Python 3.9+, `argparse`, `urllib.request`, `json`, `statistics`, `hashlib`, existing Artemis modules, `unittest`

**Spec:** `docs/superpowers/specs/2026-10-26-artemis-llm-benchmark-design.md`

## Global Constraints

- Use one warm-up and three recorded repetitions per prompt by default.
- Use exactly 18 committed prompt cases in suite version 1.
- Reuse Artemis routing, prompt construction, response-token budget, and generation temperature.
- Add no dependencies and do not manage model downloads or server processes.
- Never label end-to-end throughput as llama.cpp generation throughput.
- Never save secrets or complete system prompts.
- Ignore all generated files under `benchmark-results/`.

## Review Focus

- A server response without `usage` or `timings` must retain the response and expose null server metrics.
- A timeout or malformed response must become a recorded error while later repetitions continue.
- A model label containing path traversal or shell punctuation must be rejected before writing.
- Comparison inputs with different prompt digests or case IDs must fail instead of presenting an unfair report.
- Zero elapsed time or zero completion tokens must not cause division errors or invented TPS values.

---

### Task 1: Prompt suite and measured single-model runs

**Files:**
- Create: `benchmarks/artemis-prompts.json`
- Create: `scripts/benchmark_llms.py`
- Create: `tests/test_benchmark_llms.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `load_llm_sam.load_identity()`, `load_mode()`, `route_intent()`, `build_system_prompt()`, and `get_generation_settings()`.
- Produces: `load_suite(path: Path) -> dict`, `validate_label(label: str) -> str`, `build_payload(case: dict, api_model: str) -> tuple[dict, dict]`, `extract_metrics(response: dict, wall_seconds: float) -> dict`, `evaluate_response(case: dict, text: str) -> dict`, `run_benchmark(args: argparse.Namespace) -> Path`, and version-1 result JSON accepted by Task 2.

- [ ] **Step 1: Write failing suite, request, metrics, validation, and error-continuation tests**

Add `unittest` cases asserting that the suite has 18 unique IDs; request construction uses Artemis's actual messages, temperature, and token budget; llama.cpp timing fields and fallback end-to-end TPS stay distinct; missing/zero metrics yield nulls; unsafe labels fail; reasoning/Markdown/length/content checks report individual failures; and a mocked failed request does not prevent the next repetition.

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_benchmark_llms -v`

Expected: FAIL because `scripts/benchmark_llms.py` and the suite do not exist.

- [ ] **Step 3: Add the version-1 Artemis prompt suite**

Create 18 stable cases covering identity, concise speech, local knowledge recall, ambiguity, hallucination resistance, reporting guidance, safety guidance, and response formatting. Do not include sensor questions because production handles them without an LLM.

- [ ] **Step 4: Implement the minimal `run` path**

Use `urllib.request` for non-streaming JSON POSTs. Record raw `usage` and `timings`, normalized nullable metrics, exact response text, checks, prompt debug counts, finish reason, errors, UTC time, suite digest, and platform details. Create `benchmark-results/` only when writing a run, and sanitize the model label before deriving the filename.

- [ ] **Step 5: Ignore generated benchmark results**

Add `benchmark-results/` to `.gitignore` without changing existing rules.

- [ ] **Step 6: Run focused and existing tests**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_benchmark_llms -v`

Expected: all benchmark tests pass.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: the complete Python suite passes.
### Task 2: Compatible-run comparison and operator documentation

**Files:**
- Modify: `scripts/benchmark_llms.py`
- Modify: `tests/test_benchmark_llms.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: version-1 result JSON from Task 1.
- Produces: `validate_compatible_runs(runs: list[dict]) -> None`, `summarize_run(run: dict) -> dict`, `render_comparison(runs: list[dict]) -> str`, and `compare_runs(paths: list[Path], output: Path | None) -> Path`.

- [ ] **Step 1: Write failing compatibility, aggregation, and report tests**

Assert that mismatched suite IDs, versions, digests, case IDs, or repeat counts fail clearly; aggregation ignores errored observations without hiding their count; mean/median/min/max are correct; null metrics remain visibly unavailable; and the report groups raw responses by prompt and model.

- [ ] **Step 2: Run the focused tests and confirm the new tests fail**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_benchmark_llms -v`

Expected: FAIL because comparison functions are absent.

- [ ] **Step 3: Implement compatible comparison and Markdown rendering**

Keep aggregation deterministic, escape Markdown table cells, show success/error and automated-check rates, and label server-reported generation TPS separately from calculated end-to-end output TPS.

- [ ] **Step 4: Document the sequential three-model workflow**

Add concise README commands for running Qwen2.5 1.5B, Qwen3.5 2B, and Qwen3.5 4B one at a time against the same endpoint, then comparing their saved JSON files. State that the GGUF and `llama-server` both remain local on the Pi.

- [ ] **Step 5: Verify help, focused tests, and the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 scripts/benchmark_llms.py --help`

Expected: exits 0 and lists `run` and `compare`.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_benchmark_llms -v`

Expected: all benchmark tests pass.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: the complete Python suite passes.
