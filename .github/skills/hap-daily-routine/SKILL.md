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
- `hap-daily-backup` starts Time Machine, copies changed iCloud files to the external disk, and writes the backup dashboard.
- `hap-architecture` captures user instructions into skills, keeps the home page, architecture page and requirements register current, and describes how to reestablish HAP and its subprojects.
- `hap-copilot-standard-check` is read-only verification — it does not fix anything or touch other repos.
- `hap-propagate-standard` pushes shared `.github` files into subprojects — it does not run software updates or commit/push.
- `hap-sync-copied-library` is for repo init, GitHub creation, or recovering a blocked push — it is not meant for routine day-to-day commits.

None of them, individually or combined, cover "is there uncommitted or unpushed work sitting in BUD/STRM right now?" This skill closes that gap and gives a single entry point for "is everything current and in sync today?"

## **1.3 Two tiers**

### **1.3.1 Daily tier (cleanup, backup, checks, and git sync)**

1. **Disk cleanup** — run first, before any other daily or periodic action:

   ```bash
   source /Users/bennyskov/Projects/HAP/.venv/bin/activate
   python3 -B /Users/bennyskov/Projects/HAP/scripts/disk_cleanup.py --apply
   ```

   [disk_cleanup.py](../../../scripts/disk_cleanup.py) removes only current-user-owned
   regular files under `~/Library/Caches`: `pip/` and `Homebrew/` files must be
   older than 7 days; other user app cache files must be older than 30 days.
   Modification, access, and metadata-change times must all meet the threshold.
   These are the default macOS cache locations; custom pip/Homebrew locations
   outside this tree are deliberately not cleaned. App caches may rebuild or
   require downloads; close apps before a pass where practical. Age checks do
   not guarantee that a file is unused by a running app.
   The script retains directories, skips symlinks, hardlinks, other owners,
   mounted filesystems and protected directory names, and never cleans system
   caches, Trash, Downloads, projects, credentials, models, or Docker data.
   No sudo. Omitting `--apply` provides a read-only preview.
   Report eligible/deleted counts, allocated MiB, skipped entries, and errors;
   allocated size is not guaranteed freed disk space. If cleanup returns nonzero,
   report the partial failure, do not retry deletion automatically, and continue
   independent read-only checks.

2. **Daily backup** — invoke [hap-daily-backup](../hap-daily-backup/SKILL.md)
   immediately after disk cleanup and before the remaining checks. It first
   requests a manual Time Machine backup, then copies new/touched iCloud
   `PRIVAT` files to `/Volumes/backup shared/PRIVAT`, and always generates
   `logs/status_report_backup.html` when the backup steps fail or succeed.
   Report its per-section status; a queued/running backup is not completed.
   Continue independent checks after errors, without retrying backup actions.

3. **Git status sweep** — for each repo in **1.1**:

   ```bash
   cd /Users/bennyskov/Projects/<REPO> && git status --short --branch
   ```

   Flag: uncommitted changes, untracked files outside expected ignore patterns, and `ahead`/`behind` counts versus the remote (if one exists).

4. **Standard drift check** — run `hap-copilot-standard-check` against HAP. If HAP's shared/templated files changed since the last propagate, also run it against BUD and STRM to see whether they've drifted out of sync. Also run `python3 -B src/architecture_refs.py` to confirm the architecture page still matches the skill steps (see `hap-architecture` 1.3 step 5).
5. **Runtime check** — run `hap-maintenance check` (read-only: `hermes status`, venv activation, API connectivity). Do not run the `update` flow in the daily tier.
6. **Daily git sync** — for each repo in **1.1**, follow **1.3.3** to commit
   eligible changes and push any pending local commits. Each new commit must
   identify `hap-daily-routine` in its message. Report blocked repos and
   continue with the other repos; never automatically propagate standards.
7. **Workspace status dashboard** — always regenerate the HTML dashboard as the last check, so it reflects the current state after the git sync:

   ```bash
   source /Users/bennyskov/Projects/HAP/.venv/bin/activate
   python3 /Users/bennyskov/Projects/HAP/src/status_report.py
   ```

   This writes `logs/status-report.html` (git-ignored; see `hap-maintenance` section 1.6.4). Do not skip this step, even when the other checks find nothing. If the script fails, report the failure as a finding.
8. **Report** — a short pass/fail summary per repo and per check, including
   commits and pushes, cleanup and backup results, both dashboard paths and
   their per-section OK/WARN/ERROR summaries. Both reports are linked from the
   home page `index.html`.

### **1.3.2 Periodic tier (heavier, run weekly or before a significant work session)**

1. **Maintenance update** — run `hap-maintenance` with no qualifier (or `all` if framework alignment should be reviewed too) — this covers Homebrew/Hermes/Ollama updates and calls `hap-copilot-standard-check` internally for the HAP framework-alignment portion.
2. **Standard propagation** — if step 1's standard check (or the daily tier's) found drift between HAP and a subproject, run `hap-propagate-standard` to sync the shared/templated files into the affected subproject(s).
3. **Periodic git sync** — if periodic actions produced new changes or local commits, sync the affected
   repos using the same safety checks and commit attribution in **1.3.3**.
4. **Git status recheck** — re-run the daily tier's git status sweep to confirm every repo is clean and up to date with its remote.
5. **Dashboard refresh** — regenerate the workspace status dashboard (daily tier step 7) so it shows the state after the periodic actions. Refresh the backup dashboard with `hap-daily-backup`'s status-only mode if a current Time Machine snapshot is needed; do not start a second backup pass.

### **1.3.3 Safe git sync**

Apply these steps separately to HAP, BUD, and STRM:

1. **Preflight** — check the branch, status, staged and unstaged changes, untracked paths, and
   upstream. If there is no upstream, the branch is detached, or the remote is
   unavailable, report the repo as blocked without committing or pushing.
   Fetch the configured upstream and check ahead/behind against the refreshed
   tracking branch. If behind or diverged, stop for that repo; do not pull,
   merge, rebase, force-push, or rewrite history automatically.
2. **Review candidates** — before staging or pushing, review the candidate paths and changes, including
   already-staged changes and commits pending push. Never include secrets,
   credentials, private data, generated or protected content, or other ignored
   paths. Do not read excluded files to inspect their contents. If a candidate
   is unsafe, cannot be reviewed safely, or its eligibility is uncertain, block
   the whole repo and report why; do not silently omit it or push existing
   commits from that repo. Preserve existing staged changes.
3. **Stage and commit** — stage only the individually reviewed eligible paths, including tracked
   deletions. Do not use blanket `git add -A` on the entire repo. Recheck the
   complete staged diff before committing. If there are staged changes, create
   a commit with a short factual description identifying the daily routine and
   the required co-author trailer, for example:

   ```text
   hap-daily-routine: update project files

   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
   ```

   Do not create an empty commit. If only previously committed changes are
   ahead, push them without creating a new commit or rewriting their messages.
4. **Push** — push only to the current branch's verified configured upstream, without
   force. If the commit or push fails, report the error and any remaining local
   changes or commits; do not automatically retry, modify the remote, or claim
   the repo is synced. A blocked push-protection or authentication issue needs
   explicit resolution, not history rewriting in this routine.
5. **Verify sync** — after a successful push, refresh the upstream and recheck local status and
   ahead/behind. If the refresh fails, report synchronization as unverified.
   Report the commit identifier, push result, and any remaining changes for each
   repo; a clean, up-to-date repo needs no commit or push.

## **1.4 Decision flow**

```text
Start
  -> Run daily tier (1.3.1)
  -> Any drift, blocked git sync, or stale runtime found?
       no  -> report "all current" and stop
       yes -> is this a scheduled/periodic pass, or did the user ask to fix it now?
                no  -> report findings only, stop
                yes -> run periodic tier (1.3.2) for the affected repos/steps only
```

Do not run the full periodic tier just because the daily tier found one small thing — only act on what was actually flagged (e.g. don't run a Homebrew upgrade because STRM had an uncommitted file).

## **1.5 Guardrails**

- Never force-push, rewrite history, or delete a branch as part of this routine — that is `hap-sync-copied-library` territory and requires its explicit safety steps.
- Never commit `config/KEYS.md` or any file matching the credential patterns in `copilot-ignore.instructions.md`; if a git status sweep shows one of these, stop the affected repo's sync and flag it instead of committing or pushing.
- Keep commit messages short and factual and identify `hap-daily-routine`; do not fabricate a detailed changelog if the actual diff is trivial.
- If `hap-maintenance`'s BASE update flow hits an authentication-gated step (e.g. Docker Desktop cask upgrade), follow its own section 1.8.3 handling — do not retry it automatically from this routine.
- Treat this skill as an orchestrator only; if one of the underlying skills changes its flow, this skill's references should be re-read, not duplicated.

## **1.6 Expected Output**

Return a short routine report:

- Tier run (daily / periodic).
- Disk cleanup result (eligible/deleted files, allocated MiB, skipped entries, errors).
- Backup result and path to `logs/status_report_backup.html`, including Time Machine's request/current state and file-copy counts.
- Per-repo git status (clean / dirty / ahead / behind / no remote).
- Per-repo commit identifier, push result, and blocked or skipped sync reason.
- Standard drift findings, if any, and whether they were propagated.
- Runtime/software check results, if the periodic tier ran.
- Path to the regenerated HTML status dashboard (`logs/status-report.html`) and its per-section summary.
- Any blocked or deferred step (auth-gated upgrade, missing remote, secret-scanning block) and what it needs next.
