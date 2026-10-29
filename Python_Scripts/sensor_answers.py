from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from intent_router import normalize_text
from sensor_state import LocationSnapshot, SensorState


_NAMED_LOCATION = re.compile(
    r"\b(?:in|for)\s+(?:the\s+)?"
    r"(?P<location>[a-z0-9]+(?:\s+[a-z0-9]+)*?)"
    r"(?:\s+in\s+(?:degrees?\s+)?(?:celsius|fahrenheit))?$"
)
_LEADING_LOCATION_PATTERNS = (
    re.compile(
        r"^(?:what is|what s)\s+"
        r"(?!the\s+(?:temperature|temp|humidity)$)(?:the\s+)?"
        r"(?P<location>[a-z0-9]+(?:\s+[a-z0-9]+)*)\s+"
        r"(?:temperature|temp|humidity)$"
    ),
    re.compile(
        r"^how humid is\s+(?:the\s+)?"
        r"(?P<location>[a-z0-9]+(?:\s+[a-z0-9]+)*)$"
    ),
)
_UNIT_ONLY = {"celsius", "fahrenheit", "degree celsius", "degree fahrenheit"}


@dataclass(frozen=True)
class SensorFact:
    measurement: str
    value: str
    unit: str


@dataclass(frozen=True)
class SensorAnswerPlan:
    kind: str
    fallback: str
    location: str | None
    facts: tuple[SensorFact, ...]
    subject: str | None = None


@dataclass(frozen=True)
class _LocationResolution:
    location_id: str | None = None
    error_kind: str | None = None
    error_location: str | None = None


def build_sensor_answer(
    user_text: str,
    route: dict[str, Any],
    state: SensorState,
) -> str | None:
    plan = build_sensor_answer_plan(user_text, route, state)
    return None if plan is None else plan.fallback


def build_sensor_answer_plan(
    user_text: str,
    route: dict[str, Any],
    state: SensorState,
) -> SensorAnswerPlan | None:
    if route.get("primary_intent") != "sensor_query":
        return None

    normalized = normalize_text(user_text)
    resolution = _resolve_location(normalized, state)
    if resolution.error_kind == "clarification":
        return SensorAnswerPlan(
            "clarification",
            "Which location do you mean?",
            None,
            (),
        )
    if resolution.error_kind == "unknown_location":
        assert resolution.error_location is not None
        return SensorAnswerPlan(
            "unknown_location",
            f"I do not have sensor information for the {resolution.error_location}.",
            resolution.error_location,
            (),
        )
    if resolution.error_kind == "no_locations":
        return SensorAnswerPlan(
            "no_locations",
            "I do not have any sensor locations yet.",
            None,
            (),
        )

    assert resolution.location_id is not None
    location_id = resolution.location_id
    snapshot = state.snapshot(location_id)
    if snapshot is None:
        location = _display_location(location_id)
        return SensorAnswerPlan(
            "unknown_location",
            f"I do not have sensor information for the {location}.",
            location,
            (),
        )

    topics = set(route.get("topics", []))
    wants_temperature = "temperature" in topics
    wants_humidity = "humidity" in topics
    wants_conditions = "environment" in topics or (wants_temperature and wants_humidity)

    if wants_conditions:
        return _conditions_plan(snapshot, "celsius" in normalized)
    if wants_temperature:
        return _temperature_plan(snapshot, "celsius" in normalized)
    if wants_humidity:
        return _humidity_plan(snapshot)
    return _conditions_plan(snapshot, "celsius" in normalized)


def _resolve_location(
    normalized_text: str,
    state: SensorState,
) -> _LocationResolution:
    known_locations = state.known_locations()
    matches: list[tuple[str, int, int]] = []
    for location_id in known_locations:
        display_name = _display_location(location_id)
        for match in re.finditer(rf"\b{re.escape(display_name)}\b", normalized_text):
            matches.append((location_id, match.start(), match.end()))

    complete_matches = {
        location_id
        for location_id, start, end in matches
        if not any(
            other_start <= start
            and other_end >= end
            and (other_start, other_end) != (start, end)
            for _, other_start, other_end in matches
        )
    }
    if len(complete_matches) == 1:
        return _LocationResolution(location_id=complete_matches.pop())
    if len(complete_matches) > 1:
        return _LocationResolution(error_kind="clarification")

    named_match = _NAMED_LOCATION.search(normalized_text)
    if named_match is None:
        named_match = next(
            (
                match
                for pattern in _LEADING_LOCATION_PATTERNS
                if (match := pattern.match(normalized_text)) is not None
            ),
            None,
        )
    if named_match is not None:
        named_location = named_match.group("location").strip()
        if named_location not in _UNIT_ONLY:
            return _LocationResolution(
                error_kind="unknown_location",
                error_location=named_location,
            )

    if len(known_locations) == 1:
        return _LocationResolution(location_id=known_locations[0])
    if len(known_locations) > 1:
        return _LocationResolution(error_kind="clarification")
    return _LocationResolution(error_kind="no_locations")


def _conditions_plan(snapshot: LocationSnapshot, use_celsius: bool) -> SensorAnswerPlan:
    has_temperature = snapshot.temperature.state == "current"
    has_humidity = snapshot.humidity.state == "current"
    location = _display_location(snapshot.location_id)

    if has_temperature and has_humidity:
        value, unit = _temperature_value(snapshot.temperature.value, use_celsius)
        humidity = _format_number(snapshot.humidity.value)
        return SensorAnswerPlan(
            "reading",
            (
                f"The {location} is {value} degrees {unit} "
                f"with {humidity} percent relative humidity."
            ),
            location,
            (
                SensorFact("temperature", value, f"degrees {unit}"),
                SensorFact("humidity", humidity, "percent"),
            ),
            "conditions",
        )
    if has_temperature:
        plan = _temperature_plan(snapshot, use_celsius)
        return SensorAnswerPlan(
            plan.kind,
            plan.fallback,
            plan.location,
            plan.facts,
            "conditions",
        )
    if has_humidity:
        plan = _humidity_plan(snapshot)
        return SensorAnswerPlan(
            plan.kind,
            plan.fallback,
            plan.location,
            plan.facts,
            "conditions",
        )
    return SensorAnswerPlan(
        "unavailable",
        f"I do not have current sensor information for the {location}.",
        location,
        (),
        "conditions",
    )


def _temperature_plan(snapshot: LocationSnapshot, use_celsius: bool) -> SensorAnswerPlan:
    location = _display_location(snapshot.location_id)
    if snapshot.temperature.state != "current":
        return SensorAnswerPlan(
            "unavailable",
            f"I do not have a current temperature reading for the {location}.",
            location,
            (),
            "temperature",
        )

    value, unit = _temperature_value(snapshot.temperature.value, use_celsius)
    spoken_unit = f"degrees {unit}"
    return SensorAnswerPlan(
        "reading",
        f"The {location} temperature is {value} {spoken_unit}.",
        location,
        (SensorFact("temperature", value, spoken_unit),),
        "temperature",
    )


def _humidity_plan(snapshot: LocationSnapshot) -> SensorAnswerPlan:
    location = _display_location(snapshot.location_id)
    if snapshot.humidity.state != "current":
        return SensorAnswerPlan(
            "unavailable",
            f"I do not have a current humidity reading for the {location}.",
            location,
            (),
            "humidity",
        )

    humidity = _format_number(snapshot.humidity.value)
    return SensorAnswerPlan(
        "reading",
        f"The {location} humidity is {humidity} percent.",
        location,
        (SensorFact("humidity", humidity, "percent"),),
        "humidity",
    )


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


def validate_sensor_narration(text: str, plan: SensorAnswerPlan) -> bool:
    candidate = text.strip()
    if not candidate:
        return False

    patterns = _sensor_narration_patterns(plan)
    return any(re.fullmatch(pattern, candidate, re.IGNORECASE) for pattern in patterns)


def _sensor_narration_patterns(plan: SensorAnswerPlan) -> tuple[str, ...]:
    if plan.kind == "clarification":
        return (
            r"Which location do you mean\?",
            r"What location do you mean\?",
            r"What sensor location do you mean\?",
        )
    if plan.kind == "no_locations":
        return (
            r"I do not have any sensor locations yet\.",
            r"No sensor locations are available yet\.",
        )

    if plan.location is None:
        return ()
    location = re.escape(plan.location)

    if plan.kind == "unknown_location":
        return (
            rf"I do not have sensor information for the {location}\.",
            rf"There is no sensor information for the {location}\.",
            rf"Sensor information for the {location} is not available\.",
        )
    if plan.kind == "unavailable":
        if plan.subject in {"temperature", "humidity"}:
            subject = re.escape(plan.subject)
            return (
                rf"I do not have a current {subject} reading for the {location}\.",
                rf"There is no current {subject} reading for the {location}\.",
                rf"A current {subject} reading for the {location} is not available\.",
            )
        if plan.subject == "conditions":
            return (
                rf"I do not have current sensor information for the {location}\.",
                rf"There is no current sensor information for the {location}\.",
                rf"Current sensor information for the {location} is not available\.",
            )
        return ()
    if plan.kind != "reading":
        return ()

    facts = {fact.measurement: fact for fact in plan.facts}
    if set(facts) == {"temperature"}:
        return _single_reading_patterns(location, facts["temperature"])
    if set(facts) == {"humidity"}:
        return _single_reading_patterns(location, facts["humidity"])
    if set(facts) != {"temperature", "humidity"}:
        return ()

    temperature = facts["temperature"]
    humidity = facts["humidity"]
    temperature_value = re.escape(temperature.value)
    temperature_unit = re.escape(temperature.unit)
    humidity_value = re.escape(humidity.value)
    humidity_unit = re.escape(humidity.unit)
    return (
        rf"In the {location}, the temperature is(?: currently)? "
        rf"{temperature_value} {temperature_unit} and the humidity is(?: currently)? "
        rf"{humidity_value} {humidity_unit}\.",
        rf"The {location} temperature is(?: currently)? "
        rf"{temperature_value} {temperature_unit} and the humidity is(?: currently)? "
        rf"{humidity_value} {humidity_unit}\.",
        rf"The {location} temperature is(?: currently)? "
        rf"{temperature_value} {temperature_unit} with "
        rf"{humidity_value} {humidity_unit} relative humidity\.",
    )


def _single_reading_patterns(location: str, fact: SensorFact) -> tuple[str, ...]:
    measurement = re.escape(fact.measurement)
    value = re.escape(fact.value)
    unit = re.escape(fact.unit)
    return (
        rf"The {location} {measurement} is(?: currently)? {value} {unit}\.",
        rf"In the {location}, the {measurement} is(?: currently)? {value} {unit}\.",
        rf"The {measurement} in the {location} is(?: currently)? {value} {unit}\.",
        rf"The {location} {measurement} currently reads {value} {unit}\.",
    )
