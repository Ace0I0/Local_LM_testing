# Graph Report - Local_LM_testing  (2026-10-28)

## Corpus Check
- Corpus is ~36,754 words - fits in a single context window. You may not need a graph.

## Summary
- 443 nodes · 839 edges · 22 communities (18 shown, 4 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- MQTT Sensor Client
- Intent Routing
- Interactive Assistant Runtime
- Knowledge Token Budget
- Benchmark Runner
- Benchmark Tests
- Mosquitto Setup
- Archived Assistant Runtime
- Sensor Answers
- Implementation Plans
- ESP32 Firmware
- MQTT Product Design
- Analog Horror Knowledge
- Sensor State Tests
- Vita Carnis Knowledge
- Mosquitto Setup Tests
- Broker Design
- Fictional Agencies
- Safety Protocols
- Disease Reference
- Broadcast Style

## God Nodes (most connected - your core abstractions)
1. `SensorState` - 30 edges
2. `analyze_query()` - 24 edges
3. `MqttSensorClient` - 21 edges
4. `build_sensor_answer()` - 21 edges
5. `run_interactive()` - 16 edges
6. `run_benchmark()` - 16 edges
7. `run_wizard()` - 15 edges
8. `FakePahoClient` - 14 edges
9. `SensorAnswerTests` - 13 edges
10. `normalize_text()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `Location-based MQTT Identity` --semantically_similar_to--> `Location ID`  [INFERRED] [semantically similar]
  docs/superpowers/specs/2026-10-22-environment-mqtt-contract-design.md → GLOSSARY.md
- `Three-interval Freshness Rule` --semantically_similar_to--> `Stale Reading`  [INFERRED] [semantically similar]
  docs/superpowers/specs/2026-10-22-environment-mqtt-contract-design.md → GLOSSARY.md
- `Read-only MQTT Sensor Answers` --semantically_similar_to--> `Deterministic Sensor Question Routing`  [INFERRED] [semantically similar]
  README.md → docs/superpowers/specs/2026-10-23-artemis-mqtt-sensor-consumer-design.md
- `Local LLM Benchmark` --semantically_similar_to--> `Sequential Local-model Benchmark`  [INFERRED] [semantically similar]
  README.md → docs/superpowers/specs/2026-10-26-artemis-llm-benchmark-design.md
- `run_tests()` --calls--> `route_intent()`  [INFERRED]
  Archive/Python_Scripts/test_intent_router.py → Python_Scripts/intent_router.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Environmental MQTT State Flow** — glossary_sensor_node, docs_superpowers_specs_2026_10_22_environment_mqtt_contract_design_environmental_mqtt_contract, docs_superpowers_specs_2026_10_23_artemis_mqtt_sensor_consumer_design_thread_safe_current_state, readme_read_only_mqtt_sensor_answers [INFERRED 0.95]
- **EAS Lore Knowledge Network** — memory_knowledge_eas_agencies_artemis_public_signal_office, memory_knowledge_eas_current_activity_active_advisory_registry, memory_knowledge_eas_locations_fictional_local_hazard_index, memory_knowledge_eas_creatures_the_iris, memory_knowledge_eas_general_analog_broadcast_style [INFERRED 0.85]

## Communities (22 total, 4 thin omitted)

### Community 0 - "MQTT Sensor Client"
Cohesion: 0.06
Nodes (8): MqttSensorClient, _LocationState, MeasurementSnapshot, _Reading, SensorState, FakePahoClient, MqttSensorClientTests, SensorControllerTests

### Community 1 - "Intent Routing"
Cohesion: 0.08
Nodes (32): run_tests(), _add_unique(), analyze_query(), _best_token_similarity(), _build_debug_reasons(), build_selected_file_details(), _choose_primary_intent(), _choose_secondary_intents() (+24 more)

### Community 2 - "Interactive Assistant Runtime"
Cohesion: 0.12
Nodes (24): ask_local_model(), debug_log(), estimate_token_count(), find_project_dir(), format_elapsed(), get_generation_settings(), get_knowledge_query_keywords(), get_mqtt_password() (+16 more)

### Community 3 - "Knowledge Token Budget"
Cohesion: 0.11
Nodes (16): run_tests(), build_system_prompt(), format_examples(), format_list(), build_budgeted_knowledge_context(), calculate_context_budget_for_file(), calculate_response_tokens(), dedupe_selected_files() (+8 more)

### Community 4 - "Benchmark Runner"
Cohesion: 0.16
Nodes (20): build_parser(), build_payload(), compare_runs(), _escape_cell(), evaluate_response(), extract_metrics(), _format_metric(), load_suite() (+12 more)

### Community 5 - "Benchmark Tests"
Cohesion: 0.08
Nodes (6): ComparisonTests, PromptSuiteTests, RequestAndMetricTests, RunTests, sample_run(), ValidationTests

### Community 6 - "Mosquitto Setup"
Cohesion: 0.16
Nodes (25): ask(), ask_secret(), assert_mqtt_payload(), assert_publish_denied(), banner(), _clear(), confirm(), ensure_mqtt_user() (+17 more)

### Community 7 - "Archived Assistant Runtime"
Cohesion: 0.13
Nodes (19): ask_local_model(), build_system_prompt(), format_elapsed(), format_examples(), format_list(), get_generation_settings(), get_relevant_knowledge_files(), load_identity() (+11 more)

### Community 8 - "Sensor Answers"
Cohesion: 0.22
Nodes (11): build_sensor_answer(), _conditions_answer(), _display_location(), _format_number(), _humidity_answer(), _resolve_location(), _temperature_answer(), _temperature_value() (+3 more)

### Community 9 - "Implementation Plans"
Cohesion: 0.09
Nodes (21): Background MQTT Client, MQTT Controller Lifecycle, Deterministic Sensor Answers, Validated Environmental Sensor State, Compatible-run Comparison, Measured Single-model Run, Versioned Artemis Prompt Suite, Background MQTT Reconnection (+13 more)

### Community 10 - "ESP32 Firmware"
Cohesion: 0.16
Nodes (9): isValidReading(), connectMqtt(), connectWifi(), loop(), publishDiscovery(), publishMeasurements(), publishRetained(), setup() (+1 more)

### Community 11 - "MQTT Product Design"
Cohesion: 0.14
Nodes (13): Local-first Home Helper, MQTT Backbone, Conversational, Daily, and Live Presentation Paths, Environmental MQTT Contract, Exact Retained-topic Cleanup, Location-based MQTT Identity, Retained QoS 1 State, Three-interval Freshness Rule (+5 more)

### Community 12 - "Analog Horror Knowledge"
Cohesion: 0.14
Nodes (15): Fake People, Nature's Mockery, Roots, The Iris, The Wretch, Woodcrawler, Active Advisory Registry, Current Simulated Activity Board (+7 more)

### Community 14 - "Vita Carnis Knowledge"
Cohesion: 0.22
Nodes (9): Harvester / Congregentur Carnis, Host of Influence / Imperium Carnis, Mimic / Trucidatum Carnis, Monolith / Coelum Carnis, Singularity / Verum Carnis, The Crawl / Scandere Carnis, Vita Carnis, Fictional Local Hazard Index (+1 more)

### Community 15 - "Mosquitto Setup Tests"
Cohesion: 0.57
Nodes (7): assert_contains(), assert_mode(), assert_not_contains(), fail(), run_wizard(), test_setup_mosquitto.sh script, write_fake_commands()

### Community 16 - "Broker Design"
Cohesion: 0.29
Nodes (6): Artemis-owned Broker Files, Broker Acceptance Checks, Mosquitto Setup Wizard, artemis_test Account, Authenticated Local MQTT Broker, Retained MQTT Smoke Test

### Community 17 - "Fictional Agencies"
Cohesion: 0.33
Nodes (6): Artemis Public Signal Office, Gray Carrier Signal, Station 7, Artemis Public Signal Office Contact Information, Fictional Reporting Channel, Station 7

### Community 18 - "Safety Protocols"
Cohesion: 0.50
Nodes (4): Do Not Investigate Protocol, Elevated Unknown Activity Outside Protocol, Emergency Contact Reminder, Unknown Presence Inside Residence Protocol

## Knowledge Gaps
- **35 isolated node(s):** `Measurement State`, `llama-server`, `SAM Text-to-Speech`, `Conversational, Daily, and Live Presentation Paths`, `Broker Acceptance Checks` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 138 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SensorState` connect `MQTT Sensor Client` to `Sensor Answers`, `Interactive Assistant Runtime`, `Sensor State Tests`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `SensorState` (e.g. with `handle_sensor_turn()` and `run_interactive()`) actually correct?**
  _`SensorState` has 18 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Measurement State`, `llama-server`, `SAM Text-to-Speech` to the rest of the system?**
  _35 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MQTT Sensor Client` be split into smaller, more focused modules?**
  _Cohesion score 0.05764411027568922 - nodes in this community are weakly interconnected._
- **Why does `MqttSensorClient` connect `MQTT Sensor Client` to `Interactive Assistant Runtime`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `analyze_query()` (e.g. with `.test_explanation_about_temperature_is_not_a_sensor_query()` and `.test_routes_environmental_questions_without_eas_knowledge()`) actually correct?**
  _`analyze_query()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Intent Routing` be split into smaller, more focused modules?**
  _Cohesion score 0.0792156862745098 - nodes in this community are weakly interconnected._