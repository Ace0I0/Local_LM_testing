#!/usr/bin/env bash

set -euo pipefail

readonly SERVICE_NAME=artemis-llama.service
readonly SETTINGS_FILE=/etc/artemis/llama-server.env
readonly UNIT_FILE=/etc/systemd/system/artemis-llama.service

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

diagnostics() {
  sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
  sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

require_path() {
  [[ -e "$1" ]] || fail "Path does not exist: $1"
  [[ "$1" != *[[:space:]]* ]] || fail "Paths containing whitespace are not supported."
}

read_value() {
  local name="$1" prompt="$2"
  read -r -p "$prompt" "$name"
  [[ -n "${!name}" ]] || fail "A value is required."
}

verify_health() {
  local attempt
  for attempt in {1..30}; do
    if curl --fail --silent --show-error --max-time 5 \
      http://127.0.0.1:8080/health >/dev/null; then
      return 0
    fi
    sleep 2
  done
  diagnostics
  fail "llama-server did not become healthy on 127.0.0.1:8080."
}

require_command curl
require_command sudo
require_command systemctl
sudo -v

printf 'Artemis llama-server boot setup\n\n'
read_value LLAMA_SERVICE_USER "Pi user that owns llama.cpp and the model: "
id -u "$LLAMA_SERVICE_USER" >/dev/null 2>&1 ||
  fail "No such user: $LLAMA_SERVICE_USER"
[[ "$LLAMA_SERVICE_USER" != root ]] || fail "Use a non-root service user."

read_value LLAMA_SERVER "Absolute path to llama-server: "
read_value LLAMA_MODEL "Absolute path to the Qwen GGUF: "
require_path "$LLAMA_SERVER"
require_path "$LLAMA_MODEL"
[[ -x "$LLAMA_SERVER" ]] || fail "llama-server is not executable: $LLAMA_SERVER"

printf '\nThis will install %s and enable it at boot. Continue? [y/N] ' "$SERVICE_NAME"
read -r CONFIRM
[[ "$CONFIRM" =~ ^[Yy] ]] || exit 0

sudo install -d -m 0755 /etc/artemis
sudo tee "$SETTINGS_FILE" >/dev/null <<EOF
LLAMA_SERVER=$LLAMA_SERVER
LLAMA_MODEL=$LLAMA_MODEL
EOF
sudo chmod 0644 "$SETTINGS_FILE"

sudo tee "$UNIT_FILE" >/dev/null <<EOF
[Unit]
Description=Artemis local Qwen llama-server
After=network.target

[Service]
Type=simple
User=$LLAMA_SERVICE_USER
EnvironmentFile=$SETTINGS_FILE
ExecStart=$LLAMA_SERVER -m $LLAMA_MODEL --host 127.0.0.1 --port 8080 -c 8192 --jinja --chat-template-kwargs '{"enable_thinking":false}'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now artemis-llama.service
if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
  diagnostics
  fail "$SERVICE_NAME is not active."
fi
verify_health
printf 'llama-server is running at http://127.0.0.1:8080 and will start on boot.\n'
