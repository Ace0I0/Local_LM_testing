# Home Helper Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace every active EAS-era memory reference with the one Home Helper
identity and three factual knowledge files.

**Architecture:** The controller loads home_helper.json directly. Router topic
selection and token budgets use only the new files, while sensor questions keep
their existing no-knowledge path. Tests assert the new prompt and routing
contract before legacy files are removed.

**Tech Stack:** Python 3, JSON, plaintext knowledge files, unittest.

**Spec:** docs/superpowers/specs/2026-10-29-home-helper-memory-design.md

## Global Constraints

- Preserve MQTT and narrated-sensor behavior.
- Do not invent local household facts or control devices.
- Delete every active EAS file and reference.
- Keep one hardcoded Home Helper mode; do not add mode selection.

## Review Focus

- Sensor queries must remain knowledge-free.
- General safety questions must never load deleted lore.
- Missing legacy filenames must not be reachable through routing or budgets.
- Sensor narration prompts must retain trusted-fact-only behavior.
- No active source, test, README, mode, or knowledge file may retain EAS text.

---

### Task 1: Replace the active memory contract

**Files:**
- Create: memory/modes/home_helper.json
- Create: memory/knowledge/home_helper_overview.txt
- Create: memory/knowledge/sensor_guidance.txt
- Create: memory/knowledge/safety_boundaries.txt
- Modify: memory/identity.json
- Modify: Python_Scripts/load_llm_sam.py
- Modify: Python_Scripts/intent_router.py
- Modify: Python_Scripts/token_budget.py
- Modify: tests/test_sensor_controller.py
- Modify: tests/test_sensor_answers.py
- Modify: README.md
- Delete: memory/active_mode.txt, memory/modes/EAS.json,
  memory/modes/informational.json, memory/modes/learning.json, and
  memory/knowledge/eas_*.txt

- [x] Write failing tests for Home Helper prompt text and general routing files.
- [x] Run the focused tests to observe the expected legacy-mode failure.
- [x] Replace the mode, identity, knowledge files, routing map, budgets, and
  display defaults with Home Helper equivalents.
- [x] Delete legacy memory files only after callers use the replacement names.
- [x] Run the focused and full test suites, router test, and a repository-wide
  EAS-reference check.
