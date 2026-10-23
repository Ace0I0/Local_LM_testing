from __future__ import annotations

from dataclasses import dataclass
import math
import re
import threading
import time
from typing import Callable, Literal


MeasurementStatus = Literal["current", "missing", "stale", "offline"]
AvailabilityStatus = Literal["online", "offline", "unknown"]

_TOPIC_PATTERN = re.compile(
    r"^artemis/sensors/"
    r"(?P<location>[a-z0-9]+(?:_[a-z0-9]+)*)/"
    r"(?:sensor/(?P<measurement>temperature|humidity)/state|(?P<status>status))$"
)
_DECIMAL_PATTERN = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")


@dataclass(frozen=True)
class MeasurementSnapshot:
    value: float | None
    state: MeasurementStatus


@dataclass(frozen=True)
class LocationSnapshot:
    location_id: str
    temperature: MeasurementSnapshot
    humidity: MeasurementSnapshot
    availability: AvailabilityStatus


@dataclass
class _Reading:
    value: float
    received_at: float


@dataclass
class _LocationState:
    temperature: _Reading | None = None
    humidity: _Reading | None = None
    availability: AvailabilityStatus = "unknown"


class SensorState:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        stale_after: float = 180.0,
    ) -> None:
        self._clock = clock
        self._stale_after = stale_after
        self._locations: dict[str, _LocationState] = {}
        self._lock = threading.Lock()

    def ingest(self, topic: str, payload: bytes) -> bool:
        match = _TOPIC_PATTERN.fullmatch(topic)
        if match is None:
            return False

        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            return False

        kind = match.group("measurement") or "status"
        if kind == "status":
            if text not in {"online", "offline"}:
                return False
            value: float | AvailabilityStatus = text
        else:
            if _DECIMAL_PATTERN.fullmatch(text) is None:
                return False
            value = float(text)
            if not math.isfinite(value):
                return False
            if kind == "humidity" and not 0 <= value <= 100:
                return False

        location_id = match.group("location")
        received_at = self._clock()
        with self._lock:
            location = self._locations.setdefault(location_id, _LocationState())
            if kind == "status":
                location.availability = value
            else:
                setattr(location, kind, _Reading(value=value, received_at=received_at))
        return True

    def snapshot(self, location_id: str) -> LocationSnapshot | None:
        with self._lock:
            location = self._locations.get(location_id)
            if location is None:
                return None

            now = self._clock()
            return LocationSnapshot(
                location_id=location_id,
                temperature=self._measurement_snapshot(
                    location.temperature,
                    location.availability,
                    now,
                ),
                humidity=self._measurement_snapshot(
                    location.humidity,
                    location.availability,
                    now,
                ),
                availability=location.availability,
            )

    def known_locations(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._locations))

    def _measurement_snapshot(
        self,
        reading: _Reading | None,
        availability: AvailabilityStatus,
        now: float,
    ) -> MeasurementSnapshot:
        if reading is None:
            return MeasurementSnapshot(value=None, state="missing")
        if availability == "offline":
            return MeasurementSnapshot(value=reading.value, state="offline")
        if now - reading.received_at > self._stale_after:
            return MeasurementSnapshot(value=reading.value, state="stale")
        return MeasurementSnapshot(value=reading.value, state="current")
