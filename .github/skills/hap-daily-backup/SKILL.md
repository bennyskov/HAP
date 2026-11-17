---
name: hap-daily-backup
description: Back up iCloud PRIVAT, archive the backup volume, and safely make eligible files iCloud-only.
---

# **1. Skill Instructions**

## **1.1 Purpose**

Run the daily backup before the daily routine's checks, immediately after disk
cleanup. This skill owns backup logic; the daily routine only invokes it.

## **1.2 Paths and prerequisites**

- Run as the normal macOS user, never with sudo.
- Activate the HAP virtual environment.
- iCloud source: `~/Library/Mobile Documents/com~apple~CloudDocs/PRIVAT`.
  The requested `iCloud/PRIVATE` is actually named `PRIVAT` on this Mac; do not
  create a new `PRIVATE` directory or silently switch between sources.
- External destination: `/Volumes/backup shared/PRIVAT`.
  `/Volumes/backup shared` must already be mounted. Never create a replacement
  volume directory on the internal disk or fall back to another destination.
- Time Machine must already have a destination configured.
- Archive destination: `/Volumes/Virtuel Machines/zip-archive-of-backup-shared/`.
  The `Virtuel Machines` volume must already be mounted.
- Step 5 requires the macOS Swift command-line tools and Foundation.

## **1.3 Execution**

```bash
source /Users/bennyskov/Projects/HAP/.venv/bin/activate
cd /Users/bennyskov/Projects/HAP
python3 -B -m src.daily_backup
```

[daily_backup.py](../../../src/daily_backup.py) performs these steps in order:

1. **Force a manual Time Machine start:** call `/usr/bin/tmutil startbackup`
   without `--auto`, then query status and the latest completed backup.
   This bypasses waiting for the scheduled run, not macOS permissions or an
   unavailable destination. Do not stop/restart an already-running backup.
   The request is non-blocking: accepted, queued/running, and completed are
   distinct states. A previous completed backup does not prove this run finished.
   If authorization or Full Disk Access is required, report the error; do not
   collect passwords or retry with sudo.
2. **Copy new/touched iCloud files:** recursively compare file size and
   nanosecond modification time with the corresponding external copy. Copy
   when either differs or the destination file is missing, even if the
   destination timestamp is newer. Preserve relative paths and modification
   times. Stage and checksum each copy before atomically replacing its previous
   version; a source changing during copying is reported as an error.
   Copies use private permissions. No deletion or pruning of destination-only
   files, no historical version archive, and no source modifications.
   Symlinks, special files and `.icloud` placeholders are skipped and reported
   as incomplete. For cloud-only files, download them in Finder first; normal
   iCloud file reads may require hydration. Files whose content changes while
   both size and modification time are deliberately preserved are not detected.
3. **Generate the backup dashboard**, including when either backup step fails:
   `www/status_report_backup.html`. It shows the generation timestamp, Time
   Machine request/live state/latest completed backup, source and destination,
   pending/copied/unchanged counts, copied MiB, skips, and explicit errors.
   It is a snapshot, not a live completion monitor or persisted last-success
   record. Never interpret "request accepted" as "backup completed". The
   generated report is Git-visible but must never be committed.
4. **Archive the backup shared volume:** create a dated ZIP of everything in
   `/Volumes/backup shared`, excluding only top-level dot files, at
   `/Volumes/Virtuel Machines/zip-archive-of-backup-shared/`. Include dot
   directories and nested dot files. Verify the archive before publishing it;
   keep only the five newest archives made by this workflow. Never delete older
   archives if creation or verification fails. Preserve symbolic links as
   links without following them. Fail explicitly on special files,
   inaccessible files, or a file changing during copying rather than claiming
   a complete archive. This is not a filesystem snapshot;
   concurrent additions or removals may not be captured. Require both volumes
   to be mounted; do not create a
   fallback volume. Report archive and retention errors in the command output.
   The dashboard is written before this step and does not show the ZIP result.
   ZIP timestamps outside 1980–2107 are clamped to the supported range.
5. **Make PRIVAT files iCloud-only:** after the preceding steps, use
   [icloud_eviction.swift](../../../src/icloud_eviction.swift) and Apple's
   `FileManager.evictUbiquitousItem(at:)` to remove eligible local file copies,
   not the iCloud copies or the external backups. Do not run this step if
   Time Machine, the copy, dashboard, or ZIP reports an error. A Time Machine
   start remains asynchronous and is not proof of completion.
   For each downloaded regular file, require an uploaded, current iCloud version
   with no active upload, download, conflict, or sync exclusion; unknown states
   are errors. Verify the current file against the external backup with SHA-256,
   checking both files for changes, then recheck iCloud state and file identity
   immediately before eviction. Files already cloud-only are not downloaded.
   Symlinks, special files, and legacy `.icloud` placeholders are skipped.
   Errors leave affected files untouched where possible and are reported;
   eviction requests that succeeded before a later failure are not undone.
   macOS may download a file again when it is accessed. Results are printed
   after the dashboard is written, so they are not included in that snapshot.
   Copying later changed cloud-only files can download them again before backup.

Time Machine failure must not prevent the independent file copy or dashboard.
File copy failure must not prevent the dashboard. A nonzero exit indicates an
error; report it and continue independent daily checks, without automatic retries.

## **1.4 Status-only mode**

To refresh the dashboard without starting Time Machine or copying files:

```bash
source /Users/bennyskov/Projects/HAP/.venv/bin/activate
cd /Users/bennyskov/Projects/HAP
python3 -B -m src.daily_backup --status-only
```

This scans metadata, checks Time Machine, and writes only the HTML dashboard;
it does not create or prune ZIP archives or evict iCloud files.
The dashboard explicitly marks actions as not run and never claims success for
files merely found to be pending.

## **1.5 Expected output**

- Time Machine request result, current state, and latest verified completed backup.
- File copy counts, bytes, skips, and errors.
- Dashboard path and per-section OK/WARN/ERROR states.
- ZIP archive result and retention errors.
- iCloud-only counts and errors, including any files left local.
- Any required action: mount the disk, download cloud-only files, grant macOS
  access interactively, or retry an unstable file after it stops changing.
