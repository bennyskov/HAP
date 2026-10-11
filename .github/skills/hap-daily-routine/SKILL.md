---
name: hap-daily-routine
description: Use this skill to run the routine pass that keeps HAP and its subprojects (BUD, STRM, future projects) current, drift-free, and synced to GitHub.
---

# **1. Skill Instructions**

## **1.1 Purpose**

This skill orchestrates the other HAP maintenance skills into a sensible daily/periodic sequence. It does not duplicate their logic — it calls them in the right order and adds the one missing piece: routine git status/commit/push across all project repos.

Repos currently covered: `HAP`, `BUD`, `STRM`. Add new sibling projects to this list as they are bootstrapped via `hap-propagate-standard`.

## **1.2 Why a separate skill**

Each existing skill has a narrow job and should stay that way:

- `hap-maintenance` updates software and checks framework alignment — it does not touch subprojects or git remotes.
- `hap-copilot-standard-check` is read-only verification — it does not fix anything or touch other repos.
- `hap-propagate-standard` pushes shared `.github` files into subprojects — it does not run software updates or commit/push.
- `hap-sync-copied-library` is for repo init, GitHub creation, or recovering a blocked push — it is not meant for routine day-to-day commits.

None of them, individually or combined, cover "is there uncommitted or unpushed work sitting in BUD/STRM right now?" This skill closes that gap and gives a single entry point for "is everything current and in sync today?"

## **1.3 Two tiers**

### **1.3.1 Daily tier (cheap, read-mostly, safe to run every day)**

1. **Git status sweep** — for each repo in **1.1**:

   ```bash
   cd /Users/bennyskov/Projects/<REPO> && git status --short --branch
   ```

   Flag: uncommitted changes, untracked files outside expected ignore patterns, and `ahead`/`behind` counts versus the remote (if one exists).

2. **Standard drift check** — run `hap-copilot-standard-check` against HAP. If HAP's shared/templated files changed since the last propagate, also run it against BUD and STRM to see whether they've drifted out of sync.
3. **Runtime check** — run `hap-maintenance check` (read-only: `hermes status`, venv activation, API connectivity). Do not run the `update` flow in the daily tier.
4. **Workspace status dashboard** — always regenerate the HTML dashboard as the last check, so it reflects the current state:

   ```bash
   source /Users/bennyskov/Projects/HAP/.venv/bin/activate
   python3 /Users/bennyskov/Projects/HAP/src/status_report.py
   ```

   This writes `logs/status-report.html` (git-ignored; see `hap-maintenance` section 1.6.4). Do not skip this step, even when the other checks find nothing. If the script fails, report the failure as a finding.
5. **Report**: a short pass/fail summary per repo and per check, plus the dashboard path and its per-section OK/WARN/ERROR summary. Do not auto-commit, auto-push, or auto-propagate in this tier. Surface findings and let the next tier (or an explicit user request) act on them.

### **1.3.2 Periodic tier (heavier, run weekly or before a significant work session)**

1. Run `hap-maintenance` with no qualifier (or `all` if framework alignment should be reviewed too) — this covers Homebrew/Hermes/Ollama updates and calls `hap-copilot-standard-check` internally for the HAP framework-alignment portion.
2. If step 1's standard check (or the daily tier's) found drift between HAP and a subproject, run `hap-propagate-standard` to sync the shared/templated files into the affected subproject(s).
3. For each repo with a remote and pending local commits (from **1.3.1** step 1 or new work since):

   ```bash
   cd /Users/bennyskov/Projects/<REPO>
   git add -A
   git commit -m "<concise message>"
   git push
   ```

   If a repo has no remote yet (e.g. STRM today) or a push is blocked (secret scanning, diverged history), stop and use `hap-sync-copied-library` instead of forcing it here.
4. Re-run the daily tier's git status sweep to confirm every repo is clean and up to date with its remote.
5. Regenerate the workspace status dashboard (daily tier step 4) so it shows the state after the periodic actions.

## **1.4 Decision flow**

```text
Start
  -> Run daily tier (1.3.1)
  -> Any drift, uncommitted work, or stale runtime found?
       no  -> report "all current" and stop
       yes -> is this a scheduled/periodic pass, or did the user ask to fix it now?
                no  -> report findings only, stop
                yes -> run periodic tier (1.3.2) for the affected repos/steps only
```

Do not run the full periodic tier just because the daily tier found one small thing — only act on what was actually flagged (e.g. don't run a Homebrew upgrade because STRM had an uncommitted file).

## **1.5 Guardrails**

- Never force-push, rewrite history, or delete a branch as part of this routine — that is `hap-sync-copied-library` territory and requires its explicit safety steps.
- Never commit `config/KEYS.md` or any file matching the credential patterns in `copilot-ignore.instructions.md`; if a git status sweep shows one of these as untracked-but-not-ignored, stop and flag it instead of committing.
- Keep commit messages for routine syncs short and factual (e.g. "Routine sync: update docs/skills"); do not fabricate a detailed changelog if the actual diff is trivial.
- If `hap-maintenance`'s BASE update flow hits an authentication-gated step (e.g. Docker Desktop cask upgrade), follow its own section 1.8.3 handling — do not retry it automatically from this routine.
- Treat this skill as an orchestrator only; if one of the underlying skills changes its flow, this skill's references should be re-read, not duplicated.

## **1.6 Expected Output**

Return a short routine report:

- Tier run (daily / periodic).
- Per-repo git status (clean / dirty / ahead / behind / no remote).
- Standard drift findings, if any, and whether they were propagated.
- Runtime/software check results, if the periodic tier ran.
- Path to the regenerated HTML status dashboard (`logs/status-report.html`) and its per-section summary.
- Any blocked or deferred step (auth-gated upgrade, missing remote, secret-scanning block) and what it needs next.
