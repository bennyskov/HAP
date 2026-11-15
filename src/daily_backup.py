"""Start Time Machine, copy changed iCloud files, and write a backup dashboard.

Run from HAP: python3 -B -m src.daily_backup
Use --status-only to generate a dashboard without starting or copying backups.
Default output: www/status_report_backup.html (generated, never commit it).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from src.status_report import Section, STATUS_ERROR, STATUS_LABEL, STATUS_OK, STATUS_WARN, render_html, worst

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "PRIVAT"
BACKUP_VOLUME = Path("/Volumes/backup shared")
DEFAULT_DESTINATION = BACKUP_VOLUME / "PRIVAT"
DEFAULT_OUTPUT = REPO_ROOT / "www" / "status_report_backup.html"


def _tmutil(*arguments: str) -> str:
    result = subprocess.run(
        ["/usr/bin/tmutil", *arguments], capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode:
        raise RuntimeError(
            f"tmutil {arguments[0]} exited {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip() or 'no diagnostic output'}"
        )
    return result.stdout


def time_machine(*, start: bool) -> Section:
    section = Section("Time Machine", STATUS_OK, note="A start request is not proof of a completed backup.")
    if start:
        try:
            _tmutil("startbackup")
            section.add("Manual start", "Request accepted")
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            section.add("Manual start", str(exc), STATUS_ERROR, "Time Machine could not be started")
    else:
        section.add("Manual start", "Not requested (status-only)", STATUS_WARN, "No backup started by this invocation")
    try:
        output = _tmutil("status")
        running = re.search(r"\bRunning\s*=\s*([01])\s*;", output)
        if running is None:
            raise RuntimeError("tmutil status did not contain a recognized Running field")
        if running.group(1) == "1":
            phase = re.search(r"\bBackupPhase\s*=\s*([^;]+);", output)
            section.add(
                "Current state", f"Running ({phase.group(1).strip() if phase else 'phase unavailable'})",
                STATUS_WARN, "Backup is in progress; completion is not yet verified",
            )
        else:
            section.add(
                "Current state", "Idle", STATUS_WARN,
                "No backup is currently running; a start request may still be queued",
            )
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        section.add("Current state", str(exc), STATUS_ERROR, "Unable to verify Time Machine status")
    try:
        latest = _tmutil("latestbackup").strip()
        if not latest:
            raise RuntimeError("tmutil latestbackup returned no completed backup")
        section.add("Latest completed backup", latest)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        section.add("Latest completed backup", str(exc), STATUS_WARN, "No completed backup could be verified")
    return section


def _reject_symlinks(path: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Backup paths must be absolute and contain no '..'")
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError(f"Symbolic links are not allowed in backup paths: {component}")


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _copy_file(source: Path, destination: Path, volume: Path) -> int:
    _reject_symlinks(source)
    _reject_symlinks(destination)
    if not os.path.ismount(volume):
        raise OSError("External backup volume is no longer mounted")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    temporary: Path | None = None
    try:
        with os.fdopen(source_fd, "rb") as original:
            before = os.fstat(original.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("Only regular files can be backed up")
            temp_fd, temp_name = tempfile.mkstemp(prefix=".hap-backup-", dir=destination.parent)
            temporary = Path(temp_name)
            with os.fdopen(temp_fd, "w+b") as copied:
                digest = hashlib.sha256()
                count = 0
                while chunk := original.read(1024 * 1024):
                    copied.write(chunk)
                    digest.update(chunk)
                    count += len(chunk)
                copied.flush()
                os.fsync(copied.fileno())
                copied.seek(0)
                if hashlib.file_digest(copied, "sha256").digest() != digest.digest():
                    raise OSError("Copied file checksum did not match")
                if (
                    count != before.st_size
                    or _identity(os.fstat(original.fileno())) != _identity(before)
                    or _identity(source.stat(follow_symlinks=False)) != _identity(before)
                ):
                    raise OSError("Source changed during copying; previous backup was retained")
                os.utime(copied.fileno(), ns=(before.st_atime_ns, before.st_mtime_ns))
            if not os.path.ismount(volume):
                raise OSError("External backup volume disconnected during copying")
            _reject_symlinks(destination)
            os.replace(temporary, destination)
            temporary = None
            return count
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def copy_changed_files(source: Path, destination: Path, volume: Path, *, apply: bool) -> Section:
    section = Section("iCloud file backup", STATUS_OK, note="Incremental mirror: changed files replace their previous copy; destination-only files are retained.")
    section.add("Source", str(source))
    section.add("Destination", str(destination))
    try:
        _reject_symlinks(source)
        _reject_symlinks(destination)
        _reject_symlinks(volume)
        if not source.is_dir():
            raise FileNotFoundError(f"iCloud source directory is unavailable: {source}")
        if not os.path.ismount(volume):
            raise OSError(f"External backup disk is not mounted: {volume}")
        if destination == volume or not destination.is_relative_to(volume):
            raise ValueError("Destination must be a folder inside the external backup volume")
        if destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ValueError("Source and destination must not overlap")
        if destination.exists() and not destination.is_dir():
            raise NotADirectoryError(f"Destination is not a directory: {destination}")
    except (OSError, ValueError) as exc:
        section.add("Preflight", str(exc), STATUS_ERROR, "File backup was not run; no local fallback is allowed")
        return section

    copied = unchanged = pending = skipped = errors = copied_bytes = 0

    def scan_error(exc: OSError) -> None:
        nonlocal errors
        errors += 1
        section.add("Scan error", str(exc), STATUS_ERROR, "Source inventory is incomplete")

    for directory, directories, files in os.walk(source, followlinks=False, onerror=scan_error):
        parent = Path(directory)
        links = [name for name in directories if (parent / name).is_symlink()]
        skipped += len(links)
        directories[:] = [name for name in directories if name not in links]
        for name in files:
            path = parent / name
            target = destination / path.relative_to(source)
            try:
                info = path.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or name.endswith(".icloud"):
                    skipped += 1
                    continue
                _reject_symlinks(target)
                if target.exists():
                    previous = target.stat()
                    if not stat.S_ISREG(previous.st_mode):
                        raise ValueError("Destination file conflicts with a non-regular entry")
                    if (info.st_size, info.st_mtime_ns) == (previous.st_size, previous.st_mtime_ns):
                        unchanged += 1
                        continue
                pending += 1
                if apply:
                    copied_bytes += _copy_file(path, target, volume)
                    copied += 1
            except (OSError, ValueError) as exc:
                errors += 1
                section.add("File copy error", str(exc), STATUS_ERROR, "A file was not backed up; retry after resolving this error")
    section.add("Changed or new files", str(pending))
    section.add("Copied files", str(copied))
    section.add("Unchanged files", str(unchanged))
    section.add("Copied MiB", f"{copied_bytes / (1024 * 1024):.2f}")
    section.add("Errors", str(errors), STATUS_ERROR if errors else STATUS_OK, "Backup is incomplete" if errors else "")
    section.add(
        "Skipped entries", str(skipped), STATUS_WARN if skipped else STATUS_OK,
        "Symlinks, special files, or iCloud placeholders were skipped; download cloud-only files in Finder first" if skipped else "",
    )
    if not apply:
        section.add("Copy action", "Not run (status-only)", STATUS_WARN, "Inventory only; no files were copied")
    else:
        section.add("Copy action", "Finished" if not errors and not skipped else "Incomplete")
    return section


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-only", action="store_true", help="Only check status and pending copies")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Backup dashboard output path")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("This backup routine requires macOS")
    if os.geteuid() == 0:
        parser.error("Run as your normal user; do not use sudo")
    sections = [
        time_machine(start=not args.status_only),
        copy_changed_files(DEFAULT_SOURCE, DEFAULT_DESTINATION, BACKUP_VOLUME, apply=not args.status_only),
    ]
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            render_html(sections, title="HAP Backup Status Report", heading="HAP Daily Backup Status"),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"ERROR: Could not write backup dashboard: {exc}", file=sys.stderr)
        return 1
    print(f"Backup dashboard written to {args.output}")
    for section in sections:
        print(f"[{STATUS_LABEL[section.status]}] {section.title}")
        for row in section.rows:
            print(f"  {row.label}: {row.value}" + (f" ({row.reason})" if row.reason else ""))
    return 1 if worst(*(section.status for section in sections)) == STATUS_ERROR else 0


if __name__ == "__main__":
    raise SystemExit(main())
