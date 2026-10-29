# LLM-Narrated Sensor Answers Design

Date: 2026-10-28
Status: Approved
Supersedes: The deterministic sensor-response path in `2026-10-23-artemis-mqtt-sensor-consumer-design.md`

## Intent

Let Artemis use the local Qwen model to phrase every current sensor answer more naturally while keeping MQTT-backed sensor state as the only source of facts. The model may change wording, but it may not calculate new values, interpret conditions, add advice, or introduce facts.

## Goals

- Route current temperature, humidity, and environmental-condition questions into the sensor path reliably.
- Resolve and validate the requested location and readings before contacting the model.
- Give Qwen a compact packet containing only the facts it may state.
- Accept only short paraphrases that preserve the supplied location, measurement, value, unit, and availability facts.
- Fall back to the existing deterministic answer whenever the model is unavailable or its response cannot be proven safe.
- Continue sending the final accepted or fallback sentence through SAM.

## Non-goals

- Judging whether a reading is comfortable, hot, cold, humid, dry, dangerous, or unusual.
- Generating warnings, recommendations, alerts, trends, history, or comparisons.
- Adding thresholds, user preferences, persistence, device control, or a second validation model.
- Changing MQTT topics, payload validation, freshness rules, unit conversion, or sensor storage.
- Adding model-selection or model-switching configuration.

## Source-of-truth boundary

`SensorState` remains authoritative for MQTT readings, connection-derived availability, and freshness. Existing sensor-answer logic remains authoritative for:

- location resolution;
- requested measurements;
- current versus unavailable readings;
- Celsius-to-Fahrenheit conversion;
- speech rounding and display units; and
- the deterministic fallback sentence.

The language model never receives raw MQTT payloads and never performs unit conversion or arithmetic. It receives only already validated, already formatted display facts.

## Selected approach: trusted facts, constrained narration, validated output

For a sensor request, Artemis first builds a small answer plan from the validated snapshot. The plan contains:

- the resolved display location, when one is known;
- the requested measurement or measurements;
- each available display value and its required spoken unit;
- the availability fact when a directly requested value is not current;
- the deterministic fallback sentence; and
- the response shape that is valid for that combination of facts.

Examples of supplied facts are `living room`, `temperature`, `70.7`, and `degrees Fahrenheit`, or `living room`, `humidity`, and `45 percent`. For an unavailable reading, the only supplied fact is that Artemis has no current reading for that measurement and location.

Existing combined-answer behavior is preserved: when a general conditions request has one current measurement and one unavailable measurement, the plan contains and narrates only the current measurement. It does not mention the omitted measurement. When neither measurement is current, the plan contains only the existing general no-current-sensor-information fact.

Unknown-location plans require the user-supplied location and the fact that Artemis has no sensor information for it; they do not require the requested measurement to be repeated. Location-clarification plans contain only the request for one location. These responses still go through Qwen so every routed sensor question follows the same narration-and-fallback path.

The answer plan is an internal application object, not a knowledge file and not user-editable prompt text. It is assembled only from normalized request data and validated `SensorState` snapshots.

## Prompt contract

Sensor narration uses a focused prompt assembled from the existing identity and mode plus the answer plan. It does not load unrelated knowledge files. The prompt tells Qwen to:

- return one plain-English sentence suitable for SAM;
- rephrase only the supplied facts;
- include every required location, measurement, value, and unit exactly as supplied;
- keep each value paired with its supplied measurement and unit;
- make no calculation, classification, comparison, warning, recommendation, or safety statement;
- include no additional number; and
- return only the sentence, without Markdown, labels, or commentary.

The original user question is included only as request context. It is never treated as a source of sensor facts. The sensor narration request uses a small response-token cap appropriate for one sentence. The existing local llama-server endpoint and model remain unchanged.

## Output validation

Model output is untrusted. Before it is printed or spoken, a deterministic validator checks it against the answer plan.

The first version deliberately accepts a narrow family of natural sentence shapes rather than attempting open-ended semantic validation. A response is accepted only when all of these conditions hold:

- it is non-empty plain text containing exactly one short sentence;
- it contains the resolved location and every requested measurement name required by the plan;
- every expected formatted value and spoken unit appears exactly as supplied;
- each value and unit occur in the recognized clause for the correct measurement;
- it contains no numeric token other than the supplied formatted values or digits that are part of the exact validated display location;
- it uses only the small safe narration vocabulary and supplied fact words allowed for that answer shape; and
- current-reading shapes contain no negation, while unavailable-reading shapes contain no value.

Separate recognized shapes cover temperature, humidity, combined conditions, one available measurement in a combined request, unavailable requested measurements, unknown locations, and requests that need a location clarification. This keeps values from being swapped between temperature and humidity and excludes qualitative language, advice, and warnings by construction.

Punctuation and capitalization may vary. The validator does not try to repair an invalid answer. Any failure selects the deterministic fallback.

## Request and fallback flow

1. Route the user text once.
2. If it is not a current sensor request, continue through the existing general LLM path unchanged.
3. Resolve the location and build the trusted answer plan from `SensorState`.
4. Send the focused narration prompt and user question to llama-server.
5. Validate the returned sentence against the answer plan.
6. Print and speak the validated sentence, or the deterministic fallback if any step fails.

Fallback covers connection refusal, timeout, HTTP error, malformed JSON, missing response fields, empty output, and validation failure. A sensor-specific model failure must not terminate the interactive Artemis process. Debug mode may state why fallback occurred, but normal output contains only the final answer. No raw MQTT payload or secret is logged.

The llama-server request is bounded by a 60-second timeout so an unavailable or wedged server eventually yields the factual fallback. The existing deterministic path remains available even when llama-server is not running.

## Routing correction

Current sensor wording must select `sensor_query` even when a generic explanation phrase such as `what is` produces the same score. Current-reading cues are the existing direct request shapes (`what is` or `what's` with temperature, temp, or humidity; `how humid`; conditions requests), explicit `current`, `now`, or `reading` language, and room-measurement phrases such as `room temp`, `room temperature`, or `room humidity`. This covers the observed shorthand without treating every occurrence of a sensor word as a live reading request.

Conceptual cues such as `explain`, `meaning`, `history`, `measurement`, `measure`, `how ... work`, or `about` prevent sensor promotion and keep the request in the normal explanation path. Thus `what is the living room temp` and `tell me the room temperature` are sensor requests, while `explain room temperature` and `what is the history of temperature measurement` are explanation requests. The implementation may express these cues through the existing weighted rule table or one small tie-break predicate, whichever produces the smallest clear change.

The controller continues to rely on the primary intent; it will not treat every mention of temperature or humidity as a live sensor request.

## Code boundaries

The smallest complete change reaches these existing areas:

- `Python_Scripts/intent_router.py`: correct current sensor-query selection without weakening conceptual-query behavior.
- `Python_Scripts/sensor_answers.py`: expose the trusted answer plan, deterministic fallback, focused prompt facts, and narrow response validation while reusing existing location, conversion, and formatting behavior.
- `Python_Scripts/load_llm_sam.py`: call Qwen for sensor narration, handle model failures, choose validated output or fallback, and pass the final sentence to the existing SAM path.
- `tests/test_sensor_answers.py`: cover fact planning and accepted/rejected paraphrases.
- `tests/test_sensor_controller.py`: cover successful narration and all fallback boundaries without a live model or broker.
- Existing router tests: cover the observed `what is the living room temp` tie and preserve the conceptual-temperature negative case.
- `README.md`: describe that current sensor answers are locally narrated from validated facts and fall back deterministically.

No new runtime dependency, service, configuration file, persistence layer, or public model API is introduced.

## Testing

Tests use fakes and mocks; they do not require Mosquitto, llama-server, Qwen, or SAM.

Required coverage:

- the observed living-room temperature wording routes to `sensor_query`;
- the specified current-reading examples route to `sensor_query`, while the specified conceptual and historical examples remain explanation requests;
- plans contain only resolved, formatted facts and the current deterministic fallback;
- valid temperature, humidity, combined, partial, unavailable, unknown-location, and clarification paraphrases are accepted;
- a missing location, missing measurement, altered value, altered unit, extra number, swapped temperature/humidity value, qualitative judgment, warning, advice, extra sentence, or malformed output is rejected;
- accepted narration is printed and passed to SAM;
- connection refusal, timeout, HTTP failure, malformed server response, and validation failure all use the exact deterministic fallback and still call SAM once;
- non-sensor turns continue through the existing general LLM flow; and
- the full existing standard-library test suite remains green.

## Acceptance

On the Raspberry Pi, a question such as `what is the living room temp` is routed as a sensor request. Artemis obtains the current MQTT-backed value, asks local Qwen for a one-sentence paraphrase, validates that sentence, and speaks it through SAM. Across repeated questions the wording may vary, but the stated facts do not. If Qwen invents content or llama-server is unavailable, Artemis speaks the existing deterministic factual answer instead and remains running.
