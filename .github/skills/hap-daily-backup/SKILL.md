---
name: hap-daily-backup
description: Start a manual Time Machine backup, copy changed iCloud PRIVAT files to the external backup shared disk, and generate the backup status dashboard.
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
   `logs/status_report_backup.html`. It shows the generation timestamp, Time
   Machine request/live state/latest completed backup, source and destination,
   pending/copied/unchanged counts, copied MiB, skips, and explicit errors.
   It is a snapshot, not a live completion monitor or persisted last-success
   record. Never interpret "request accepted" as "backup completed".

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

This scans metadata, checks Time Machine, and writes only the HTML dashboard.
The dashboard explicitly marks actions as not run and never claims success for
files merely found to be pending.

## **1.5 Expected output**

- Time Machine request result, current state, and latest verified completed backup.
- File copy counts, bytes, skips, and errors.
- Dashboard path and per-section OK/WARN/ERROR states.
- Any required action: mount the disk, download cloud-only files, grant macOS
  access interactively, or retry an unstable file after it stops changing.
