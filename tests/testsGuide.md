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
generation after a failed backup. The existing workspace dashboard's default
title and heading remain covered when reusing its renderer.

# **3. Architecture Reference Tests**

## **3.1 Running**

From the HAP repository root:

```bash
source .venv/bin/activate
python3 -B -m unittest discover -s tests -p 'test_architecture_refs.py' -v
```

## **3.2 Scope**

[test_architecture_refs.py](test_architecture_refs.py) tests
[architecture_refs.py](../src/architecture_refs.py). One case checks the real
`architecture.html` against the real skills; the others use temporary skill and
page fixtures to cover matching references, renamed steps, steps missing from
the page, unknown steps/sections/skills, section-title mismatches, and ignoring
numbered lines inside code fences.
