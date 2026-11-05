# Artemis documentation

[Project overview, setup, and everyday commands](../README.md)

Start with the project README to install the Python dependencies, start the model, and run Artemis. Commands in these guides run from the repository root unless stated otherwise.

## Setup and operation

| Task | Guide |
| --- | --- |
| Install Mosquitto; add accounts; change passwords or usernames | [MQTT broker](guides/mqtt-broker.md) |
| Configure and flash another sensor device | [ESP32 sensors](guides/esp32-sensors.md) |
| Configure the model to start at boot | [llama-server service](guides/llama-server.md) |
| Ask about readings and understand unavailable data | [Sensor questions](guides/sensor-questions.md) |
| Compare local model performance | [Model benchmarks](guides/model-benchmarks.md) |

## Components and terminology

ESP32 devices publish readings through the Mosquitto MQTT broker. Home Assistant displays discovered sensors; Artemis reads the sensor topics independently and answers questions using the local model and SAM speech output.

See the [component overview](../README.md#components), [source layout](../README.md#project-structure), and [glossary](../GLOSSARY.md).

## Project history

[Project direction interview](project-direction-interview.md), [design specifications](superpowers/specs/), and [implementation plans](superpowers/plans/) record decisions and work at particular dates. Some describe proposed or superseded behavior. Use the current guides and source for operational instructions.

## Maintaining these docs

Use GitHub-flavored Markdown and relative links for repository files. Give each procedure a clear goal, prerequisites, where to run commands, and a verification step. Explain placeholders before commands, keep credentials out of examples, and link to the main guide instead of duplicating long procedures.

Update the relevant guide when behavior changes. Keep the README's everyday commands consistent with the detailed guides.
