# **1. Disk Cleanup Tests**

## **1.1 Running**

From the HAP repository root:

```bash
source .venv/bin/activate
python3 -B -m unittest discover -s tests -p 'test_disk_cleanup.py' -v
```

## **1.2 Scope**

[test_disk_cleanup.py](test_disk_cleanup.py) tests
[disk_cleanup.py](../scripts/disk_cleanup.py) using isolated temporary fixtures,
never the real user's caches. Cases cover preview mode, separate 7/30-day
retention boundaries, recent access/change protection, retained directories,
symlinks, hardlinks, protected content, changes between scanning and deletion,
missing caches, and explicit I/O failures including the CLI's nonzero exit status.

# **2. Daily Backup Tests**

## **2.1 Running**

From the HAP repository root:

```bash
source .venv/bin/activate
python3 -B -m unittest discover -s tests -p 'test_daily_backup.py' -v
```

## **2.2 Scope**

[test_daily_backup.py](test_daily_backup.py) tests
[daily_backup.py](../src/daily_backup.py) with isolated temporary source and
destination fixtures and mocked Time Machine commands/mount checks. Tests never
start Time Machine or copy real iCloud files. Cases cover new/touched/unchanged
files, size changes with preserved timestamps, non-pruning copies, status-only
mode, missing sources/unmounted disks, symlink and placeholder handling,
atomic-copy failures, changing sources, explicit command errors, and dashboard
generation after a failed backup. The backup dashboard's default output path and
the existing workspace dashboard's default title and heading are also covered.
ZIP tests cover top-level dot-file exclusion, nested hidden entries, empty
folders, old timestamps, five-archive retention, symlink preservation, special
file failures, unmounted volumes, and command failure reporting.
The iCloud-only step uses mocked iCloud operations and temporary files to check
backup verification, unsafe or changed files, failure gating, and status-only
behavior. A macOS helper test checks that ordinary local files are never evicted;
tests never evict real iCloud files.

# **3. Architecture Reference Tests**

## **3.1 Running**

From the HAP repository root:

```bash
source .venv/bin/activate
python3 -B -m unittest discover -s tests -p 'test_architecture_refs.py' -v
```

## **3.2 Scope**

[test_architecture_refs.py](test_architecture_refs.py) tests
[architecture_refs.py](../src/architecture_refs.py). Cases check the real
`www/architecture.html` and its skill links, the checker's default page path,
and temporary skill and page fixtures covering matching references, renamed
steps, steps missing from the page, unknown steps/sections/skills,
section-title mismatches, and ignoring numbered lines inside code fences.

# **4. Status Report Path Tests**

## **4.1 Running**

From the HAP repository root:

```bash
source .venv/bin/activate
python3 -B -m unittest discover -s tests -p 'test_status_report.py' -v
```

## **4.2 Scope**

[test_status_report.py](test_status_report.py) checks the workspace report's
default and explicit output paths, the home and architecture page links, and
Git ignore behavior for web content and other paths. System status collection
is mocked; explicit-output testing uses a temporary directory, and the Git
ignore test uses hypothetical paths without modifying the real reports.
