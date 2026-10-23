from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

import load_llm_sam as controller
from intent_router import analyze_query
from sensor_state import SensorState


class SensorControllerTests(unittest.TestCase):
    def test_build_system_prompt_reuses_a_provided_route(self) -> None:
        route = analyze_query("hello artemis")
        identity = {"name": "Artemis", "core_rules": []}
        mode = {"display_name": "Test", "tone": [], "response_rules": []}

        with patch.object(
            controller,
            "route_intent",
            side_effect=AssertionError("route was recalculated"),
        ):
            _, debug = controller.build_system_prompt(
                identity,
                mode,
                "hello artemis",
                route=route,
            )

        self.assertIs(debug["router"], route)

    def test_mqtt_password_uses_environment_without_prompting(self) -> None:
        password = controller.get_mqtt_password(
            {"ARTEMIS_MQTT_PASSWORD": "environment-secret"},
            lambda _: self.fail("prompt should not be called"),
        )

        self.assertEqual(password, "environment-secret")

    def test_mqtt_password_uses_hidden_prompt_when_environment_is_unset(self) -> None:
        password = controller.get_mqtt_password({}, lambda _: "prompt-secret")

        self.assertEqual(password, "prompt-secret")

    def test_mqtt_password_rejects_empty_values(self) -> None:
        with self.assertRaises(ValueError):
            controller.get_mqtt_password({"ARTEMIS_MQTT_PASSWORD": ""}, lambda _: "unused")
        with self.assertRaises(ValueError):
            controller.get_mqtt_password({}, lambda _: "")

    def test_sensor_turn_speaks_the_direct_answer(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        output = StringIO()

        with patch.object(controller, "make_sam_wav") as speak, redirect_stdout(output):
            handled = controller.handle_sensor_turn(
                "what is the temperature",
                route,
                state,
                {"name": "Artemis"},
            )

        self.assertTrue(handled)
        self.assertIn("The living room temperature is 70.7 degrees Fahrenheit.", output.getvalue())
        speak.assert_called_once_with(
            "The living room temperature is 70.7 degrees Fahrenheit.",
            {"name": "Artemis"},
        )

    def test_non_sensor_turn_is_left_for_the_existing_pipeline(self) -> None:
        with patch.object(
            controller,
            "make_sam_wav",
            side_effect=AssertionError("SAM should not be called"),
        ):
            handled = controller.handle_sensor_turn(
                "hello",
                {"primary_intent": "general_chat", "topics": ["general"]},
                SensorState(),
                {"name": "Artemis"},
            )

        self.assertFalse(handled)


if __name__ == "__main__":
    unittest.main()
