# llama-server Boot Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the existing local Qwen llama-server start, restart, and survive
Raspberry Pi reboots without exposing its API beyond loopback.

**Architecture:** A repeatable Bash wizard collects the Pi user and the existing
llama.cpp and GGUF paths, writes a root-owned settings file, renders a systemd
unit, enables it, and verifies the local health endpoint. The repository stores
only templates and installer logic; no machine path or secret is committed.

**Tech Stack:** Bash, systemd 257, curl, native llama.cpp llama-server.

**Spec:** `docs/superpowers/specs/2026-10-29-llama-server-service-design.md`

## Global Constraints

- Target Raspberry Pi 5 running Debian 13 with systemd and sudo.
- Bind only to `127.0.0.1:8080`.
- Preserve the Qwen3.5 2B command options: 8192 context, Jinja, and disabled thinking.
- Do not start Artemis, download models, or add MQTT credentials.
- Keep host-specific paths outside Git.

## Review Focus

- A missing executable or model must abort before writing or enabling the service.
- A failed service start must show status and recent journal output.
- The generated unit must use the selected non-root user and loopback host.
- Re-running must replace Artemis-owned files without touching other services.
- A listening process that returns a non-success HTTP response must fail verification.

---

### Task 1: Repeatable llama-server service installer

**Files:**
- Create: `scripts/setup_llama_server.sh`
- Create: `tests/test_setup_llama_server.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing llama-server executable and Qwen GGUF on the Pi.
- Produces: `/etc/artemis/llama-server.env`, `/etc/systemd/system/artemis-llama.service`, and an enabled `artemis-llama.service`.

- [ ] **Step 1: Write the failing shell contract test**

Assert that the installer parses, validates required host paths, writes only
the two Artemis-owned system files, configures `User=`, loopback host,
`Restart=on-failure`, and the existing Qwen command options, invokes
`systemctl daemon-reload enable --now`, and checks the local HTTP endpoint.

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `bash tests/test_setup_llama_server.sh`

Expected: FAIL because `scripts/setup_llama_server.sh` does not exist.

- [ ] **Step 3: Implement the interactive installer**

Copy the wizard template unchanged above its stages marker. The stages collect
public paths, require a non-root service user, create root-owned files under
`/etc/artemis` and `/etc/systemd/system`, reload and enable the unit, then
verify active status plus `http://127.0.0.1:8080/health`. Any failure prints
systemd diagnostics and exits nonzero.

- [ ] **Step 4: Run the contract test to verify it passes**

Run: `bash tests/test_setup_llama_server.sh`

Expected: PASS.

- [ ] **Step 5: Document Pi handoff and commit**

Add the installer invocation, the one-time sudo requirement, service
diagnostic commands, and the loopback-only boundary to the README. Commit the
installer, test, and documentation.
