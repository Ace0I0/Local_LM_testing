import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import load_llm_sam as controller
from intent_router import analyze_query
from sensor_answers import build_sensor_answer_plan, validate_sensor_narration
from sensor_state import SensorState


class MultiRoomSensorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.state = SensorState(clock=lambda: self.now)
        for room, temperature, humidity in (
            ('bedroom', b'20', b'55'), ('game_room', b'25', b'40')
        ):
            self.state.ingest(f'artemis/sensors/{room}/sensor/temperature/state', temperature)
            self.state.ingest(f'artemis/sensors/{room}/sensor/humidity/state', humidity)
            self.state.ingest(f'artemis/sensors/{room}/status', b'online')

    def plan(self, question):
        route = analyze_query(question)
        self.assertEqual(route['primary_intent'], 'sensor_query')
        self.assertFalse(route['needs_knowledge'])
        plan = build_sensor_answer_plan(question, route, self.state)
        self.assertIsNotNone(plan)
        return plan

    def test_house_summary_contains_each_room_and_requested_units(self):
        for question in ('How are conditions around the house in Celsius?',
                         'Give me a house summary in Celsius',
                         'Show readings for all rooms in Celsius'):
            with self.subTest(question=question):
                plan = self.plan(question)
                self.assertEqual(plan.kind, 'summary')
                self.assertIn('bedroom is 20 degrees Celsius with 55 percent', plan.fallback)
                self.assertIn('game room is 25 degrees Celsius with 40 percent', plan.fallback)

    def test_temperature_only_summary_does_not_include_humidity(self):
        plan = self.plan('What is the temperature in all rooms?')
        self.assertIn('68 degrees Fahrenheit', plan.fallback)
        self.assertIn('77 degrees Fahrenheit', plan.fallback)
        self.assertNotIn('percent', plan.fallback)

    def test_extrema_are_computed_from_measurements(self):
        for question, winner, value in (
            ('Which room is warmest?', 'game room', '77 degrees Fahrenheit'),
            ('Which room is coldest?', 'bedroom', '68 degrees Fahrenheit'),
            ('Which room is most humid?', 'bedroom', '55 percent'),
            ('Which room is least humid?', 'game room', '40 percent'),
            ('Which room has the highest temperature?', 'game room', '77 degrees Fahrenheit'),
            ('Which room has the lowest humidity?', 'game room', '40 percent'),
            ('Which room is the warmest?', 'game room', '77 degrees Fahrenheit'),
            ('Which is the coldest room?', 'bedroom', '68 degrees Fahrenheit'),
        ):
            with self.subTest(question=question):
                plan = self.plan(question)
                self.assertEqual(plan.kind, 'comparison')
                self.assertIn(winner, plan.intro)
                self.assertIn(value, plan.fallback)

    def test_two_named_rooms_are_compared_without_other_rooms(self):
        self.state.ingest('artemis/sensors/garage/sensor/temperature/state', b'30')
        plan = self.plan('Compare the bedroom and game room temperature in Celsius')
        self.assertEqual(plan.kind, 'summary')
        self.assertIn('bedroom temperature is 20 degrees Celsius', plan.fallback)
        self.assertIn('game room temperature is 25 degrees Celsius', plan.fallback)
        self.assertNotIn('garage', plan.fallback)
        unknown = self.plan('Compare the bedroom and kitchen temperature')
        self.assertEqual(unknown.kind, 'unknown_location')
        self.assertIn('kitchen', unknown.fallback)

    def test_controller_falls_back_if_multi_room_narration_changes_a_value(self):
        question = 'What is the temperature in all rooms?'
        plan = self.plan(question)
        with (patch.object(controller, 'ask_local_model', return_value=(plan.fallback.replace('68', '99'), {})),
              patch.object(controller, 'make_sam_wav') as speak,
              redirect_stdout(StringIO())):
            controller.handle_sensor_turn(question, analyze_query(question), self.state,
                                          {'name': 'Artemis'}, {'tone': []})
        speak.assert_called_once_with(plan.fallback, {'name': 'Artemis'})

    def test_ties_and_single_current_room_are_explicit(self):
        self.state.ingest('artemis/sensors/bedroom/sensor/temperature/state', b'25')
        plan = self.plan('Which room is warmest?')
        self.assertIn('tied', plan.intro)
        self.assertIn('bedroom', plan.intro)
        self.assertIn('game room', plan.intro)
        self.state.ingest('artemis/sensors/bedroom/status', b'offline')
        plan = self.plan('Which room is warmest?')
        self.assertIn('Only one room', plan.intro)
        self.assertNotIn('warmest', plan.intro)
        self.assertIn('current temperature reading for the bedroom', plan.fallback)

    def test_offline_stale_and_missing_measurements_are_not_ranked(self):
        self.now = 181.0
        self.state.ingest('artemis/sensors/game_room/sensor/temperature/state', b'26')
        self.state.ingest('artemis/sensors/garage/status', b'online')
        plan = self.plan('Which room is coldest?')
        self.assertIn('Only one room', plan.intro)
        self.assertIn('78.8 degrees Fahrenheit', plan.fallback)
        self.assertNotIn('68 degrees', plan.fallback)
        self.assertIn('current temperature reading for the garage', plan.fallback)
        self.state.ingest('artemis/sensors/game_room/status', b'offline')
        self.assertNotIn('degrees', self.plan('Which room is warmest?').fallback)

    def test_empty_house_and_ambiguous_measurement_are_honest(self):
        self.state = SensorState()
        self.assertEqual(self.plan('Give me a house summary').kind, 'no_locations')
        self.assertEqual(self.plan('Which room is warmest?').kind, 'no_locations')

    def test_multi_room_narration_allows_rephrasing_but_rejects_corruption(self):
        plan = self.plan('What is the temperature in all rooms?')
        narration = ('In the bedroom, the temperature is 68 degrees Fahrenheit. '
                     'The temperature in the game room is 77 degrees Fahrenheit.')
        self.assertTrue(validate_sensor_narration(narration, plan))
        self.assertTrue(validate_sensor_narration(plan.fallback, plan))
        swapped = narration.replace('68', 'SWAP').replace('77', '68').replace('SWAP', '77')
        for bad in (swapped,
                    narration.split('. ')[0] + '.', narration + ' Open a window.',
                    narration.replace('Fahrenheit', 'Celsius'),
                    narration.replace('game room', 'garage')):
            self.assertFalse(validate_sensor_narration(bad, plan), bad)
        comparison = self.plan('Which room is warmest?')
        self.assertTrue(validate_sensor_narration(comparison.fallback, comparison))
        self.assertFalse(validate_sensor_narration(
            comparison.fallback.replace('warmest', 'coldest'), comparison))

    def test_controller_supplies_room_facts_and_uses_longer_response_budget(self):
        question = 'What is the temperature in all rooms?'
        plan = self.plan(question)
        with (patch.object(controller, 'ask_local_model', return_value=(plan.fallback, {})) as ask,
              patch.object(controller, 'make_sam_wav') as speak,
              redirect_stdout(StringIO())):
            controller.handle_sensor_turn(question, analyze_query(question), self.state,
                                          {'name': 'Artemis'}, {'tone': []})
        self.assertIn('Location: bedroom', ask.call_args.args[1])
        self.assertIn('Location: game room', ask.call_args.args[1])
        self.assertGreater(ask.call_args.args[2], 64)
        speak.assert_called_once_with(plan.fallback, {'name': 'Artemis'})

    def test_historical_and_explanatory_questions_are_not_live_rankings(self):
        for question in ('Which room was warmest yesterday?', 'Explain relative humidity'):
            self.assertNotEqual(analyze_query(question)['primary_intent'], 'sensor_query')
