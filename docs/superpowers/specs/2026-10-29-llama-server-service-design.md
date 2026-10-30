# llama-server Boot Service Design

## Intent

Start the existing local Qwen llama-server automatically when the Raspberry
Pi boots so Artemis can use its existing loopback API without manually
launching the model.

## Scope

- Install and enable one systemd service for llama-server.
- Keep the server bound to 127.0.0.1:8080.
- Preserve the current Qwen model, 8192-token context, Jinja template, and
  disabled-thinking options.
- Provide an interactive, repeatable Pi-side installer that collects
  machine-specific paths and verifies the server's HTTP health endpoint.

## Non-goals

- Starting Artemis automatically: it currently needs a terminal for keyboard
  input.
- Exposing the model API through Tailscale or the LAN.
- Downloading models, rebuilding llama.cpp, or changing inference settings.

## Approaches

1. A single systemd service installed by a setup wizard. Chosen because it
   starts before interactive use, restarts after failure, and keeps the
   existing native llama.cpp installation.
2. A shell startup file or tmux session. Rejected because it only starts after
   a user login and is not supervised by the host.
3. A container. Rejected because the native llama.cpp binary and GGUF already
   work on the Pi; Docker adds no required capability.

## Design

The installer will validate systemd, the configured service user, the
llama-server executable, and the GGUF model file. It will create a root-owned
configuration file outside the repository and a systemd unit that runs as the
configured non-root user. The service uses Restart=on-failure, waits for
networking, and executes the existing command with --host 127.0.0.1 --port
8080 -c 8192 --jinja and enable_thinking:false.

After enabling and starting the unit, the installer will require the unit to
be active and will query the loopback server before reporting success. It
will show systemd status and recent journal logs if startup fails.

## Security

The unit binds only to loopback, so Tailscale does not expose the inference
API. No model paths, service user name, or settings are secrets; no MQTT
credential is needed because Artemis is not part of this service.
