from __future__ import annotations

import re
from typing import Any

from intent_router import normalize_text
from sensor_state import LocationSnapshot, SensorState


_NAMED_LOCATION = re.compile(
    r"\b(?:in|for)\s+(?:the\s+)?"
    r"(?P<location>[a-z0-9]+(?:\s+[a-z0-9]+)*?)"
    r"(?:\s+in\s+(?:degrees?\s+)?(?:celsius|fahrenheit))?$"
)
_UNIT_ONLY = {"celsius", "fahrenheit", "degree celsius", "degree fahrenheit"}


def build_sensor_answer(
    user_text: str,
    route: dict[str, Any],
    state: SensorState,
) -> str | None:
    if route.get("primary_intent") != "sensor_query":
        return None

    normalized = normalize_text(user_text)
    location_id, location_error = _resolve_location(normalized, state)
    if location_error is not None:
        return location_error

    snapshot = state.snapshot(location_id)
    if snapshot is None:
        return f"I do not have sensor information for the {_display_location(location_id)}."

    topics = set(route.get("topics", []))
    wants_temperature = "temperature" in topics
    wants_humidity = "humidity" in topics
    wants_conditions = "environment" in topics or (wants_temperature and wants_humidity)

    if wants_conditions:
        return _conditions_answer(snapshot, "celsius" in normalized)
    if wants_temperature:
        return _temperature_answer(snapshot, "celsius" in normalized)
    if wants_humidity:
        return _humidity_answer(snapshot)
    return _conditions_answer(snapshot, "celsius" in normalized)


def _resolve_location(
    normalized_text: str,
    state: SensorState,
) -> tuple[str, str | None]:
    known_locations = state.known_locations()
    for location_id in known_locations:
        display_name = _display_location(location_id)
        if re.search(rf"\b{re.escape(display_name)}\b", normalized_text):
            return location_id, None

    named_match = _NAMED_LOCATION.search(normalized_text)
    if named_match is not None:
        named_location = named_match.group("location").strip()
        if named_location not in _UNIT_ONLY:
            return "", f"I do not have sensor information for the {named_location}."

    if len(known_locations) == 1:
        return known_locations[0], None
    if len(known_locations) > 1:
        return "", "Which location do you mean?"
    return "", "I do not have any sensor locations yet."


def _conditions_answer(snapshot: LocationSnapshot, use_celsius: bool) -> str:
    has_temperature = snapshot.temperature.state == "current"
    has_humidity = snapshot.humidity.state == "current"
    location = _display_location(snapshot.location_id)

    if has_temperature and has_humidity:
        value, unit = _temperature_value(snapshot.temperature.value, use_celsius)
        humidity = _format_number(snapshot.humidity.value)
        return (
            f"The {location} is {value} degrees {unit} "
            f"with {humidity} percent relative humidity."
        )
    if has_temperature:
        return _temperature_answer(snapshot, use_celsius)
    if has_humidity:
        return _humidity_answer(snapshot)
    return f"I do not have current sensor information for the {location}."


def _temperature_answer(snapshot: LocationSnapshot, use_celsius: bool) -> str:
    location = _display_location(snapshot.location_id)
    if snapshot.temperature.state != "current":
        return f"I do not have a current temperature reading for the {location}."

    value, unit = _temperature_value(snapshot.temperature.value, use_celsius)
    return f"The {location} temperature is {value} degrees {unit}."


def _humidity_answer(snapshot: LocationSnapshot) -> str:
    location = _display_location(snapshot.location_id)
    if snapshot.humidity.state != "current":
        return f"I do not have a current humidity reading for the {location}."

    humidity = _format_number(snapshot.humidity.value)
    return f"The {location} humidity is {humidity} percent."


def _temperature_value(value: float | None, use_celsius: bool) -> tuple[str, str]:
    assert value is not None
    if use_celsius:
        return _format_number(value), "Celsius"
    return _format_number((value * 9 / 5) + 32), "Fahrenheit"


def _format_number(value: float | None) -> str:
    assert value is not None
    return f"{round(value, 1):g}"


def _display_location(location_id: str) -> str:
    return location_id.replace("_", " ")
