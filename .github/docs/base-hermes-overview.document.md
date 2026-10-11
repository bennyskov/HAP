# **1. BASE Hermes Overview**

## **1.1 Purpose**

This document tracks the current state of the `BASE`-level Hermes runtime (macOS, Homebrew, and the Hermes agent itself) so maintenance runs have a quick reference point instead of re-discovering the environment each time.

## **1.2 Runtime Snapshot**

Updated by the `hap-maintenance` skill's "Documentation and Cleanup" step. Reflects the most recent maintenance pass.

- Last updated: 2026-10-11
- Hermes Agent version: v0.21.6+509.gf925b01 (local `f925b01791fe`, stable update channel; no newer stable update available)
- Install method: git, at `~/.hermes/hermes-agent`
- Python: 3.14.7
- Config version: v50 (migrated during the 2026-10-10 update)
- Active local model: `qwen2.5-coder:7b` (Ollama)
- Gateway manager: `launchd`
- Provider connectivity: Ollama reachable at `http://localhost:11434`
- Ollama: 0.40.3 (Homebrew service, restarted after upgrade)
- Docker Desktop: 4.94.0, no cask update pending
- Latest maintenance: Homebrew upgraded `ollama` 0.40.2 → 0.40.3 and `sqlite` 3.53.4 → 3.54.0; nothing outdated afterward. Hermes already up to date; cache cleanup and gateway restart completed, with launchd reporting the gateway running. The active model pull succeeded; the read-only Ollama `/api/tags` check returned 200. External provider APIs were not tested.
- Shell activation: the zsh hook activates the HAP venv on `cd`; no `python`/`python3` aliases override it.

## **1.3 Key Commands**

- `hermes --version` — check installed version and update status
- `hermes status` — full runtime, API key, and service status
- `hermes doctor` — deeper diagnostics (env, config, SSL, packages)
- `hermes update` — pull latest code and sync skills/config
- `hermes gateway restart` — restart the background gateway service

## **1.4 Known Quirks**

- After `hermes update`, a stale "gateways may still be serving pre-update modules" warning can persist in `hermes status` output even after a successful `hermes gateway restart` with a new PID. `hermes doctor` reporting "Version files consistent" is the reliable signal that the update actually applied; treat the warning as cosmetic unless doctor also flags a version mismatch.
- The `~/.zshrc` auto-activate hook for the HAP project venv must not `source .venv/bin/activate` directly: that script depends on `$BASH_SOURCE`, which this machine's zsh (5.9) does not populate, so sourcing it resolves `VIRTUAL_ENV` to the parent of the current directory instead of the venv path (silently breaking `PATH`/`VIRTUAL_ENV`). The hook now sets `VIRTUAL_ENV`/`PATH`/`_OLD_VIRTUAL_PATH` directly instead of sourcing the bash-only script. The hook also previously pointed at a stale `~/Projects/hermes-agent-project` directory and was repointed to `~/Projects/HAP`.
- `brew upgrade --cask docker-desktop` fails partway through because removing `/Library/PrivilegedHelperTools/com.docker.*` requires `sudo`, and this machine has no passwordless-sudo rule or Touch ID sudo configured, so it cannot complete non-interactively (from an agent, script, or cron).
  - **Fix applied**: enabled `autoDownloadUpdates` in `~/Library/Group Containers/group.com.docker/settings.json` so Docker Desktop pre-downloads new versions itself. You still need to click "Update" once via the Docker Desktop GUI (or `Docker menu > Check for Updates`) when it's running, which uses Docker's own privileged-helper auth (a normal macOS password/Touch ID dialog) instead of Homebrew/sudo.
  - **Maintenance handoff**: Docker Desktop was current (4.94.0) at the 2026-10-11 check. When it is outdated again, run `sudo -v && brew upgrade --cask docker-desktop` in a user-controlled interactive terminal and enter the password only at the sudo prompt. Verify afterward with `brew outdated --cask docker-desktop`; maintenance does not create passwordless sudo rules or assume authorization transfers between terminals.

## **1.5 Maintenance Cadence**

Run `/hap-maintenance` periodically to keep Homebrew packages, Hermes, and the active Ollama model current, clear stale Python bytecode caches, and re-validate the shell/`.venv` environment. The default invocation runs BASE maintenance; use `hap` or `all` to include framework alignment and the Copilot customization standard check.

Use `hap-daily-routine` as the entry point for the recurring cross-project pass: it sequences a cheap daily status/drift check (git status across HAP/BUD/STRM, `hap-copilot-standard-check`, `hap-maintenance check`) and a heavier periodic pass (`hap-maintenance`, `hap-propagate-standard` when drift is found, and committing/pushing each repo) without duplicating any of their logic.
