---
name: hap-maintenance
description: Use this skill for repeatable maintenance of the HAP development workspace on macOS.
---

# **1. Skill Instructions**

## **1.1 Purpose**
Use this skill for repeatable maintenance of the HAP development workspace on macOS. This includes both `BASE` level tasks (system, runtime) and `HAP` level tasks (project structure, conventions).

## **1.2 Scope Boundary**
- **BASE**: Covers macOS, Homebrew, and HAP runtime maintenance. Use this for updating software, verifying runtime health, and validating shell/.venv behavior.
- **HAP**: Covers HAP framework alignment across projects. Use this for maintaining shared structure, reusable tools, common definitions, and documentation patterns.
- This skill does **not** cover domain-specific business logic for individual projects.

## **1.3 Use When**
- Updating hermes and Homebrew packages.
- Verifying shell environment loading and `.venv` activation.
- Validating provider API connectivity after environment changes.
- Reviewing whether shared files, names, and conventions are aligned across projects.
- Creating or refining reusable framework helpers, templates, or definitions.
- Standardizing how projects organize config, docs, scripts, and shared assets.
- Auditing framework-level docs, legacy prompts, or skills for consistency.
- Updating maintenance documentation after performing tasks.

## **1.4 Prerequisites**
Before running any terminal commands in this skill, **activate the project `.venv`**:
```bash
source /Users/bennyskov/Projects/HAP/.venv/bin/activate
```
**Why:** This prevents Python bytecode version conflicts and ensures correct package imports.

## **1.5 Invocation Modes**

The skill can be invoked with a short natural-language qualifier; no special command parser is required.

- **No qualifier or `update`**: Run the `BASE` update and verification flow in section 1.6.1. Do not substitute a read-only Copilot-layout check for maintenance.
- **`check`**: Run read-only environment and runtime checks only. Do not update software, caches, models, or services.
- **`hap`**: Review HAP framework alignment. Use a named asset or convention when provided; run the Copilot standard check when reviewing Copilot guidance.
- **`all`**: Run both the `BASE` update flow and HAP framework alignment. If no HAP asset is specified, check the Copilot standard and report the scope used.

Report every step that could not be completed and why; do not imply a failed or skipped update succeeded.

## **1.6 Standard Maintenance Flow**

### **1.6.1 BASE: System and Runtime Maintenance**
- **Update Tooling**:
  - `brew update && brew upgrade`
  - If a cask upgrade requires administrator authentication, follow section 1.8.3. Continue independent maintenance steps and report the blocked upgrade as pending.
  - `hermes update`
- **Clear Caches**:
  - Clear stale Python bytecode, especially after updates, to prevent import errors.
  - `find ~/.hermes/hermes-agent -type f -name "*.pyc" -delete 2>/dev/null`
  - `find ~/.hermes/hermes-agent -depth -type d -name "__pycache__" -empty -delete 2>/dev/null`
- **Update Models**:
  - Pull the active local Ollama model (use `hermes status | awk '/  Model:/{print; exit}'` to check the model name without printing credential status).
  - `ollama pull qwen2.5-coder:7b`
- **Verify Runtime**:
  - `hermes --version`
  - `hermes gateway restart`
  - `hermes status --full | awk '/◆ Environment/{show=1} /◆ API Keys/{show=0} /◆ Gateway Service/{show=1} /◆ Scheduled Jobs/{show=0} show'` (plain `hermes status` now prints a condensed summary that omits the `◆`-prefixed sections; use `--full` to filter them)
- **Validate Environment**:
  - Confirm `~/.zshrc` sources `$HOME/.config/hermes/env.zsh`.
  - Ensure project `.venv` auto-activates correctly.
- **Validate APIs**:
  - Use non-destructive, read-only endpoints to check provider connectivity (e.g., list models).

### **1.6.2 HAP: Framework Alignment**
- **Identify Asset**: Pinpoint the framework asset, pattern, or convention to review.
- **Check Scope**: Confirm if it's shared across multiple projects or local to one.
- **Verify Consistency**: Check if naming, placement, and responsibility align with `HAP` standards.
- **Review Dependencies**: Ensure related docs, legacy prompts, and skills reference the current structure.
- **Standardize**: Refactor duplicated logic or inconsistent patterns into a shared, standardized form.
- **Check Copilot Standard**: Run the `hap-copilot-standard-check` skill to verify the documented HAP Copilot layout is still upheld and still matches the current upstream VS Code customization spec (instructions, skills, custom agents, legacy prompts, and legacy chat modes). Flag stale file names, missing files, and outdated format references; fix them if confirmed.

### **1.6.3 Documentation and Cleanup**
- **Sync API Keys**: If keys changed, update `config/KEYS.md` to match `~/.config/hermes/env.zsh`. Never commit this file — it must stay in `.gitignore`.
- **Update Docs**: Add concise updates to `.github/docs/base-hermes-overview.document.md` and other relevant framework documents.

## **1.7 Safety Rules**
- Never print secret values in logs or docs.
- Use read-only endpoint checks for API validation.
- Always run within the activated project `.venv`.
- Keep framework changes minimal and ensure they are easy for other projects to adopt.
- Preserve clear boundaries between `BASE`, `HAP`, and project-specific layers.

## **1.8 Troubleshooting**

### **1.8.1 Import errors like "cannot import name 'env_float' from 'utils'"**
**Cause:** Stale Python bytecode cache, often from mismatched Python versions.
**Solution:** Clear all bytecode and compiled cache as shown in the `BASE` maintenance flow for HAP.

```bash
# Also clear any site-packages cache
find ~/.hermes/hermes-agent/venv -name "*.pyc" -delete 2>/dev/null

# Verify with any hermes command
hermes --version
```

**Prevention:**
- The maintenance skill includes cache clearing in the BASE maintenance flow.
- Avoid running `python3` directly in the hermes directory; use `hermes` command or call the venv Python: `.hermes/hermes-agent/venv/bin/python`
- Avoid setting `PYTHONPATH` to include the hermes directory, as it can cause version conflicts.
- Always activate the project `.venv` before running Python-dependent commands in terminal.

### **1.8.2 Gateway fails to restart**
**Cause:** PID mismatch or launchd state on macOS.

**Check:** `launchctl list | grep hermes` to see service status.

**Fix:** Restart manually:
```bash
hermes gateway stop
sleep 2
hermes gateway start
hermes status --full | awk '/◆ Gateway Service/{show=1; next} /◆ Scheduled Jobs/{show=0} show'
```

### **1.8.3 Docker Desktop upgrade requires administrator authentication**
**Cause:** Homebrew needs administrator permission to replace Docker Desktop's privileged helpers, but the agent command runner cannot securely prompt for a sudo password.

**Interactive task:** In VS Code, launch the existing `HAP: Upgrade Docker Desktop` task from `.vscode/tasks.json` using the task-running tool. It opens and focuses a visible terminal, activates the project venv, requests sudo authentication, upgrades Docker, and checks for a remaining update. Tell the user to enter their Mac login password at that terminal's `Password:` prompt. Use the task-output tool to check completion, then independently verify the installed cask state. Do not launch a second copy while the task is awaiting input.

**Fallback:** Only if an interactive task tool is unavailable, tell the user to run this in their own interactive VS Code terminal or macOS Terminal:
```bash
source /Users/bennyskov/Projects/HAP/.venv/bin/activate
sudo -v && brew upgrade --cask docker-desktop
brew outdated --cask docker-desktop
```

- Enter the Mac login password only at the terminal's sudo prompt, never in chat. Password characters are not displayed.
- The upgrade starts immediately after authentication. Sudo authorization is temporary and may be terminal-specific; do not assume authentication in the user's terminal authorizes the agent command runner.
- Let sudo handle its own password timeout and retry policy. If authentication times out or the user cancels, report the upgrade as pending rather than retrying automatically.
- Do not create passwordless sudo rules, run Homebrew itself with sudo, or collect passwords using chat, scripts, or command arguments.
- Do not repeatedly retry an upgrade blocked on authentication. Keep it pending until successful completion is verified.
- After the user completes the command, verify with `brew outdated --cask docker-desktop`. An empty result with a successful exit status means no newer cask version is pending; command failure does not count as verification.

## **1.9 Outputs**
- Command summary.
- Software versions changed and any upgrades still pending, including administrator-authentication handoffs.
- Pass/fail status for environment, venv, and API checks.
- Updated overview notes when applicable.
