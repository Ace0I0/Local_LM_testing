# Environmental MQTT Contract Design

Date: 2026-10-22
Status: Proposed

## Objective

Define the permanent MQTT wire contract for temperature, relative humidity, and Sensor Node availability. ESPHome publishes the state, Home Assistant displays it, and Artemis consumes it read-only.

This contract represents current state, not history or device control.

## Chosen approach

Use ESPHome's native separate scalar state topics. Do not publish a combined JSON mirror.

Separate topics preserve ESPHome and Home Assistant conventions, keep each payload directly parseable, and avoid maintaining two representations of the same reading. The shared domain terms are defined in [`GLOSSARY.md`](../../../GLOSSARY.md).

## Location identity

Each Sensor Node is identified by its installed location rather than its hardware. A Location ID must match:

```text
^[a-z0-9]+(?:_[a-z0-9]+)*$
```

Examples include `living_room`, `main_bedroom`, and `garage`. Moving a node to another location changes its MQTT identity and requires clearing the old retained topics.

Version one assumes at most one environmental Sensor Node per Location ID. Supporting multiple nodes in one location requires a future contract revision rather than an undocumented suffix convention.

## Topic contract

For a Location ID named `<location>`, the permanent topics are:

| Meaning | Topic | Payload |
| --- | --- | --- |
| Temperature | `artemis/sensors/<location>/sensor/temperature/state` | Celsius decimal |
| Relative humidity | `artemis/sensors/<location>/sensor/humidity/state` | Percentage decimal |
| Availability | `artemis/sensors/<location>/status` | `online` or `offline` |

The ESPHome `topic_prefix` is `artemis/sensors/<location>`. Its temperature and humidity component object names must remain `temperature` and `humidity` so the standard ESPHome topic structure produces the exact contract above.

Home Assistant discovery messages under `homeassistant/#` are transport metadata and are not part of this sensor-data contract.

## Payload rules

Measurement payloads are plain base-10 decimal text with no JSON wrapper, unit suffix, or percent sign.

Valid examples:

```text
21.5
-4.25
45.0
```

Temperature is expressed only in degrees Celsius. Home Assistant and Artemis may convert it to Fahrenheit for presentation.

Humidity is relative humidity and must be between `0` and `100`, inclusive. A consumer must reject empty payloads, nonnumeric text, `NaN`, infinity, and out-of-range humidity. Invalid messages do not replace the last valid Measurement State.

The contract does not impose a temperature range until the selected sensor hardware establishes a trustworthy operating range. It also does not require a fixed number of decimal places; consumers parse a finite decimal value rather than formatted display text.

## Delivery and freshness

Temperature, humidity, and availability use MQTT QoS 1 with the retain flag. A new consumer therefore receives the latest state immediately after subscribing.

ESPHome publishes retained `online` availability when it connects and configures a retained `offline` last will for unexpected disconnects. A clean shutdown also publishes `offline`.

The default measurement update interval is `60s`, exposed in ESPHome as the `sensor_update_interval` substitution. It may be changed in a node configuration or with ESPHome's command-line substitution support; there is no MQTT command for changing it at runtime.

A consumer considers a Measurement State stale after three configured reporting intervals. The default stale timeout is therefore `180s`. If a deployment changes `sensor_update_interval`, its consumer configuration must keep the stale timeout at least three times the new interval.

Availability and freshness remain distinct:

- `offline` makes the location unavailable immediately.
- `online` means the MQTT client is connected, not that its sensor is healthy.
- An online node whose valid Measurement State exceeds the stale timeout is stale.

MQTT carries only current state. Home Assistant or Artemis owns timestamps and history after receiving messages.

## Consumer subscriptions

Artemis's read-only consumer will subscribe to:

```text
artemis/sensors/+/sensor/temperature/state
artemis/sensors/+/sensor/humidity/state
artemis/sensors/+/status
```

Home Assistant consumes the same state through ESPHome MQTT discovery. Neither consumer receives device-control authority from this contract.

## Rename and removal behavior

Moving, renaming, or removing a Sensor Node requires publishing a zero-length retained message to each old state and status topic. This removes obsolete retained values that would otherwise appear to represent a live location.

The cleanup targets are resolved from the old Location ID before any configuration is changed. No wildcard deletion is allowed.

## Acceptance criteria

A conforming Sensor Node and consumer must demonstrate that:

1. Temperature and humidity publish to the exact topics for the configured Location ID.
2. Payloads are unitless decimal text using Celsius and relative-humidity percentage semantics.
3. State arrives at QoS 1 and is retained for new subscribers.
4. Availability changes to `online` on connection and `offline` after a clean or unexpected disconnect.
5. The default update interval is 60 seconds and can be overridden as a deployment setting.
6. Consumers reject malformed and out-of-range humidity payloads without replacing their last valid values.
7. Consumers distinguish offline locations from online locations with stale measurements.
8. Renaming or removing a node clears only its three exact old retained topics.

## Deferred work

- Production Mosquitto usernames, passwords, and ACLs
- ESPHome hardware-specific configuration and the separate sensor-node repository
- Home Assistant installation and dashboard design
- Artemis MQTT subscription and storage code
- Alert thresholds and unusual-reading rules
- Historical storage and daily-summary retention
- Additional sensor types
- MQTT TLS outside the trusted LAN

## Alternatives rejected

**Combined JSON snapshot:** This makes temperature and humidity atomic for Artemis but requires custom ESPHome publishing and Home Assistant templates.

**Scalar topics plus a JSON mirror:** This creates two sources of truth and adds synchronization failure modes.

**Hardware-based node IDs:** These survive physical moves but require a separate location registry before Artemis can answer location-oriented questions.

**Runtime interval commands:** These add device-control behavior to a read-only first version and complicate stale-reading calculation.
