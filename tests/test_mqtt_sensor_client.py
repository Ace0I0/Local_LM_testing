from types import SimpleNamespace
import unittest
from unittest.mock import patch

import paho.mqtt.client as mqtt

from mqtt_sensor_client import MqttSensorClient
from sensor_state import SensorState


class FakePahoClient:
    def __init__(self) -> None:
        self.credentials = None
        self.reconnect_delays = None
        self.connect_calls = []
        self.subscriptions = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self.on_connect = None
        self.on_connect_fail = None
        self.on_disconnect = None
        self.on_message = None

    def username_pw_set(self, username, password=None):
        self.credentials = (username, password)

    def reconnect_delay_set(self, min_delay=1, max_delay=120):
        self.reconnect_delays = (min_delay, max_delay)

    def connect_async(self, host, port=1883, keepalive=60):
        self.connect_calls.append((host, port, keepalive))

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))

    def loop_start(self):
        self.loop_started = True

    def disconnect(self):
        self.disconnected = True

    def loop_stop(self):
        self.loop_stopped = True


class MqttSensorClientTests(unittest.TestCase):
    def test_rejects_an_empty_password(self) -> None:
        with self.assertRaises(ValueError):
            MqttSensorClient(SensorState(), "")

    def test_builds_an_mqtt5_v2_client_and_configures_credentials(self) -> None:
        fake = FakePahoClient()
        with patch("mqtt_sensor_client.mqtt.Client", return_value=fake) as factory:
            adapter = MqttSensorClient(SensorState(), "private-value")

        factory.assert_called_once_with(
            mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTv5,
        )
        self.assertEqual(fake.credentials, ("artemis", "private-value"))
        self.assertEqual(fake.reconnect_delays, (1, 120))
        self.assertNotIn("private-value", repr(adapter))
        self.assertFalse(hasattr(adapter, "password"))

    def test_successful_connection_subscribes_to_read_only_topics(self) -> None:
        fake = FakePahoClient()
        adapter = MqttSensorClient(SensorState(), "secret", client=fake)

        fake.on_connect(fake, None, None, 0, None)

        self.assertTrue(adapter.connected)
        self.assertEqual(
            fake.subscriptions,
            [
                ("artemis/sensors/+/sensor/temperature/state", 1),
                ("artemis/sensors/+/sensor/humidity/state", 1),
                ("artemis/sensors/+/status", 1),
            ],
        )

    def test_refused_connection_does_not_subscribe(self) -> None:
        fake = FakePahoClient()
        adapter = MqttSensorClient(SensorState(), "secret", client=fake)

        fake.on_connect(fake, None, None, 135, None)

        self.assertFalse(adapter.connected)
        self.assertEqual(fake.subscriptions, [])

    def test_messages_update_real_state_and_count_only_rejections(self) -> None:
        state = SensorState()
        fake = FakePahoClient()
        adapter = MqttSensorClient(state, "secret", client=fake)

        fake.on_message(
            fake,
            None,
            SimpleNamespace(
                topic="artemis/sensors/living_room/sensor/temperature/state",
                payload=b"21.5",
            ),
        )
        fake.on_message(
            fake,
            None,
            SimpleNamespace(topic="artemis/sensors/living_room/status", payload=b"bad"),
        )

        self.assertEqual(state.snapshot("living_room").temperature.value, 21.5)
        self.assertEqual(adapter.rejected_messages, 1)

    def test_start_stop_and_connection_failure_are_non_throwing(self) -> None:
        fake = FakePahoClient()
        adapter = MqttSensorClient(
            SensorState(),
            "secret",
            client=fake,
            host="broker.local",
            port=1884,
        )

        adapter.start()
        fake.on_connect_fail(fake, None)
        fake.on_disconnect(fake, None, None, 128, None)
        adapter.stop()

        self.assertEqual(fake.connect_calls, [("broker.local", 1884, 60)])
        self.assertTrue(fake.loop_started)
        self.assertTrue(fake.disconnected)
        self.assertTrue(fake.loop_stopped)
        self.assertFalse(adapter.connected)


if __name__ == "__main__":
    unittest.main()
