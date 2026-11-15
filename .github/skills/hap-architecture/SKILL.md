---
name: hap-architecture
description: Use this skill to capture user instructions into skills, maintain the HAP home and architecture pages and the requirements register, and reestablish HAP and its subprojects from the skills.
---

# **1. Skill Instructions**

## **1.1 Purpose**

The skills are the source of truth for how HAP and its subprojects (BUD,
STRM, future projects) work. Every durable instruction from the user must end
up in a skill step, so the workspace can always be reestablished and explained
from the skills alone. This skill owns that capture process, the requirements
register, and the two pages that visualize it.

## **1.2 Pages**

- [index.html](../../../www/index.html) — the HAP home page. Links to the
  architecture page and both status reports
  (`www/status-report.html`, `www/status_report_backup.html`).
- [architecture.html](../../../www/architecture.html) — the HAP architecture:
  layers, the daily/periodic flowchart, the reestablish flow, the skills map,
  and the requirements register.

Every step on the architecture page carries a reference badge such as
`1.3.1 step 1 · Disk cleanup`. The same number and step name exist in the
named skill, so a badge can always be followed back to its instruction. Each
reference is encoded as `data-skill`, `data-section`, `data-step` and
`data-name` attributes, which [architecture_refs.py](../../../src/architecture_refs.py)
validates against the skill files.

## **1.3 Capture flow**

Run this whenever the user gives a durable instruction (a new behavior,
script, page, schedule, or rule — not a one-off question):

1. **Capture the instruction** — update the owning skill, or create a new
   skill when none fits. Write the instruction as a numbered step with a bold
   step name under a numbered heading, so it can be referenced.
2. **Register the request** — add an item to **1.5** with the date, the
   request in short form, and the skill reference(s) where it now lives.
3. **Update the architecture page** — add or adjust the matching nodes in
   `www/architecture.html`. Badge text, `data-section`, `data-step` and
   `data-name` must match the skill exactly.
4. **Update the home page** — when a new page or report is added, link it from
   `www/index.html`.
5. **Verify references** — run the reference check and its tests; fix every
   reported mismatch before finishing:

   ```bash
   source /Users/bennyskov/Projects/HAP/.venv/bin/activate
   cd /Users/bennyskov/Projects/HAP
   python3 -B src/architecture_refs.py
   python3 -B -m unittest discover -s tests -p 'test_*.py'
   ```

## **1.4 Reestablish HAP and subprojects**

Skills describe the workflows; the code they run (`scripts/`, `src/`,
`tests/`) lives in git. Together they are enough to rebuild the workspace:

1. **Restore repositories** — clone `bennyskov/HAP`, `bennyskov/BUD` and
   `bennyskov/STRM` as siblings under `~/Projects/`. If a remote is missing,
   use `hap-sync-copied-library`.
2. **Create the virtual environment** — in HAP:
   `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. **Restore the runtime** — run `hap-maintenance` (update mode) for
   Homebrew, Hermes and Ollama.
4. **Restore subproject standards** — run `hap-propagate-standard` for each
   subproject.
5. **Verify the architecture** — run the reference check in **1.3** step 5.
6. **Run the daily routine** — run `hap-daily-routine`; it regenerates both
   status reports linked from the home page.

## **1.5 Requirements register**

User requests, newest last, with where each one is captured:

1. **Disk cleanup** — 2026-11-15: a tight Python disk cleanup, run first in
   the daily routine (pip/Homebrew caches older than 7 days, other user app
   caches older than 30 days). Captured in `hap-daily-routine` 1.3.1 step 1
   and `scripts/disk_cleanup.py`.
2. **Daily backup** — 2026-11-15: a `hap-daily-backup` skill started by the
   daily routine; first force a Time Machine backup, then copy touched files
   from iCloud `PRIVAT` to the external disk `backup shared/PRIVAT`. Captured
   in `hap-daily-backup` 1.3 steps 1–2 and `hap-daily-routine` 1.3.1 step 2.
3. **Backup status report** — 2026-11-15: a separate
   `www/status_report_backup.html` showing the backup status. Captured in
   `hap-daily-backup` 1.3 step 3.
4. **Daily git sync** — 2026-11-15: commit and push any missing update in the
   daily routine, with the commit stating the daily routine made it. Captured
   in `hap-daily-routine` 1.3.1 step 6 and 1.3.3.
5. **Status home page** — 2026-11-15: a home page linking the status reports.
   Captured in this skill, 1.2 and 1.3 step 4.
6. **Architecture page** — 2026-11-15: a page showing the HAP architecture and
   a flowchart of the steps, with reference points matching the skill step
   numbers and names. Captured in this skill, 1.2 and 1.3 step 3.
7. **Skills as source of truth** — 2026-11-15: always update the skills with
   every user instruction so HAP and the subprojects can be reestablished from
   the skills. Captured in this skill, 1.1, 1.3 and 1.4, and in
   `.github/copilot-instructions.md` 1.5.
8. **Web page directory** — 2026-11-15: move the home page and
   `status-report*` into `www/` and update their links and generator paths.
   Captured in this skill, 1.7 step 1, and `hap-daily-routine` 1.3.1 step 7.
9. **Backup report directory** — 2026-11-15: move the backup status report into
   `www/` and update its references. Captured in this skill, 1.7 step 1, and
   `hap-daily-backup` 1.3 step 3.
10. **Keep web content visible to Git** — 2026-11-15: do not git-ignore
    content in `www/`. Captured in this skill, 1.7 step 2, and
    `hap-daily-routine` 1.3.3 step 2.
11. **Architecture page directory** — 2026-11-15: move the architecture page
    into `www/` and update its links and reference checker. Captured in this
    skill, 1.7 step 1, and `src/architecture_refs.py`.

## **1.6 Guardrails**

- Never leave a durable user instruction only in chat; finish the capture flow
  in **1.3** in the same task.
- Do not renumber or rename an existing skill step without updating the
  architecture page in the same change; the reference check must pass.
- Keep private data out of the pages: show folder roles and paths, never file
  names or contents from iCloud, backups, logs, or credentials.
- The home and architecture pages are static, version-controlled files. Status
  reports are generated by the daily routine and must never be committed.
  Content in `www/` is intentionally Git-visible; report the generated
  dashboards separately and leave them unstaged during routine sync.

## **1.7 Web page locations**

1. **Keep the pages and reports in www** — keep the home and architecture
   pages at `www/index.html` and `www/architecture.html`, and generate the
   workspace and backup reports at `www/status-report.html` and
   `www/status_report_backup.html`. Keep navigation, skill links, report
   generators and the reference checker aligned with these locations.
2. **Do not ignore www content** — keep all `www/` paths visible to Git,
   including nested paths matching general ignore rules. Review content before
   committing and never commit secrets or generated reports.
