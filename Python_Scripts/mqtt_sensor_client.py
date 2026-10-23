from __future__ import annotations

import threading
from typing import Any

import paho.mqtt.client as mqtt

from sensor_state import SensorState


SUBSCRIPTIONS = (
    ("artemis/sensors/+/sensor/temperature/state", 1),
    ("artemis/sensors/+/sensor/humidity/state", 1),
    ("artemis/sensors/+/status", 1),
)


class MqttSensorClient:
    def __init__(
        self,
        state: SensorState,
        password: str,
        client: Any | None = None,
        host: str = "127.0.0.1",
        port: int = 1883,
    ) -> None:
        if not password:
            raise ValueError("The Artemis MQTT password cannot be empty.")

        self._state = state
        self._host = host
        self._port = port
        self._client = client or mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTv5,
        )
        self._diagnostics_lock = threading.Lock()
        self._connected = False
        self._rejected_messages = 0

        self._client.username_pw_set("artemis", password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=120)
        self._client.on_connect = self._on_connect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    @property
    def connected(self) -> bool:
        with self._diagnostics_lock:
            return self._connected

    @property
    def rejected_messages(self) -> int:
        with self._diagnostics_lock:
            return self._rejected_messages

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, 60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        connected = self._connection_succeeded(reason_code)
        with self._diagnostics_lock:
            self._connected = connected

        if connected:
            for topic, qos in SUBSCRIPTIONS:
                client.subscribe(topic, qos=qos)

    def _on_connect_fail(self, client, userdata) -> None:
        with self._diagnostics_lock:
            self._connected = False

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ) -> None:
        with self._diagnostics_lock:
            self._connected = False

    def _on_message(self, client, userdata, message) -> None:
        if self._state.ingest(message.topic, message.payload):
            return

        with self._diagnostics_lock:
            self._rejected_messages += 1

    @staticmethod
    def _connection_succeeded(reason_code) -> bool:
        if hasattr(reason_code, "is_failure"):
            return not reason_code.is_failure
        return int(reason_code) == 0
