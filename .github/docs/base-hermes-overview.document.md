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
- `brew upgrade --cask docker-desktop` can fail partway through if it needs `sudo` to remove a privileged helper tool (`com.docker.socket`). This requires an interactive terminal with a password prompt — it cannot be completed non-interactively. Run it manually when needed.

## **1.5 Maintenance Cadence**

Run `/hap-maintenance` periodically to keep Homebrew packages, Hermes, and the active Ollama model current, clear stale Python bytecode caches, and re-validate the shell/`.venv` environment. The HAP framework alignment step also runs `hap-copilot-standard-check` to catch drift in the Copilot customization layout.
