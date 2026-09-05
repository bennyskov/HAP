---
name: hap-maintenance
description: Use this skill for repeatable maintenance of the HAP development workspace on macOS.
---

# Skill Instructions

## Purpose
Use this skill for repeatable maintenance of the HAP development workspace on macOS. This includes both `BASE` level tasks (system, runtime) and `HAP` level tasks (project structure, conventions).

## Scope Boundary
-- **BASE**: Covers macOS, Homebrew, and HAP runtime maintenance. Use this for updating software, verifying runtime health, and validating shell/.venv behavior.
-- **HAP**: Covers HAP framework alignment across projects. Use this for maintaining shared structure, reusable tools, common definitions, and documentation patterns.
- This skill does **not** cover domain-specific business logic for individual projects.

## Use When
- Updating hermes and Homebrew packages.
- Verifying shell environment loading and `.venv` activation.
- Validating provider API connectivity after environment changes.
- Reviewing whether shared files, names, and conventions are aligned across projects.
- Creating or refining reusable framework helpers, templates, or definitions.
- Standardizing how projects organize config, docs, scripts, and shared assets.
- Auditing framework-level docs, prompts, or skills for consistency.
- Updating maintenance documentation after performing tasks.

## Prerequisites
Before running any terminal commands in this skill, **activate the project `.venv`**:
```bash
source /Users/bennyskov/Projects/HAP/.venv/bin/activate
```
**Why:** This prevents Python bytecode version conflicts and ensures correct package imports.

## Standard Maintenance Flow

### 1. BASE: System and Runtime Maintenance
- **Update Tooling**:
  - `brew update && brew upgrade`
  - `hermes update`
- **Clear Caches**:
  - Clear stale Python bytecode, especially after updates, to prevent import errors.
  - `find ~/.hermes/hermes-agent -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null`
  - `find ~/.hermes/hermes-agent -name "*.pyc" -delete 2>/dev/null`
- **Update Models**:
  - Pull the active local Ollama model (check `hermes status` for the model name).
  - `ollama pull qwen2.5-coder:7b`
- **Verify Runtime**:
  - `hermes --version`
  - `hermes gateway restart`
  - `hermes status`
- **Validate Environment**:
  - Confirm `~/.zshrc` sources `$HOME/.config/hermes/env.zsh`.
  - Ensure project `.venv` auto-activates correctly.
- **Validate APIs**:
  - Use non-destructive, read-only endpoints to check provider connectivity (e.g., list models).

### 2. HAP: Framework Alignment
- **Identify Asset**: Pinpoint the framework asset, pattern, or convention to review.
- **Check Scope**: Confirm if it's shared across multiple projects or local to one.
-- **Verify Consistency**: Check if naming, placement, and responsibility align with `HAP` standards.
- **Review Dependencies**: Ensure related docs, prompts, and skills reference the current structure.
- **Standardize**: Refactor duplicated logic or inconsistent patterns into a shared, standardized form.
- **Check Copilot Standard**: Run the `hap-copilot-standard-check` skill to verify the documented HAP Copilot layout is still upheld and still matches the current upstream VS Code customization spec (instructions, prompts, skills, agents/chat modes). Flag stale file names, missing files, and outdated format references; fix them if confirmed.

### 3. Documentation and Cleanup
- **Sync API Keys**: If keys changed, update `config/KEYS.md` to match `~/.config/hermes/env.zsh`. Never commit this file — it must stay in `.gitignore`.
- **Update Docs**: Add concise updates to `.github/docs/base-hermes-overview.md` and other relevant framework documents.

## Safety Rules
- Never print secret values in logs or docs.
- Use read-only endpoint checks for API validation.
- Always run within the activated project `.venv`.
- Keep framework changes minimal and ensure they are easy for other projects to adopt.
-- Preserve clear boundaries between `BASE`, `HAP`, and project-specific layers.

## Troubleshooting

### Import errors like "cannot import name 'env_float' from 'utils'"
**Cause:** Stale Python bytecode cache, often from mismatched Python versions.
**Solution:** Clear all bytecode and compiled cache as shown in the `BASE` maintenance flow for HAP.

# Also clear any site-packages cache
find ~/.hermes/hermes-agent/venv -name "*.pyc" -delete 2>/dev/null

# Verify with any hermes command
hermes --version
```bash

**Prevention:**
- The maintenance skill now includes cache clearing as part of the standard update flow (step 1.3).
- Avoid running `python3` directly in the hermes directory; use `hermes` command or call the venv Python: `.hermes/hermes-agent/venv/bin/python`
- Avoid setting `PYTHONPATH` to include the hermes directory, as it can cause version conflicts.
- Always activate the project `.venv` before running Python-dependent commands in terminal.

### Gateway fails to restart
**Cause:** PID mismatch or launchd state on macOS.

**Check:** `launchctl list | grep hermes` to see service status.

**Fix:** Restart manually:
```bash
hermes gateway stop
sleep 2
hermes gateway start
hermes status
```

## Outputs
- Command summary.
- Pass/fail status for environment, venv, and API checks.
- Updated overview notes when applicable.
