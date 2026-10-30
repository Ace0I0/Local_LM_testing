#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WIZARD="$REPO_ROOT/scripts/setup_llama_server.sh"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_contains() {
  grep -Fq -- "$2" "$1" || fail "$1 does not contain: $2"
}

[[ -x "$WIZARD" ]] || fail "missing executable installer: $WIZARD"
bash -n "$WIZARD"

assert_contains "$WIZARD" '/etc/artemis/llama-server.env'
assert_contains "$WIZARD" '/etc/systemd/system/artemis-llama.service'
assert_contains "$WIZARD" 'User=$LLAMA_SERVICE_USER'
assert_contains "$WIZARD" '--host 127.0.0.1'
assert_contains "$WIZARD" 'Restart=on-failure'
assert_contains "$WIZARD" 'systemctl daemon-reload'
assert_contains "$WIZARD" 'systemctl enable --now artemis-llama.service'
assert_contains "$WIZARD" 'http://127.0.0.1:8080/health'
