# Mosquitto First Slice Design

Date: 2026-10-22  
Status: Approved

## Objective

Establish a small, persistent MQTT broker on the Raspberry Pi that can be tested over SSH before any ESP32, Home Assistant, or Artemis integration is added.

The slice succeeds when Mosquitto starts with the Pi, requires authentication, limits the test account to a disposable test topic, delivers a retained temperature/humidity payload at QoS 1, rejects anonymous clients, and preserves the retained payload across a service restart.

## Confirmed environment

- Raspberry Pi hostname: `RP`
- Architecture: ARM64 (`aarch64`)
- Operating system: Debian 13.2 (Trixie)
- Package manager: `apt`
- Service manager: systemd 257
- Passwordless `sudo` is available
- Mosquitto and its command-line clients are not currently installed
- The LAN is private and trusted

Debian 13 currently packages Mosquitto 2.0.21 for ARM64. The implementation must verify the installed version rather than assume it.

## Deployment choice

Install Debian's `mosquitto` and `mosquitto-clients` packages and run the broker as a native systemd service.

This is smaller than introducing Docker for one service and follows the host's existing package and service management. Docker remains available for later services where it provides a concrete benefit.

## Broker configuration

Keep Debian's main Mosquitto configuration intact. Add a dedicated Artemis fragment under `/etc/mosquitto/conf.d/` containing:

- A TCP listener on port `1883`
- Anonymous access disabled
- A password file under `/etc/mosquitto/`
- An ACL file under `/etc/mosquitto/`

The password and ACL files must be readable by the `mosquitto` service account and not world-readable. The broker password must be entered interactively and must never be written to this repository, terminal history, or logs.

TLS is intentionally deferred because the broker stays on the user's trusted private LAN. Authentication and authorization remain required so an accidental local client cannot publish or subscribe anonymously.

## Initial account and authorization

Create one setup-only account named `artemis_test`. Its ACL grants read/write access only to:

```text
artemis/test/#
```

This account is not the future Artemis runtime identity. Later slices will create separate least-privilege accounts for ESPHome publishers, Home Assistant, and Artemis's read-only consumer.

## Smoke-test contract

Use this disposable topic:

```text
artemis/test/climate
```

Publish this representative payload:

```json
{"temperature_c": 21.5, "humidity_pct": 45.0}
```

The message uses QoS 1 and the retain flag. This exercises the behavior needed for current sensor state without prematurely establishing the permanent ESPHome topic contract.

## SSH test flow

The setup procedure will support testing from the existing SSH session without sensor hardware:

1. Install the broker and clients.
2. Create the password and ACL files.
3. Add the Artemis listener configuration.
4. Start or restart Mosquitto and confirm the systemd unit is active.
5. Publish the retained test payload using authenticated credentials.
6. Subscribe for one message and verify the exact topic and payload are returned.
7. Attempt an anonymous subscription and require it to fail.
8. Restart Mosquitto.
9. Subscribe again and verify the retained payload survived.
10. Repeat the authenticated test through the Pi's LAN address rather than only `localhost`.

The password will be captured with hidden terminal input for client tests. It will remain only in the current shell process and will be unset when testing finishes.

## Delivery mechanism

Provide one interactive Bash setup wizard in the repository. It will:

- Check that the host provides Debian-compatible `apt`, systemd, and `sudo`
- Show and confirm every privileged stage before running it
- Install only `mosquitto` and `mosquitto-clients`
- Prompt through `mosquitto_passwd` rather than placing a password on a command line
- Write only the dedicated Artemis configuration, password, and ACL files
- Secure their ownership and permissions
- Restart the service and show useful journal output if startup fails
- Run the authenticated, anonymous-rejection, retained-message, restart, and LAN-listener checks
- Print the installed version, broker status, topic, and relevant file paths at completion

The wizard must be safe to rerun. It may update the `artemis_test` password and replace only Artemis-owned Mosquitto files; it must not overwrite Debian's main Mosquitto configuration or unrelated broker files.

## Failure handling

If package installation fails, stop without writing broker configuration.

If configuration or service startup fails, report `systemctl status` and recent `journalctl` entries. Do not weaken authentication as a fallback. Because Debian 13 ships Mosquitto 2.0.21, which predates the 2.1 `--test-config` option, service startup plus immediate status/log inspection is the authoritative configuration check.

If a smoke test fails, leave the broker configuration in place for diagnosis but print the exact failed check and a command the user can rerun. Never delete or overwrite files outside the Artemis-owned paths.

## Repository impact

The implementation should touch only:

- The interactive setup wizard under `scripts/`
- A short README section linking to the wizard and explaining the SSH test
- The existing project-direction documentation only if the permanent MQTT contract is later decided

No Python controller, router, knowledge, ESPHome, Home Assistant, or LLM code changes belong in this slice.

## Deferred work

- Permanent MQTT topic and payload contract
- ESPHome configuration and sensor hardware
- Home Assistant MQTT integration and dashboard
- Artemis MQTT subscription code
- Separate production users and ACLs
- MQTT TLS
- Firewall changes, unless testing shows the host already blocks the trusted LAN

## Sources

- [Eclipse Mosquitto authentication methods](https://mosquitto.org/documentation/authentication-methods/)
- [Eclipse Mosquitto broker manual](https://mosquitto.org/man/mosquitto-8.html)
- [Debian 13 Mosquitto package](https://packages.debian.org/trixie/mosquitto)
