# **1. BASE Hermes Overview**

## **1.1 Purpose**

This document tracks the current state of the `BASE`-level Hermes runtime (macOS, Homebrew, and the Hermes agent itself) so maintenance runs have a quick reference point instead of re-discovering the environment each time.

## **1.2 Runtime Snapshot**

Updated by the `hap-maintenance` skill's "Documentation and Cleanup" step. Reflects the most recent maintenance pass.

- Last updated: 2026-09-05
- Hermes Agent version: v0.21.0 (upstream `d20a8e44`)
- Install method: git, at `~/.hermes/hermes-agent`
- Python: 3.11.15
- Active local model: `qwen2.5-coder:7b` (Ollama)
- Gateway manager: `launchd`
- Provider connectivity: Ollama reachable at `http://localhost:11434`

## **1.3 Key Commands**

- `hermes --version` — check installed version and update status
- `hermes status` — full runtime, API key, and service status
- `hermes doctor` — deeper diagnostics (env, config, SSL, packages)
- `hermes update` — pull latest code and sync skills/config
- `hermes gateway restart` — restart the background gateway service

## **1.4 Known Quirks**

- After `hermes update`, a stale "gateways may still be serving pre-update modules" warning can persist in `hermes status` output even after a successful `hermes gateway restart` with a new PID. `hermes doctor` reporting "Version files consistent" is the reliable signal that the update actually applied; treat the warning as cosmetic unless doctor also flags a version mismatch.
- `brew upgrade --cask docker-desktop` fails partway through because removing `/Library/PrivilegedHelperTools/com.docker.*` requires `sudo`, and this machine has no passwordless-sudo rule or Touch ID sudo configured, so it cannot complete non-interactively (from an agent, script, or cron).
  - **Fix applied**: enabled `autoDownloadUpdates` in `~/Library/Group Containers/group.com.docker/settings.json` so Docker Desktop pre-downloads new versions itself. You still need to click "Update" once via the Docker Desktop GUI (or `Docker menu > Check for Updates`) when it's running, which uses Docker's own privileged-helper auth (a normal macOS password/Touch ID dialog) instead of Homebrew/sudo.
  - **Optional, not applied**: add a narrowly-scoped sudoers rule (e.g. via `sudo visudo -f /etc/sudoers.d/homebrew-docker-desktop`) granting passwordless root for the specific `rm`/`launchctl` commands the docker-desktop cask needs, so `brew upgrade --cask docker-desktop` never prompts. This is a standing security change (passwordless root for those commands, for this user) and should only be done deliberately, not as routine maintenance.

## **1.5 Maintenance Cadence**

Run `/hap-maintenance` periodically to keep Homebrew packages, Hermes, and the active Ollama model current, clear stale Python bytecode caches, and re-validate the shell/`.venv` environment. The HAP framework alignment step also runs `hap-copilot-standard-check` to catch drift in the Copilot customization layout.
