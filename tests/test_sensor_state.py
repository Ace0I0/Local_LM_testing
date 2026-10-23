import unittest

from sensor_state import SensorState


class MutableClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class SensorStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = MutableClock()
        self.state = SensorState(clock=self.clock)

    def test_accepts_the_three_contract_topics(self) -> None:
        self.assertTrue(
            self.state.ingest(
                "artemis/sensors/living_room/sensor/temperature/state",
                b"21.5",
            )
        )
        self.assertTrue(
            self.state.ingest(
                "artemis/sensors/living_room/sensor/humidity/state",
                b"45.0",
            )
        )
        self.assertTrue(
            self.state.ingest("artemis/sensors/living_room/status", b"online")
        )

        snapshot = self.state.snapshot("living_room")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.temperature.value, 21.5)
        self.assertEqual(snapshot.temperature.state, "current")
        self.assertEqual(snapshot.humidity.value, 45.0)
        self.assertEqual(snapshot.humidity.state, "current")
        self.assertEqual(snapshot.availability, "online")

    def test_rejects_topics_outside_the_contract(self) -> None:
        invalid_topics = (
            "artemis/sensors/Living-Room/status",
            "artemis/sensors/living_room/extra/status",
            "artemis/sensors/+/status",
            "artemis/sensors/living__room/status",
            "artemis/sensors/living_room/sensor/pressure/state",
            "artemis/sensors/living_room/sensor/temperature",
        )

        for topic in invalid_topics:
            with self.subTest(topic=topic):
                self.assertFalse(self.state.ingest(topic, b"online"))

        self.assertEqual(self.state.known_locations(), ())

    def test_rejects_invalid_measurements_without_replacing_valid_state(self) -> None:
        temperature_topic = "artemis/sensors/living_room/sensor/temperature/state"
        humidity_topic = "artemis/sensors/living_room/sensor/humidity/state"
        self.assertTrue(self.state.ingest(temperature_topic, b"21.5"))
        self.assertTrue(self.state.ingest(humidity_topic, b"45.0"))

        invalid_temperature = (b"", b"\xff", b"NaN", b"inf", b"-inf", b"1e2", b" 22.0 ")
        invalid_humidity = (b"", b"\xff", b"NaN", b"inf", b"-inf", b"-0.1", b"100.1")

        for payload in invalid_temperature:
            with self.subTest(kind="temperature", payload=payload):
                self.assertFalse(self.state.ingest(temperature_topic, payload))

        for payload in invalid_humidity:
            with self.subTest(kind="humidity", payload=payload):
                self.assertFalse(self.state.ingest(humidity_topic, payload))

        snapshot = self.state.snapshot("living_room")
        self.assertEqual(snapshot.temperature.value, 21.5)
        self.assertEqual(snapshot.humidity.value, 45.0)

    def test_rejects_invalid_availability_without_replacing_valid_state(self) -> None:
        topic = "artemis/sensors/living_room/status"
        self.assertTrue(self.state.ingest(topic, b"online"))
        self.assertFalse(self.state.ingest(topic, b"unknown"))
        self.assertFalse(self.state.ingest(topic, b" online "))

        self.assertEqual(self.state.snapshot("living_room").availability, "online")

    def test_reading_is_current_through_180_second_boundary(self) -> None:
        topic = "artemis/sensors/living_room/sensor/temperature/state"
        self.assertTrue(self.state.ingest(topic, b"21.5"))

        self.clock.now = 180.0
        self.assertEqual(self.state.snapshot("living_room").temperature.state, "current")

        self.clock.now = 180.001
        self.assertEqual(self.state.snapshot("living_room").temperature.state, "stale")

    def test_offline_overrides_current_readings_and_online_restores_them(self) -> None:
        self.state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        self.state.ingest("artemis/sensors/living_room/status", b"offline")

        offline = self.state.snapshot("living_room")
        self.assertEqual(offline.temperature.state, "offline")
        self.assertEqual(offline.availability, "offline")

        self.state.ingest("artemis/sensors/living_room/status", b"online")
        online = self.state.snapshot("living_room")
        self.assertEqual(online.temperature.state, "current")
        self.assertEqual(online.availability, "online")

    def test_partial_locations_are_known_and_sorted(self) -> None:
        self.state.ingest("artemis/sensors/upstairs/status", b"online")
        self.state.ingest(
            "artemis/sensors/living_room/sensor/humidity/state",
            b"45",
        )

        self.assertEqual(self.state.known_locations(), ("living_room", "upstairs"))
        living_room = self.state.snapshot("living_room")
        self.assertEqual(living_room.temperature.state, "missing")
        self.assertEqual(living_room.humidity.state, "current")
        self.assertEqual(living_room.availability, "unknown")

    def test_repeated_delivery_refreshes_the_receipt_time(self) -> None:
        topic = "artemis/sensors/living_room/sensor/temperature/state"
        self.state.ingest(topic, b"21.5")
        self.clock.now = 100.0
        self.state.ingest(topic, b"21.5")

        self.clock.now = 280.0
        self.assertEqual(self.state.snapshot("living_room").temperature.state, "current")
        self.clock.now = 280.001
        self.assertEqual(self.state.snapshot("living_room").temperature.state, "stale")


if __name__ == "__main__":
    unittest.main()
