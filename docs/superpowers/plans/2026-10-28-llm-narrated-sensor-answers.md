# LLM-Narrated Sensor Answers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route live sensor questions through local Qwen for safe natural phrasing while preserving validated MQTT facts and deterministic fallback behavior.

**Architecture:** `sensor_answers.py` will turn validated state into an immutable answer plan containing formatted facts and the existing fallback sentence, then validate Qwen output against a deliberately narrow grammar. The controller will send a focused prompt to the existing llama-server call, accept only validated narration, and otherwise speak the fallback.

**Tech Stack:** Python 3 standard library, RapidFuzz router, existing llama-server HTTP client, `unittest`, SAM.

**Spec:** `docs/superpowers/specs/2026-10-28-llm-narrated-sensor-answers-design.md`

## Global Constraints

- MQTT-backed `SensorState` is the only source of sensor facts.
- Qwen may only rephrase supplied location, measurement, formatted value, unit, and availability facts.
- No interpretation, threshold, warning, advice, arithmetic, history, persistence, device control, dependency, service, or model-switching option is added.
- Invalid narration and llama-server failures use the exact existing deterministic answer and must not terminate Artemis.
- Sensor narration uses one short sentence, a 64-token response limit, and a 60-second HTTP timeout.
- Non-sensor prompt assembly and response behavior remain unchanged.

## Review Focus

- Location IDs containing digits, such as `room_2`, must validate without permitting unrelated numbers; covered in Task 2.
- A combined request with one unavailable measurement must narrate only the current measurement; covered in Task 2.
- A model sentence that swaps temperature and humidity values must be rejected; covered in Task 2.
- Malformed or unavailable llama-server responses must fall back without terminating the turn; covered in Task 3.
- Conceptual temperature language must not be promoted to a live sensor request; covered in Task 1.

---

### Task 1: Correct Current Sensor Routing

**Files:**
- Modify: `tests/test_sensor_answers.py`
- Modify: `Python_Scripts/intent_router.py`
- Modify: `Python_Scripts/load_llm_sam.py`

**Interfaces:**
- Consumes: existing `analyze_query(user_text: str) -> dict[str, Any]` weighted routing.
- Produces: routes for `what is the living room temp` and `tell me the room temperature` with `primary_intent == "sensor_query"`; conceptual examples remain `explanation`.

- [ ] **Step 1: Write failing routing tests**

Add literal cases to `SensorRoutingTests`: the two current-reading examples above must select `sensor_query`; `explain room temperature` and the existing history example must select `explanation`. Add the observed shorthand to `run_router_tests()` so the Pi-side lightweight check covers it.

- [ ] **Step 2: Verify the new tests fail for the observed shorthand and conceptual case**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_answers.SensorRoutingTests -v`

Expected: FAIL because `what is the living room temp` currently selects `explanation`, and because any newly exposed conceptual misroute is not guarded.

- [ ] **Step 3: Implement the smallest routing correction**

Extend the existing sensor phrase rules and add at most one focused conceptual guard in `analyze_query()`. Positive cues and conceptual exclusions must match the approved spec; do not make every mention of temperature or humidity a sensor request.

- [ ] **Step 4: Verify focused routing**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_answers.SensorRoutingTests -v`

Expected: all `SensorRoutingTests` pass.

- [ ] **Step 5: Commit**

```bash
git add Python_Scripts/intent_router.py Python_Scripts/load_llm_sam.py tests/test_sensor_answers.py
git commit -m "Fix current sensor question routing"
```

### Task 2: Build Trusted Answer Plans and Validate Narration

**Files:**
- Modify: `tests/test_sensor_answers.py`
- Modify: `Python_Scripts/sensor_answers.py`

**Interfaces:**
- Consumes: `LocationSnapshot`, `SensorState`, normalized user text, and the existing location/unit/rounding behavior.
- Produces: immutable `SensorFact(measurement: str, value: str, unit: str)` and `SensorAnswerPlan(kind: str, fallback: str, location: str | None, facts: tuple[SensorFact, ...])`; `build_sensor_answer_plan(user_text: str, route: dict[str, Any], state: SensorState) -> SensorAnswerPlan | None`; `validate_sensor_narration(text: str, plan: SensorAnswerPlan) -> bool`. Existing `build_sensor_answer(...) -> str | None` remains compatible and returns `plan.fallback`.

- [ ] **Step 1: Write failing answer-plan tests**

Add tests with hand-derived literal assertions for temperature, humidity, combined, partial combined, unavailable direct measurement, no current conditions, unknown location, location clarification, and digit-bearing location plans. Assert that values and units are already formatted and that the fallback exactly matches existing behavior.

- [ ] **Step 2: Verify answer-plan tests fail because the API is absent**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_answers.SensorAnswerPlanTests -v`

Expected: FAIL with missing plan symbols or methods.

- [ ] **Step 3: Implement answer-plan construction**

Refactor the current deterministic answer helpers so plan construction owns location resolution, requested/current measurement selection, display conversion, and fallback creation once. Keep `build_sensor_answer` as the compatibility projection of the plan's fallback. Use one small private structured location result rather than parsing fallback prose.

- [ ] **Step 4: Verify plan construction and existing deterministic behavior**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_answers -v`

Expected: all sensor-answer tests pass.

- [ ] **Step 5: Write failing narration-validation tests**

Add accepted cases for each plan kind and rejected cases for missing facts, changed value or unit, an extra number, a digit not belonging to `room_2`, swapped combined values, qualitative language, warnings or advice, extra sentences, Markdown, and malformed/empty output. Each expected result is a literal boolean.

- [ ] **Step 6: Verify validation tests fail because validation is absent**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_answers.SensorNarrationValidationTests -v`

Expected: FAIL with missing validator.

- [ ] **Step 7: Implement narrow full-sentence validation**

Build escaped, plan-specific full-match regular expressions for the approved temperature, humidity, combined, unavailable, no-information, unknown-location, no-locations, and clarification sentence shapes. Match case-insensitively, permit only shape punctuation and optional safe connective words, and require exact formatted values, units, and location. Do not attempt general semantic classification or repair.

- [ ] **Step 8: Verify all answer and validation behavior**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_answers -v`

Expected: all sensor-answer tests pass.

- [ ] **Step 9: Commit**

```bash
git add Python_Scripts/sensor_answers.py tests/test_sensor_answers.py
git commit -m "Add validated sensor narration plans"
```

### Task 3: Narrate Sensor Turns Through Qwen With Fallback

**Files:**
- Modify: `tests/test_sensor_controller.py`
- Modify: `Python_Scripts/load_llm_sam.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-28-llm-narrated-sensor-answers-design.md`
- Create: `docs/superpowers/plans/2026-10-28-llm-narrated-sensor-answers.md`

**Interfaces:**
- Consumes: Task 2's `SensorAnswerPlan`, `build_sensor_answer_plan`, and `validate_sensor_narration`; existing `ask_local_model`, identity, mode, output/debug, and SAM functions.
- Produces: `build_sensor_narration_prompt(identity: dict, mode: dict, plan: SensorAnswerPlan) -> str`; `ask_local_model(..., timeout: float | None = None) -> tuple[str, dict]`; `handle_sensor_turn(user_text: str, route: dict, state: SensorState, identity: dict, mode: dict) -> bool`.

- [ ] **Step 1: Write failing focused-prompt and accepted-narration controller tests**

Assert the prompt includes identity/mode, only the plan's trusted facts, the exact rephrase-only rules, and no unrelated knowledge text. Patch only the external model call and SAM boundary; assert an accepted returned sentence is printed and spoken once.

- [ ] **Step 2: Verify accepted-narration tests fail on the current direct-answer path**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_controller.SensorControllerTests -v`

Expected: FAIL because sensor turns do not call Qwen and the focused prompt does not exist.

- [ ] **Step 3: Implement focused narration flow**

Build the prompt directly from identity, mode, and plan fields; cap sensor responses at 64 tokens. Update `handle_sensor_turn` and its caller to request narration, validate it, and speak the accepted sentence. Add an optional timeout argument to the shared HTTP call and pass `60.0` only for sensor narration so the general path keeps its current behavior.

- [ ] **Step 4: Verify accepted narration passes**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_controller.SensorControllerTests -v`

Expected: accepted-narration and existing controller tests pass; failure cases added next are not yet present.

- [ ] **Step 5: Write failing fallback tests**

Add separate cases for invalid narration, `urllib.error.URLError`, `TimeoutError`, malformed JSON-facing response data (`KeyError`, `IndexError`, `TypeError`, `ValueError`, or `json.JSONDecodeError` at the controller boundary), and empty output. Assert the exact deterministic fallback is printed and passed to SAM once, and `handle_sensor_turn` returns `True` without raising.

- [ ] **Step 6: Verify fallback tests fail for uncaught errors or unsafe output**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest tests.test_sensor_controller.SensorControllerTests -v`

Expected: FAIL because the sensor narration failure boundary is not implemented.

- [ ] **Step 7: Implement bounded failure handling**

Catch only the model/response exceptions named above around the sensor narration request, log a reason through `debug_log`, and select `plan.fallback`. Never catch SAM failures or unrelated programming errors.

- [ ] **Step 8: Update user documentation**

Update the capability, flow, server startup/model references where stale, and sensor-question section to explain local fact-only narration, validation, deterministic fallback, and the 60-second sensor request timeout. Do not add setup steps or dependencies.

- [ ] **Step 9: Run the full repository verification**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all Python tests pass with zero failures and zero errors.

Run: `bash tests/test_setup_mosquitto.sh`

Expected: all Mosquitto wizard tests pass.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 Python_Scripts/load_llm_sam.py --router-test`

Expected: all lightweight router cases pass without llama-server or SAM.

Run: `python3 -m py_compile Python_Scripts/intent_router.py Python_Scripts/sensor_answers.py Python_Scripts/load_llm_sam.py`

Expected: exit code 0.

- [ ] **Step 10: Commit**

```bash
git add README.md Python_Scripts/load_llm_sam.py tests/test_sensor_controller.py docs/superpowers/specs/2026-10-28-llm-narrated-sensor-answers-design.md docs/superpowers/plans/2026-10-28-llm-narrated-sensor-answers.md
git commit -m "Narrate trusted sensor facts through Qwen"
```
