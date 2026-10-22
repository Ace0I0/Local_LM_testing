# Mosquitto First Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable SSH wizard that installs and verifies a password-protected Mosquitto broker on the Raspberry Pi.

**Architecture:** A single Bash wizard based on the repository's wizard template owns the host preflight, Debian package installation, Artemis-specific Mosquitto files, service restart, and live MQTT acceptance checks. A small dependency-free shell contract test validates the wizard locally, while the README provides the Pi handoff.

**Tech Stack:** Bash, Debian 13, apt, systemd, Mosquitto 2.0.x, `mosquitto_pub`, `mosquitto_sub`

**Spec:** `docs/superpowers/specs/2026-10-22-mosquitto-first-slice-design.md`

## Global Constraints

- Target Debian 13.2 on ARM64 with `apt`, systemd, and passwordless `sudo`.
- Install only `mosquitto` and `mosquitto-clients`; verify the installed version at runtime.
- Keep `/etc/mosquitto/mosquitto.conf` unchanged.
- Own only `/etc/mosquitto/conf.d/artemis.conf`, `/etc/mosquitto/artemis.passwd`, and `/etc/mosquitto/artemis.acl`.
- Listen on TCP port `1883`, reject anonymous clients, and do not add TLS on the trusted LAN.
- Create `artemis_test` with read/write access only to `artemis/test/#`.
- Test `artemis/test/climate` with retained QoS 1 payload `{"temperature_c": 21.5, "humidity_pct": 45.0}`.
- Never persist or log the plaintext broker password.
- Do not change Python, ESPHome, Home Assistant, LLM, or permanent MQTT-contract code.

## Review Focus

- Rerunning the wizard must replace only the three Artemis-owned files and leave unrelated Mosquitto configuration untouched; the contract test pins all writable paths.
- A package-install failure must occur before configuration writes; the contract test pins the stage order and `set -euo pipefail` remains active.
- A wrong password must fail the smoke test with a clear message rather than weakening authentication; the live test captures each client command's result.
- The ACL must reject authenticated publication outside `artemis/test/#`; the live test attempts a forbidden publication.
- A host without a usable LAN IPv4 address must stop with an actionable message after localhost checks; the wizard validates the selected address before the LAN test.

---

### Task 1: Interactive broker setup and acceptance wizard

**Files:**
- Create: `scripts/setup_mosquitto.sh`
- Create: `tests/test_setup_mosquitto.sh`

**Interfaces:**
- Consumes: `/home/ace/.agents/skills/wizard/template.sh`; Debian `apt-get`, `systemctl`, `mosquitto_passwd`, `mosquitto_pub`, `mosquitto_sub`, `hostname`, and `journalctl`.
- Produces: executable `scripts/setup_mosquitto.sh`; Artemis-owned broker files; a running `mosquitto.service`; exit status `0` only after all acceptance checks pass.

- [ ] **Step 1: Write the failing shell contract test**

Create `tests/test_setup_mosquitto.sh` with `set -euo pipefail` and an `assert_contains` helper. It must run `bash -n` on the wizard and assert that the source contains the three exact owned paths, `allow_anonymous false`, `artemis_test`, `topic readwrite artemis/test/#`, QoS 1 plus retain publication, one-message subscription with a timeout, an anonymous-rejection check, a forbidden-topic check, two service restarts, and journal diagnostics.

- [ ] **Step 2: Run the contract test and verify it fails because the wizard does not exist**

Run: `bash tests/test_setup_mosquitto.sh`

Expected: non-zero with `scripts/setup_mosquitto.sh` reported missing.

- [ ] **Step 3: Create the wizard from the standard template**

Copy `/home/ace/.agents/skills/wizard/template.sh` to `scripts/setup_mosquitto.sh` without changing anything above its `STAGES` marker. Replace the example with five stages named `Preflight`, `Install packages`, `Configure broker`, `Start service`, and `Verify MQTT`.

Stage behavior:

1. `Preflight` verifies ARM64 Debian with `apt-get`, systemd, and non-interactive `sudo`; prints the detected OS; and asks before privileged work.
2. `Install packages` runs `sudo apt-get update` and installs only `mosquitto mosquitto-clients`, then prints `mosquitto -h` version output.
3. `Configure broker` invokes interactive `sudo mosquitto_passwd -c /etc/mosquitto/artemis.passwd artemis_test`; writes the exact listener and ACL content through temporary files; installs the config as `root:root` mode `0644` and the ACL as `root:mosquitto` mode `0640`; sets the password file to `root:mosquitto` mode `0640`; and verifies the `mosquitto` user can read both protected files.
4. `Start service` enables and restarts `mosquitto.service`, requires it to be active, and prints full status plus the last 50 journal lines before exiting if startup fails.
5. `Verify MQTT` captures the password with hidden input; uses MQTT 5 so authorization failures are observable; publishes and reads back the exact retained QoS 1 payload through localhost; requires anonymous subscribe and authenticated out-of-ACL publish to fail; restarts the service; reads back the retained payload again; repeats authenticated publish/subscribe through the first non-loopback IPv4 address; then unsets the password.

Do not use `mosquitto_passwd -b`, `write_env`, or any plaintext password file. Every failed assertion must name the failed check and exit non-zero without deleting broker files.

- [ ] **Step 4: Make both shell files executable**

Run: `chmod +x scripts/setup_mosquitto.sh tests/test_setup_mosquitto.sh`

Expected: `test -x` succeeds for both paths.

- [ ] **Step 5: Run local static verification**

Run: `bash tests/test_setup_mosquitto.sh`

Expected: PASS for syntax and every pinned contract value.

Run: `shellcheck scripts/setup_mosquitto.sh tests/test_setup_mosquitto.sh`

Expected: no findings when `shellcheck` is installed; if unavailable, record that omission and rely on `bash -n` plus the contract test.

- [ ] **Step 6: Commit the wizard**

```bash
git add scripts/setup_mosquitto.sh tests/test_setup_mosquitto.sh
git commit -m "Add Mosquitto setup wizard"
```

### Task 2: SSH setup documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `scripts/setup_mosquitto.sh` from Task 1.
- Produces: one documented command and an explanation of the wizard's files, test topic, rerun behavior, and success output.

- [ ] **Step 1: Add the Mosquitto setup section to the README**

Place `## MQTT broker setup` after the existing `## Setup` section. State the Debian 13/ARM64 and trusted-LAN assumptions, instruct the user to run `bash scripts/setup_mosquitto.sh` from an interactive SSH session, list the three `/etc/mosquitto/` files it owns, name `artemis/test/climate`, and state that the permanent sensor contract and production identities remain deferred.

- [ ] **Step 2: Verify the documentation references real artifacts and exact contract values**

Run:

```bash
test -f scripts/setup_mosquitto.sh
rg -n "setup_mosquitto.sh|artemis/test/climate|artemis.conf|artemis.passwd|artemis.acl" README.md
git diff --check
```

Expected: the script exists, every contract term appears in the README, and `git diff --check` is silent.

- [ ] **Step 3: Commit the documentation**

```bash
git add README.md
git commit -m "Document Mosquitto SSH setup"
```

### Task 3: Raspberry Pi acceptance run

**Files:**
- No repository changes expected.

**Interfaces:**
- Consumes: the committed wizard on `project-testing` and an interactive SSH session on hostname `RP`.
- Produces: terminal evidence that all wizard checks pass on the actual Pi.

- [ ] **Step 1: Make `project-testing` available to the Pi**

With user approval, push `project-testing` normally; do not force-push. On the Pi, fetch the branch and switch or fast-forward to it.

- [ ] **Step 2: Run the wizard interactively on the Pi**

Run: `bash scripts/setup_mosquitto.sh`

Expected: all five stages complete and the summary reports an active broker, rejected anonymous/out-of-ACL clients, retained payload survival across restart, and successful access through the Pi's LAN address.

- [ ] **Step 3: Capture final diagnostic state**

Run:

```bash
systemctl is-active mosquitto
systemctl is-enabled mosquitto
ss -ltn | grep ':1883'
```

Expected: `active`, `enabled`, and a TCP listener on port `1883`.
