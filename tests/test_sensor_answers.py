import unittest

from intent_router import analyze_query
from sensor_answers import (
    SensorAnswerPlan,
    SensorFact,
    build_sensor_answer,
    build_sensor_answer_plan,
    validate_sensor_narration,
)
from sensor_state import SensorState


def sensor_route(*topics: str) -> dict:
    return {"primary_intent": "sensor_query", "topics": list(topics)}


class SensorRoutingTests(unittest.TestCase):
    def test_routes_home_helper_questions_to_new_knowledge(self) -> None:
        cases = (
            ("what can you do", ["home_helper_overview.txt"]),
            ("does my household data leave this raspberry pi", ["home_helper_overview.txt"]),
            ("can you turn off the lights", ["home_helper_overview.txt"]),
            ("what is home assistant used for here", ["home_helper_overview.txt"]),
            ("what is mosquitto used for", ["home_helper_overview.txt"]),
            ("what does relative humidity mean", ["sensor_guidance.txt"]),
            ("what does a stale sensor reading mean", ["sensor_guidance.txt"]),
            ("what was the temperature yesterday", ["sensor_guidance.txt"]),
            ("what should i do during a medical emergency", ["safety_boundaries.txt"]),
        )

        for user_text, expected_files in cases:
            with self.subTest(user_text=user_text):
                route = analyze_query(user_text)
                self.assertTrue(route["needs_knowledge"])
                self.assertEqual(route["selected_files"], expected_files)

    def test_routes_environmental_questions_without_general_knowledge(self) -> None:
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


class SensorAnswerPlanTests(unittest.TestCase):
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

    def test_builds_formatted_temperature_and_combined_plans(self) -> None:
        state = self.current_living_room()

        temperature = build_sensor_answer_plan(
            "what is the living room temperature",
            sensor_route("temperature"),
            state,
        )
        conditions = build_sensor_answer_plan(
            "how are conditions in the living room",
            sensor_route("environment"),
            state,
        )

        self.assertEqual(
            temperature,
            SensorAnswerPlan(
                kind="reading",
                subject="temperature",
                fallback="The living room temperature is 70.7 degrees Fahrenheit.",
                location="living room",
                facts=(SensorFact("temperature", "70.7", "degrees Fahrenheit"),),
            ),
        )
        self.assertEqual(
            conditions,
            SensorAnswerPlan(
                kind="reading",
                subject="conditions",
                fallback=(
                    "The living room is 70.7 degrees Fahrenheit "
                    "with 45 percent relative humidity."
                ),
                location="living room",
                facts=(
                    SensorFact("temperature", "70.7", "degrees Fahrenheit"),
                    SensorFact("humidity", "45", "percent"),
                ),
            ),
        )

    def test_partial_conditions_plan_omits_the_unavailable_measurement(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )

        plan = build_sensor_answer_plan(
            "how are conditions in the living room",
            sensor_route("environment"),
            state,
        )

        self.assertEqual(
            plan,
            SensorAnswerPlan(
                kind="reading",
                subject="conditions",
                fallback="The living room temperature is 70.7 degrees Fahrenheit.",
                location="living room",
                facts=(SensorFact("temperature", "70.7", "degrees Fahrenheit"),),
            ),
        )


class SensorNarrationValidationTests(unittest.TestCase):
    def test_accepts_only_recognized_fact_preserving_shapes(self) -> None:
        temperature = SensorAnswerPlan(
            kind="reading",
            subject="temperature",
            fallback="The living room temperature is 70.7 degrees Fahrenheit.",
            location="living room",
            facts=(SensorFact("temperature", "70.7", "degrees Fahrenheit"),),
        )
        humidity = SensorAnswerPlan(
            kind="reading",
            subject="humidity",
            fallback="The living room humidity is 45 percent.",
            location="living room",
            facts=(SensorFact("humidity", "45", "percent"),),
        )
        conditions = SensorAnswerPlan(
            kind="reading",
            subject="conditions",
            fallback=(
                "The living room is 70.7 degrees Fahrenheit "
                "with 45 percent relative humidity."
            ),
            location="living room",
            facts=(
                SensorFact("temperature", "70.7", "degrees Fahrenheit"),
                SensorFact("humidity", "45", "percent"),
            ),
        )
        unavailable_humidity = SensorAnswerPlan(
            kind="unavailable",
            subject="humidity",
            fallback="I do not have a current humidity reading for the living room.",
            location="living room",
            facts=(),
        )
        unavailable_conditions = SensorAnswerPlan(
            kind="unavailable",
            subject="conditions",
            fallback="I do not have current sensor information for the living room.",
            location="living room",
            facts=(),
        )
        unknown = SensorAnswerPlan(
            kind="unknown_location",
            subject=None,
            fallback="I do not have sensor information for the bedroom.",
            location="bedroom",
            facts=(),
        )
        no_locations = SensorAnswerPlan(
            kind="no_locations",
            subject=None,
            fallback="I do not have any sensor locations yet.",
            location=None,
            facts=(),
        )
        clarification = SensorAnswerPlan(
            kind="clarification",
            subject=None,
            fallback="Which location do you mean?",
            location=None,
            facts=(),
        )

        cases = (
            (
                "In the living room, the temperature is 70.7 degrees Fahrenheit.",
                temperature,
            ),
            ("The humidity in the living room is currently 45 percent.", humidity),
            (
                "In the living room, the temperature is 70.7 degrees Fahrenheit "
                "and the humidity is 45 percent.",
                conditions,
            ),
            (
                "There is no current humidity reading for the living room.",
                unavailable_humidity,
            ),
            (
                "Current sensor information for the living room is not available.",
                unavailable_conditions,
            ),
            ("Sensor information for the bedroom is not available.", unknown),
            ("No sensor locations are available yet.", no_locations),
            ("What sensor location do you mean?", clarification),
        )

        for text, plan in cases:
            with self.subTest(text=text):
                self.assertTrue(validate_sensor_narration(text, plan))

    def test_rejects_changed_or_added_content(self) -> None:
        temperature = SensorAnswerPlan(
            kind="reading",
            subject="temperature",
            fallback="The living room temperature is 70.7 degrees Fahrenheit.",
            location="living room",
            facts=(SensorFact("temperature", "70.7", "degrees Fahrenheit"),),
        )
        conditions = SensorAnswerPlan(
            kind="reading",
            subject="conditions",
            fallback=(
                "The living room is 70.7 degrees Fahrenheit "
                "with 45 percent relative humidity."
            ),
            location="living room",
            facts=(
                SensorFact("temperature", "70.7", "degrees Fahrenheit"),
                SensorFact("humidity", "45", "percent"),
            ),
        )
        room_2 = SensorAnswerPlan(
            kind="reading",
            subject="temperature",
            fallback="The room 2 temperature is 68 degrees Fahrenheit.",
            location="room 2",
            facts=(SensorFact("temperature", "68", "degrees Fahrenheit"),),
        )
        cases = (
            ("The temperature is 70.7 degrees Fahrenheit.", temperature),
            ("The living room is 70.7 degrees Fahrenheit.", temperature),
            ("The living room temperature is 72 degrees Fahrenheit.", temperature),
            ("The living room temperature is 70.7 degrees Celsius.", temperature),
            ("The living room temperature is 70.7 degrees Fahrenheit at 8.", temperature),
            ("The room 3 temperature is 68 degrees Fahrenheit.", room_2),
            (
                "The living room temperature is 45 percent and humidity is "
                "70.7 degrees Fahrenheit.",
                conditions,
            ),
            (
                "The living room temperature is a comfortable 70.7 degrees Fahrenheit.",
                temperature,
            ),
            (
                "The living room temperature is 70.7 degrees Fahrenheit; seek shelter.",
                temperature,
            ),
            (
                "The living room temperature is 70.7 degrees Fahrenheit. Stay alert.",
                temperature,
            ),
            ("**The living room temperature is 70.7 degrees Fahrenheit.**", temperature),
            ("", temperature),
        )

        for text, plan in cases:
            with self.subTest(text=text):
                self.assertFalse(validate_sensor_narration(text, plan))


class SensorAnswerPlanEdgeCaseTests(unittest.TestCase):
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

    def test_builds_unavailable_and_no_current_information_plans(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest("artemis/sensors/living_room/status", b"online")

        humidity = build_sensor_answer_plan(
            "what is the humidity",
            sensor_route("humidity"),
            state,
        )
        conditions = build_sensor_answer_plan(
            "how are conditions",
            sensor_route("environment"),
            state,
        )

        self.assertEqual(
            humidity,
            SensorAnswerPlan(
                kind="unavailable",
                subject="humidity",
                fallback="I do not have a current humidity reading for the living room.",
                location="living room",
                facts=(),
            ),
        )
        self.assertEqual(
            conditions,
            SensorAnswerPlan(
                kind="unavailable",
                subject="conditions",
                fallback="I do not have current sensor information for the living room.",
                location="living room",
                facts=(),
            ),
        )

    def test_builds_unknown_location_and_clarification_plans(self) -> None:
        state = self.current_living_room()
        unknown = build_sensor_answer_plan(
            "what is the bedroom temperature",
            sensor_route("temperature"),
            state,
        )
        state.ingest("artemis/sensors/bedroom/status", b"online")
        clarification = build_sensor_answer_plan(
            "what is the temperature",
            sensor_route("temperature"),
            state,
        )

        self.assertEqual(
            unknown,
            SensorAnswerPlan(
                kind="unknown_location",
                subject=None,
                fallback="I do not have sensor information for the bedroom.",
                location="bedroom",
                facts=(),
            ),
        )
        self.assertEqual(
            clarification,
            SensorAnswerPlan(
                kind="clarification",
                subject=None,
                fallback="Which location do you mean?",
                location=None,
                facts=(),
            ),
        )

    def test_preserves_digits_in_a_validated_display_location(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/room_2/sensor/temperature/state",
            b"20",
        )

        plan = build_sensor_answer_plan(
            "what is the room 2 temperature",
            sensor_route("temperature"),
            state,
        )

        self.assertEqual(
            plan,
            SensorAnswerPlan(
                kind="reading",
                subject="temperature",
                fallback="The room 2 temperature is 68 degrees Fahrenheit.",
                location="room 2",
                facts=(SensorFact("temperature", "68", "degrees Fahrenheit"),),
            ),
        )

    def test_temp_shorthand_preserves_an_unknown_named_location(self) -> None:
        state = self.current_living_room()
        route = analyze_query("what is the dining room temp")

        plan = build_sensor_answer_plan(
            "what is the dining room temp",
            route,
            state,
        )

        self.assertEqual(route["primary_intent"], "sensor_query")
        self.assertEqual(
            plan,
            SensorAnswerPlan(
                kind="unknown_location",
                subject=None,
                fallback="I do not have sensor information for the dining room.",
                location="dining room",
                facts=(),
            ),
        )


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
