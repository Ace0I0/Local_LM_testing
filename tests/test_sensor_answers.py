import unittest

from intent_router import analyze_query
from sensor_answers import build_sensor_answer
from sensor_state import SensorState


def sensor_route(*topics: str) -> dict:
    return {"primary_intent": "sensor_query", "topics": list(topics)}


class SensorRoutingTests(unittest.TestCase):
    def test_routes_environmental_questions_without_eas_knowledge(self) -> None:
        cases = (
            ("what is the living room temperature", "temperature"),
            ("what is the living room temp", "temperature"),
            ("tell me the room temperature", "temperature"),
            ("how humid is the living room", "humidity"),
            ("how are conditions in the living room", "environment"),
            ("what is the tempeture", "temperature"),
        )

        for user_text, topic in cases:
            with self.subTest(user_text=user_text):
                route = analyze_query(user_text)
                self.assertEqual(route["primary_intent"], "sensor_query")
                self.assertEqual(route["topics"], [topic])
                self.assertFalse(route["needs_knowledge"])
                self.assertEqual(route["selected_files"], [])

    def test_explanation_about_temperature_is_not_a_sensor_query(self) -> None:
        cases = (
            "explain room temperature",
            "what is the history of temperature measurement",
        )

        for user_text in cases:
            with self.subTest(user_text=user_text):
                route = analyze_query(user_text)
                self.assertEqual(route["primary_intent"], "explanation")


class SensorAnswerTests(unittest.TestCase):
    def current_living_room(self) -> SensorState:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        state.ingest(
            "artemis/sensors/living_room/sensor/humidity/state",
            b"45.0",
        )
        state.ingest("artemis/sensors/living_room/status", b"online")
        return state

    def test_formats_current_temperature_humidity_and_conditions(self) -> None:
        state = self.current_living_room()

        answer_temperature = build_sensor_answer(
            "what is the living room temperature",
            sensor_route("temperature"),
            state,
        )
        answer_celsius = build_sensor_answer(
            "what is the living room temperature in celsius",
            sensor_route("temperature"),
            state,
        )
        answer_humidity = build_sensor_answer(
            "how humid is the living room",
            sensor_route("humidity"),
            state,
        )
        answer_conditions = build_sensor_answer(
            "how are conditions in the living room",
            sensor_route("environment"),
            state,
        )

        self.assertEqual(
            answer_temperature,
            "The living room temperature is 70.7 degrees Fahrenheit.",
        )
        self.assertEqual(
            answer_celsius,
            "The living room temperature is 21.5 degrees Celsius.",
        )
        self.assertEqual(answer_humidity, "The living room humidity is 45 percent.")
        self.assertEqual(
            answer_conditions,
            "The living room is 70.7 degrees Fahrenheit with 45 percent relative humidity.",
        )

    def test_general_conditions_omit_an_unavailable_measurement(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )

        answer = build_sensor_answer(
            "how are conditions in the living room",
            sensor_route("environment"),
            state,
        )

        self.assertEqual(
            answer,
            "The living room temperature is 70.7 degrees Fahrenheit.",
        )

    def test_direct_request_reports_no_current_measurement(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest("artemis/sensors/living_room/status", b"online")

        answer = build_sensor_answer(
            "what is the humidity",
            sensor_route("humidity"),
            state,
        )

        self.assertEqual(
            answer,
            "I do not have a current humidity reading for the living room.",
        )

    def test_general_request_reports_when_no_measurements_are_current(self) -> None:
        state = SensorState(clock=lambda: 181.0)
        state.ingest("artemis/sensors/living_room/status", b"online")

        answer = build_sensor_answer(
            "how are conditions",
            sensor_route("environment"),
            state,
        )

        self.assertEqual(
            answer,
            "I do not have current sensor information for the living room.",
        )

    def test_uses_the_only_location_when_none_was_named(self) -> None:
        answer = build_sensor_answer(
            "what is the temperature",
            sensor_route("temperature"),
            self.current_living_room(),
        )

        self.assertEqual(
            answer,
            "The living room temperature is 70.7 degrees Fahrenheit.",
        )

    def test_asks_for_location_when_multiple_are_known(self) -> None:
        state = self.current_living_room()
        state.ingest("artemis/sensors/bedroom/status", b"online")

        answer = build_sensor_answer(
            "what is the temperature",
            sensor_route("temperature"),
            state,
        )

        self.assertEqual(answer, "Which location do you mean?")

    def test_named_unknown_location_does_not_fall_back(self) -> None:
        cases = (
            ("what is the temperature in the bedroom", "temperature"),
            ("what is the bedroom temperature", "temperature"),
            ("how humid is the bedroom", "humidity"),
        )

        for user_text, topic in cases:
            with self.subTest(user_text=user_text):
                answer = build_sensor_answer(
                    user_text,
                    sensor_route(topic),
                    self.current_living_room(),
                )

                self.assertEqual(
                    answer,
                    "I do not have sensor information for the bedroom.",
                )

    def test_prefers_the_complete_overlapping_location_name(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/bedroom/sensor/temperature/state",
            b"10",
        )
        state.ingest(
            "artemis/sensors/master_bedroom/sensor/temperature/state",
            b"25",
        )

        answer = build_sensor_answer(
            "what is the master bedroom temperature",
            sensor_route("temperature"),
            state,
        )

        self.assertEqual(
            answer,
            "The master bedroom temperature is 77 degrees Fahrenheit.",
        )

    def test_asks_for_one_location_when_multiple_are_named(self) -> None:
        state = self.current_living_room()
        state.ingest("artemis/sensors/bedroom/status", b"online")

        answer = build_sensor_answer(
            "compare the bedroom and living room temperature",
            sensor_route("temperature"),
            state,
        )

        self.assertEqual(answer, "Which location do you mean?")

    def test_non_sensor_route_is_not_handled(self) -> None:
        answer = build_sensor_answer(
            "hello",
            {"primary_intent": "general_chat", "topics": ["general"]},
            self.current_living_room(),
        )

        self.assertIsNone(answer)


if __name__ == "__main__":
    unittest.main()
