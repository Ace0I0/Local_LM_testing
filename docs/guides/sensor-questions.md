[Documentation index](../README.md) · [Project README](../../README.md)

# Artemis sensor questions

Artemis uses Paho MQTT to subscribe in the background with the read-only `artemis` account. Run the application normally and enter that account's MQTT password at the hidden prompt:

```bash
python Python_Scripts/load_llm_sam.py
```

For unattended startup, `ARTEMIS_MQTT_PASSWORD` may be supplied through the process environment. Never commit it or place it directly in a shell command. RapidFuzz handles question routing; Paho maintains the MQTT 5 connection and automatically reconnects when the local broker returns.

Initial supported questions include:

- `What is the living room temperature?`
- `What is the living room temperature in Celsius?`
- `What is the humidity?`
- `How are conditions in the living room?`

## Multiple rooms

Use your devices' actual location names. Whole-house requests cover every location Artemis has received through MQTT:

- `How are conditions around the house?`
- `Give me a house summary in Celsius`
- `What is the temperature in all rooms?`
- `Compare the bedroom and game room temperature in Celsius`
- `Compare the bedroom and game room humidity`
- `Which room is warmest?`
- `Which room is coldest?`
- `Which room is most humid?`
- `Which room is least humid?`

Named comparisons present the two rooms' readings side by side. Rankings use current measurements only, report ties, and identify rooms whose requested measurement is unavailable. With only one current reading, Artemis reports that a comparison is unavailable rather than declaring a winner. It cannot inventory devices that have never published to it. An unspecified single-room question still asks which location you mean when several are known.

Python chooses rooms, calculates rankings, and formats the trusted facts. The LLM receives those facts grouped by room and phrases a short sentence for each, retaining a fixed introduction for computed comparisons. The response budget grows with the number of rooms up to 512 tokens. Validation checks the complete answer in the supplied room order, rejecting swapped values, changed units, omitted rooms, invented rankings, and added advice. A rejected or truncated response falls back to the complete factual answer.

## Freshness and narration

MQTT measurements remain Celsius internally. Artemis presents Fahrenheit by default and uses Celsius when requested explicitly. A measurement becomes unavailable after 180 seconds without an update. General condition reports omit unavailable measurements; a direct question says only that no current reading is available. Broker downtime does not stop non-sensor questions.

Every routed sensor question is offered to the local Qwen model. Single-room answers use one sentence; multi-room answers use one per room plus any computed comparison introduction. The model receives resolved locations, requested measurements, formatted values and units, and availability facts. Rejected output, malformed responses, connection errors, or the 60-second sensor timeout use the deterministic factual answer and keep Artemis running.

The setup wizard's retained sample is accepted when Artemis starts, but it becomes unavailable after 180 seconds because it is not a live sensor. The current ESP32 firmware refreshes valid readings every 60 seconds.

Run the local checks with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/test_setup_mosquitto.sh
python3 Python_Scripts/load_llm_sam.py --router-test
```
