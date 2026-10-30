from contextlib import redirect_stdout
import http.client
from io import StringIO
import json
import unittest
import urllib.error
from unittest.mock import patch

import load_llm_sam as controller
from intent_router import analyze_query
from sensor_answers import build_sensor_answer_plan
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

    def test_sensor_prompt_contains_only_identity_mode_and_trusted_facts(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        plan = build_sensor_answer_plan("what is the temperature", route, state)
        assert plan is not None

        prompt = controller.build_sensor_narration_prompt(
            {"name": "Artemis", "type": "local-first home helper"},
            {"display_name": "Home Helper", "tone": ["calm", "direct"]},
            plan,
        )

        self.assertIn("You are Artemis, a local-first home helper.", prompt)
        self.assertIn("Current mode: Home Helper", prompt)
        self.assertIn("Tone: calm, direct", prompt)
        self.assertIn("Location: living room", prompt)
        self.assertIn("temperature: 70.7 degrees Fahrenheit", prompt)
        self.assertIn("Rephrase only the trusted sensor facts", prompt)
        self.assertNotIn("Relevant local knowledge", prompt)

    def test_sensor_turn_speaks_validated_model_narration(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        output = StringIO()
        narration = "In the living room, the temperature is 70.7 degrees Fahrenheit."

        with (
            patch.object(
                controller,
                "ask_local_model",
                return_value=(narration, {}),
            ) as ask_model,
            patch.object(controller, "make_sam_wav") as speak,
            redirect_stdout(output),
        ):
            handled = controller.handle_sensor_turn(
                "what is the temperature",
                route,
                state,
                {"name": "Artemis"},
                {"display_name": "Home Helper", "tone": []},
            )

        self.assertTrue(handled)
        self.assertIn(narration, output.getvalue())
        speak.assert_called_once_with(narration, {"name": "Artemis"})
        self.assertEqual(ask_model.call_args.args[2], 64)
        self.assertEqual(ask_model.call_args.kwargs, {"timeout": 60.0})

    def test_sensor_turn_falls_back_when_narration_is_invalid_or_empty(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        fallback = "The living room temperature is 70.7 degrees Fahrenheit."
        cases = (
            "The thermostat registers 72 degrees. Proceed to shelter.",
            "",
        )

        for narration in cases:
            with self.subTest(narration=narration):
                output = StringIO()
                with (
                    patch.object(
                        controller,
                        "ask_local_model",
                        return_value=(narration, {}),
                    ),
                    patch.object(controller, "make_sam_wav") as speak,
                    redirect_stdout(output),
                ):
                    handled = controller.handle_sensor_turn(
                        "what is the temperature",
                        route,
                        state,
                        {"name": "Artemis"},
                        {"display_name": "Home Helper", "tone": []},
                    )

                self.assertTrue(handled)
                self.assertIn(fallback, output.getvalue())
                speak.assert_called_once_with(fallback, {"name": "Artemis"})

    def test_sensor_turn_falls_back_on_model_or_response_errors(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        fallback = "The living room temperature is 70.7 degrees Fahrenheit."
        errors = (
            urllib.error.URLError("connection refused"),
            TimeoutError("timed out"),
            KeyError("choices"),
            IndexError("missing choice"),
            TypeError("invalid response"),
            ValueError("invalid value"),
            json.JSONDecodeError("invalid json", "not-json", 0),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                output = StringIO()
                with (
                    patch.object(controller, "ask_local_model", side_effect=error),
                    patch.object(controller, "make_sam_wav") as speak,
                    redirect_stdout(output),
                ):
                    handled = controller.handle_sensor_turn(
                        "what is the temperature",
                        route,
                        state,
                        {"name": "Artemis"},
                        {"display_name": "Home Helper", "tone": []},
                    )

                self.assertTrue(handled)
                self.assertIn(fallback, output.getvalue())
                speak.assert_called_once_with(fallback, {"name": "Artemis"})

    def test_sensor_turn_falls_back_on_non_text_http_content(self) -> None:
        class FakeResponse:
            def __init__(self, content: object) -> None:
                self.content = content

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {"choices": [{"message": {"content": self.content}}]}
                ).encode("utf-8")

        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        fallback = "The living room temperature is 70.7 degrees Fahrenheit."

        for content in (None, {}, [], 72):
            with self.subTest(content=content):
                output = StringIO()
                with (
                    patch.object(
                        controller.urllib.request,
                        "urlopen",
                        return_value=FakeResponse(content),
                    ),
                    patch.object(controller, "make_sam_wav") as speak,
                    redirect_stdout(output),
                ):
                    handled = controller.handle_sensor_turn(
                        "what is the temperature",
                        route,
                        state,
                        {"name": "Artemis"},
                        {"display_name": "Home Helper", "tone": []},
                    )

                self.assertTrue(handled)
                self.assertIn(fallback, output.getvalue())
                speak.assert_called_once_with(fallback, {"name": "Artemis"})

    def test_sensor_turn_falls_back_on_interrupted_http_responses(self) -> None:
        state = SensorState(clock=lambda: 0.0)
        state.ingest(
            "artemis/sensors/living_room/sensor/temperature/state",
            b"21.5",
        )
        route = {"primary_intent": "sensor_query", "topics": ["temperature"]}
        fallback = "The living room temperature is 70.7 degrees Fahrenheit."
        errors = (
            http.client.RemoteDisconnected(),
            http.client.IncompleteRead(b"partial"),
            ConnectionResetError("connection reset"),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                output = StringIO()
                with (
                    patch.object(
                        controller.urllib.request,
                        "urlopen",
                        side_effect=error,
                    ),
                    patch.object(controller, "make_sam_wav") as speak,
                    redirect_stdout(output),
                ):
                    handled = controller.handle_sensor_turn(
                        "what is the temperature",
                        route,
                        state,
                        {"name": "Artemis"},
                        {"display_name": "Home Helper", "tone": []},
                    )

                self.assertTrue(handled)
                self.assertIn(fallback, output.getvalue())
                speak.assert_called_once_with(fallback, {"name": "Artemis"})

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
                {"display_name": "Home Helper", "tone": []},
            )

        self.assertFalse(handled)


if __name__ == "__main__":
    unittest.main()
