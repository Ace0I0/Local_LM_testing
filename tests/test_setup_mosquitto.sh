#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WIZARD="$REPO_ROOT/scripts/setup_mosquitto.sh"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_contains() {
  local file="$1" expected="$2"
  grep -Fq -- "$expected" "$file" || fail "$file does not contain: $expected"
}

assert_not_contains() {
  local file="$1" unexpected="$2"
  if grep -Fq -- "$unexpected" "$file"; then
    fail "$file contains secret text: $unexpected"
  fi
}

assert_mode() {
  local file="$1" expected="$2" actual
  actual=$(stat -c '%a' "$file")
  [[ "$actual" == "$expected" ]] || fail "$file mode is $actual, expected $expected"
}

write_fake_commands() {
  local fake_bin="$1"

  mkdir -p "$fake_bin"

  cat > "$fake_bin/sudo" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n) shift ;;
    -u) shift 2 ;;
    *) break ;;
  esac
done
printf 'sudo %s\n' "$1" >> "$FAKE_ROOT/commands.log"
exec "$@"
EOF

  cat > "$fake_bin/uname" <<'EOF'
#!/usr/bin/env bash
[[ "${1:-}" == "-m" ]] && { printf 'aarch64\n'; exit 0; }
exec /usr/bin/uname "$@"
EOF

  cat > "$fake_bin/apt-get" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'apt-get %s\n' "$*" >> "$FAKE_ROOT/commands.log"
[[ "${FAKE_APT_FAIL:-0}" != "1" ]]
EOF

  cat > "$fake_bin/mosquitto" <<'EOF'
#!/usr/bin/env bash
printf 'mosquitto version 2.0.21\n'
exit 1
EOF

  cat > "$fake_bin/mosquitto_passwd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "-c" ]]; then
  password_file="$2"
  user="$3"
  mode=create
else
  password_file="$1"
  user="$2"
  mode=add
fi
mkdir -p "$(dirname "$password_file")"
if [[ "$mode" == create ]]; then
  printf '%s:hashed-password\n' "$user" > "$password_file"
else
  printf '%s:hashed-password\n' "$user" >> "$password_file"
fi
printf 'mosquitto_passwd %s %s\n' "$mode" "$user" >> "$FAKE_ROOT/commands.log"
EOF

  cat > "$fake_bin/install" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mode=755
args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|-g) shift 2 ;;
    -m) mode="$2"; shift 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
[[ ${#args[@]} -eq 2 ]]
/usr/bin/install -m "$mode" "${args[0]}" "${args[1]}"
printf 'install %s %s\n' "$mode" "${args[1]}" >> "$FAKE_ROOT/commands.log"
EOF

  cat > "$fake_bin/chown" <<'EOF'
#!/usr/bin/env bash
printf 'chown %s\n' "$*" >> "$FAKE_ROOT/commands.log"
EOF

  cat > "$fake_bin/chmod" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'chmod %s\n' "$*" >> "$FAKE_ROOT/commands.log"
exec /usr/bin/chmod "$@"
EOF

  cat > "$fake_bin/systemctl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'systemctl %s\n' "$*" >> "$FAKE_ROOT/commands.log"
case "$1" in
  enable) exit 0 ;;
  restart)
    count_file="$FAKE_ROOT/restart-count"
    count=0
    [[ -f "$count_file" ]] && count=$(<"$count_file")
    printf '%s\n' "$((count + 1))" > "$count_file"
    [[ "${FAKE_SYSTEMCTL_FAIL_RESTART:-0}" != "1" ]]
    ;;
  is-active) printf 'active\n' ;;
  status) printf 'fake mosquitto status\n' ;;
  *) exit 0 ;;
esac
EOF

  cat > "$fake_bin/journalctl" <<'EOF'
#!/usr/bin/env bash
printf 'journalctl %s\n' "$*" >> "$FAKE_ROOT/commands.log"
printf 'fake mosquitto journal\n'
EOF

  cat > "$fake_bin/hostname" <<'EOF'
#!/usr/bin/env bash
[[ "${1:-}" == "-I" ]] && { printf '192.168.0.44 \n'; exit 0; }
printf 'RP\n'
EOF

  cat > "$fake_bin/mosquitto_pub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
valid_credentials() {
  case "$1:$2" in
    artemis_test:test-password|esphome_living_room:sensor-password|homeassistant:ha-password|artemis:artemis-password) return 0 ;;
    *) return 1 ;;
  esac
}

can_write() {
  case "$1:$2" in
    artemis_test:artemis/test/*) return 0 ;;
    esphome_living_room:artemis/sensors/living_room/sensor/temperature/state|\
    esphome_living_room:artemis/sensors/living_room/sensor/humidity/state|\
    esphome_living_room:artemis/sensors/living_room/status|\
    esphome_living_room:homeassistant/*/living_room/*|\
    homeassistant:homeassistant/status) return 0 ;;
    *) return 1 ;;
  esac
}

host='' topic='' message='' user='' password='' qos='' retain=0 version=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h) host="$2"; shift 2 ;;
    -t) topic="$2"; shift 2 ;;
    -m) message="$2"; shift 2 ;;
    -u) user="$2"; shift 2 ;;
    -P) password="$2"; shift 2 ;;
    -q) qos="$2"; shift 2 ;;
    -V) version="$2"; shift 2 ;;
    -r) retain=1; shift ;;
    *) shift ;;
  esac
done
printf 'pub host=%s topic=%s user=%s qos=%s retain=%s version=%s\n' \
  "$host" "$topic" "${user:-anonymous}" "$qos" "$retain" "$version" >> "$FAKE_ROOT/commands.log"
valid_credentials "$user" "$password" || { printf 'Not authorized\n' >&2; exit 5; }
if ! can_write "$user" "$topic" && [[ "${FAKE_ALLOW_FORBIDDEN:-0}" != "1" ]]; then
  printf 'Warning: Publish 1 failed: Not authorized.\n' >&2
  exit 0
fi
[[ "$qos" == "1" && "$retain" == "1" && "$version" == "mqttv5" ]]
mkdir -p "$FAKE_ROOT/retained"
printf '%s\n%s\n' "$topic" "$message" > "$FAKE_ROOT/retained/${topic//\//__}"
EOF

  cat > "$fake_bin/mosquitto_sub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
valid_credentials() {
  case "$1:$2" in
    artemis_test:test-password|esphome_living_room:sensor-password|homeassistant:ha-password|artemis:artemis-password) return 0 ;;
    *) return 1 ;;
  esac
}

can_read() {
  case "$1:$2" in
    artemis_test:artemis/test/*|\
    esphome_living_room:homeassistant/status|\
    homeassistant:artemis/sensors/*/sensor/temperature/state|\
    homeassistant:artemis/sensors/*/sensor/humidity/state|\
    homeassistant:artemis/sensors/*/status|\
    homeassistant:homeassistant/*|\
    artemis:artemis/sensors/*/sensor/temperature/state|\
    artemis:artemis/sensors/*/sensor/humidity/state|\
    artemis:artemis/sensors/*/status) return 0 ;;
    *) return 1 ;;
  esac
}

host='' topic='' user='' password='' count='' timeout='' qos='' version='' verbose=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h) host="$2"; shift 2 ;;
    -t) topic="$2"; shift 2 ;;
    -u) user="$2"; shift 2 ;;
    -P) password="$2"; shift 2 ;;
    -C) count="$2"; shift 2 ;;
    -W) timeout="$2"; shift 2 ;;
    -q) qos="$2"; shift 2 ;;
    -V) version="$2"; shift 2 ;;
    -v) verbose=1; shift ;;
    *) shift ;;
  esac
done
printf 'sub host=%s topic=%s user=%s count=%s timeout=%s qos=%s version=%s\n' \
  "$host" "$topic" "${user:-anonymous}" "$count" "$timeout" "$qos" "$version" >> "$FAKE_ROOT/commands.log"
valid_credentials "$user" "$password" || { printf 'Not authorized\n' >&2; exit 5; }
can_read "$user" "$topic" || { printf 'Not authorized\n' >&2; exit 5; }
[[ "$count" == "1" && -n "$timeout" && "$qos" == "1" && "$version" == "mqttv5" && "$verbose" == "1" ]]
mapfile -t retained < "$FAKE_ROOT/retained/${topic//\//__}"
printf '%s %s\n' "${retained[0]}" "${retained[1]}"
EOF

  chmod +x "$fake_bin"/*
}

run_wizard() {
  local root="$1" input="$2" output="$3"
  shift 3
  mkdir -p "$root/etc/mosquitto/conf.d"
  printf 'ID=debian\nVERSION_ID="13"\n' > "$root/os-release"
  : > "$root/commands.log"
  write_fake_commands "$root/bin"
  printf '%s' "$input" | env \
    PATH="$root/bin:$PATH" \
    FAKE_ROOT="$root" \
    ARTEMIS_OS_RELEASE="$root/os-release" \
    ARTEMIS_MOSQUITTO_ETC_DIR="$root/etc/mosquitto" \
    "$@" \
    bash "$WIZARD" > "$output" 2>&1
}

[[ -f "$WIZARD" ]] || fail "$WIZARD is missing"
bash -n "$WIZARD"

TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

success_root="$TEST_ROOT/success"
mkdir -p "$success_root"
run_wizard "$success_root" $'\ny\ntest-password\nsensor-password\nha-password\nartemis-password\n' "$success_root/output"

config="$success_root/etc/mosquitto/conf.d/artemis.conf"
acl="$success_root/etc/mosquitto/artemis.acl"
passwd="$success_root/etc/mosquitto/artemis.passwd"

assert_contains "$config" 'listener 1883'
assert_contains "$config" 'allow_anonymous false'
assert_contains "$config" "password_file $passwd"
assert_contains "$config" "acl_file $acl"
assert_contains "$acl" 'user artemis_test'
assert_contains "$acl" 'topic readwrite artemis/test/#'
assert_contains "$acl" 'user esphome_living_room'
assert_contains "$acl" 'topic write artemis/sensors/living_room/sensor/temperature/state'
assert_contains "$acl" 'topic write artemis/sensors/living_room/sensor/humidity/state'
assert_contains "$acl" 'topic write artemis/sensors/living_room/status'
assert_contains "$acl" 'topic write homeassistant/+/living_room/#'
assert_contains "$acl" 'topic read homeassistant/status'
assert_contains "$acl" 'user homeassistant'
assert_contains "$acl" 'topic read artemis/sensors/+/sensor/temperature/state'
assert_contains "$acl" 'topic read artemis/sensors/+/sensor/humidity/state'
assert_contains "$acl" 'topic read artemis/sensors/+/status'
assert_contains "$acl" 'topic read homeassistant/#'
assert_contains "$acl" 'topic write homeassistant/status'
assert_contains "$acl" 'user artemis'
assert_contains "$passwd" 'artemis_test:hashed-password'
assert_contains "$passwd" 'esphome_living_room:hashed-password'
assert_contains "$passwd" 'homeassistant:hashed-password'
assert_contains "$passwd" 'artemis:hashed-password'
assert_mode "$config" 644
assert_mode "$acl" 640
assert_mode "$passwd" 640
[[ "$(<"$success_root/restart-count")" == "2" ]] || fail 'expected two broker restarts'
assert_contains "$success_root/commands.log" 'apt-get update'
assert_contains "$success_root/commands.log" 'apt-get install -y mosquitto mosquitto-clients'
assert_contains "$success_root/commands.log" 'sub host=127.0.0.1 topic=artemis/test/climate user=anonymous'
assert_contains "$success_root/commands.log" 'pub host=127.0.0.1 topic=artemis/forbidden user=artemis_test'
assert_contains "$success_root/commands.log" 'sub host=192.168.0.44 topic=artemis/test/climate user=artemis_test'
assert_contains "$success_root/commands.log" 'pub host=127.0.0.1 topic=artemis/sensors/living_room/sensor/temperature/state user=esphome_living_room'
assert_contains "$success_root/commands.log" 'sub host=127.0.0.1 topic=artemis/sensors/living_room/sensor/temperature/state user=homeassistant'
assert_contains "$success_root/commands.log" 'sub host=127.0.0.1 topic=artemis/sensors/living_room/status user=artemis'
assert_contains "$success_root/commands.log" 'pub host=127.0.0.1 topic=homeassistant/status user=homeassistant'
assert_contains "$success_root/commands.log" 'sub host=127.0.0.1 topic=homeassistant/status user=esphome_living_room'
assert_contains "$success_root/commands.log" 'pub host=127.0.0.1 topic=artemis/sensors/bedroom/status user=esphome_living_room'
assert_contains "$success_root/commands.log" 'pub host=127.0.0.1 topic=artemis/sensors/living_room/status user=homeassistant'
assert_contains "$success_root/commands.log" 'pub host=127.0.0.1 topic=artemis/sensors/living_room/status user=artemis'
assert_contains "$success_root/output" 'Setup complete'
for secret in test-password sensor-password ha-password artemis-password; do
  assert_not_contains "$success_root/output" "$secret"
  assert_not_contains "$success_root/commands.log" "$secret"
done

preserve_root="$TEST_ROOT/preserve"
mkdir -p "$preserve_root/etc/mosquitto"
printf 'legacy_user:existing-hash\nartemis_test:original-test-hash\n' > "$preserve_root/etc/mosquitto/artemis.passwd"
run_wizard "$preserve_root" $'\ny\ntest-password\nsensor-password\nha-password\nartemis-password\n' "$preserve_root/output"
assert_contains "$preserve_root/etc/mosquitto/artemis.passwd" 'legacy_user:existing-hash'
assert_contains "$preserve_root/etc/mosquitto/artemis.passwd" 'artemis_test:original-test-hash'
assert_contains "$preserve_root/etc/mosquitto/artemis.passwd" 'esphome_living_room:hashed-password'
assert_contains "$preserve_root/etc/mosquitto/artemis.passwd" 'homeassistant:hashed-password'
assert_contains "$preserve_root/etc/mosquitto/artemis.passwd" 'artemis:hashed-password'
assert_not_contains "$preserve_root/commands.log" 'mosquitto_passwd add artemis_test'

apt_failure_root="$TEST_ROOT/apt-failure"
mkdir -p "$apt_failure_root"
if run_wizard "$apt_failure_root" $'\ny\n' "$apt_failure_root/output" FAKE_APT_FAIL=1; then
  fail 'wizard succeeded when apt-get failed'
fi
[[ ! -e "$apt_failure_root/etc/mosquitto/conf.d/artemis.conf" ]] || fail 'configuration written after apt failure'

service_failure_root="$TEST_ROOT/service-failure"
mkdir -p "$service_failure_root"
if run_wizard "$service_failure_root" $'\ny\n' "$service_failure_root/output" FAKE_SYSTEMCTL_FAIL_RESTART=1; then
  fail 'wizard succeeded when mosquitto restart failed'
fi
assert_contains "$service_failure_root/output" 'Mosquitto failed to start'
assert_contains "$service_failure_root/commands.log" 'journalctl -u mosquitto.service -n 50 --no-pager'

acl_failure_root="$TEST_ROOT/acl-failure"
mkdir -p "$acl_failure_root"
if run_wizard "$acl_failure_root" $'\ny\ntest-password\nsensor-password\nha-password\nartemis-password\n' "$acl_failure_root/output" FAKE_ALLOW_FORBIDDEN=1; then
  fail 'wizard succeeded when the broker accepted an out-of-ACL publish'
fi
assert_contains "$acl_failure_root/output" 'The broker allowed the test account to publish outside artemis/test/#'

printf 'PASS: Mosquitto setup wizard behavior\n'
