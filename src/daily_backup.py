"""Start Time Machine, copy iCloud files, archive the backup, and make safe files cloud-only.

Run from HAP: python3 -B -m src.daily_backup
Use --status-only to generate a dashboard without starting, copying, archiving, or evicting.
Default output: www/status_report_backup.html (generated, never commit it).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from src.status_report import Section, STATUS_ERROR, STATUS_LABEL, STATUS_OK, STATUS_WARN, render_html, worst

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "PRIVAT"
BACKUP_VOLUME = Path("/Volumes/backup shared")
DEFAULT_DESTINATION = BACKUP_VOLUME / "PRIVAT"
DEFAULT_OUTPUT = REPO_ROOT / "www" / "status_report_backup.html"
ARCHIVE_VOLUME = Path("/Volumes/Virtuel Machines")
ARCHIVE_DESTINATION = ARCHIVE_VOLUME / "zip-archive-of-backup-shared"
ARCHIVE_PATTERN = re.compile(r"backup-shared-\d{8}-\d{6}-\d{6}-[a-z0-9_]{8}\.zip")
ICLOUD_HELPER = REPO_ROOT / "src" / "icloud_eviction.swift"


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


def _archive_symlink(archive: zipfile.ZipFile, path: Path, source: Path) -> None:
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISLNK(before.st_mode):
        raise OSError("Archive entry changed while reading a symbolic link")
    target = os.readlink(path)
    if _identity(path.stat(follow_symlinks=False)) != _identity(before):
        raise OSError("Symbolic link changed during archiving")
    timestamp = time.localtime(before.st_mtime)
    year = min(2107, max(1980, timestamp.tm_year))
    date_time = (
        (1980, 1, 1, 0, 0, 0) if timestamp.tm_year < 1980 else
        (2107, 12, 31, 23, 59, 58) if timestamp.tm_year > 2107 else
        (year, timestamp.tm_mon, timestamp.tm_mday, timestamp.tm_hour, timestamp.tm_min, timestamp.tm_sec)
    )
    info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time)
    info.create_system = 3
    info.external_attr = before.st_mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, os.fsencode(target))


def archive_backup(source: Path, destination: Path, volume: Path) -> Section:
    section = Section("Backup shared archive", STATUS_OK)
    temporary: Path | None = None
    try:
        for path in (source, destination, volume):
            _reject_symlinks(path)
        if not os.path.ismount(source) or not os.path.ismount(volume):
            raise OSError("Both backup volumes must be mounted")
        if not destination.is_relative_to(volume) or destination == volume:
            raise ValueError("Archive destination must be inside its mounted volume")
        if destination.is_relative_to(source) or source.is_relative_to(destination):
            raise ValueError("Archive source and destination must not overlap")
        destination.mkdir(parents=True, exist_ok=True)
        _reject_symlinks(destination)
        prefix = datetime.now().strftime("backup-shared-%Y%m%d-%H%M%S-%f-")
        fd, name = tempfile.mkstemp(prefix=prefix, suffix=".partial", dir=destination)
        temporary = Path(name)
        with os.fdopen(fd, "w+b") as output:
            with zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True,
                strict_timestamps=False,
            ) as archive:
                def scan_error(exc: OSError) -> None:
                    raise exc

                for directory, directories, files in os.walk(source, followlinks=False, onerror=scan_error):
                    parent = Path(directory)
                    for entry in directories[:]:
                        folder = parent / entry
                        if folder.is_symlink():
                            _archive_symlink(archive, folder, source)
                            directories.remove(entry)
                        else:
                            archive.write(folder, folder.relative_to(source).as_posix() + "/")
                    for entry in files:
                        if parent == source and entry.startswith("."):
                            continue
                        path = parent / entry
                        mode = path.stat(follow_symlinks=False).st_mode
                        if stat.S_ISLNK(mode):
                            _archive_symlink(archive, path, source)
                            continue
                        if not stat.S_ISREG(mode):
                            raise ValueError("Archive source contains a non-regular file")
                        source_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                        with os.fdopen(source_fd, "rb") as original:
                            before = os.fstat(original.fileno())
                            if not stat.S_ISREG(before.st_mode):
                                raise ValueError("Archive source contains a non-regular file")
                            info = zipfile.ZipInfo.from_file(
                                path, path.relative_to(source).as_posix(), strict_timestamps=False
                            )
                            info.compress_type = zipfile.ZIP_DEFLATED
                            with archive.open(info, "w", force_zip64=True) as member:
                                shutil.copyfileobj(original, member, length=1024 * 1024)
                            if (
                                _identity(os.fstat(original.fileno())) != _identity(before)
                                or _identity(path.stat(follow_symlinks=False)) != _identity(before)
                            ):
                                raise OSError("Archive source changed during copying")
            output.flush()
            os.fsync(output.fileno())
            output.seek(0)
            with zipfile.ZipFile(output) as archive:
                if archive.testzip() is not None:
                    raise OSError("Archive verification failed")
        if not os.path.ismount(source) or not os.path.ismount(volume):
            raise OSError("A backup volume disconnected during archiving")
        _reject_symlinks(destination)
        final = temporary.with_suffix(".zip")
        os.replace(temporary, final)
        temporary = None
        archives = sorted(
            (p for p in destination.iterdir() if ARCHIVE_PATTERN.fullmatch(p.name) and not p.is_symlink() and p.is_file()),
            key=lambda p: p.name,
            reverse=True,
        )
        for old in archives[5:]:
            if not os.path.ismount(volume):
                raise OSError("Archive volume disconnected during retention")
            _reject_symlinks(old)
            old.unlink()
        section.add("Archive", str(final))
        section.add("Retained archives", str(min(len(archives), 5)))
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        section.add("Archive error", str(exc), STATUS_ERROR, "Archive or retention did not complete")
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                section.add("Cleanup error", str(exc), STATUS_ERROR, "Incomplete archive could not be removed")
    return section


def _icloud_operation(mode: str, items: list[dict]) -> list[dict]:
    result = subprocess.run(
        ["/usr/bin/swift", str(ICLOUD_HELPER), mode], input=json.dumps(items),
        capture_output=True, text=True, timeout=3600, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"iCloud helper exited {result.returncode}: {result.stderr.strip() or 'no diagnostic output'}")
    try:
        responses = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("iCloud helper returned invalid JSON") from exc
    if (
        not isinstance(responses, list) or len(responses) != len(items)
        or any(
            not isinstance(row, dict) or row.get("status") not in {"eligible", "cloud_only", "unsafe", "evicted", "error"}
            or not isinstance(row.get("detail"), str)
            for row in responses
        )
    ):
        raise RuntimeError("iCloud helper returned an invalid result")
    return responses


def _verified_backup_identity(source: Path, target: Path, volume: Path) -> tuple[int, int, int, int, int]:
    _reject_symlinks(source)
    _reject_symlinks(target)
    if not os.path.ismount(volume):
        raise OSError("External backup volume is no longer mounted")
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(source_fd, "rb") as original:
        target_fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(target_fd, "rb") as backup:
            before, backup_before = os.fstat(original.fileno()), os.fstat(backup.fileno())
            if not stat.S_ISREG(before.st_mode) or not stat.S_ISREG(backup_before.st_mode):
                raise ValueError("Source and backup must be regular files")
            if before.st_size != backup_before.st_size or (
                hashlib.file_digest(original, "sha256").digest() != hashlib.file_digest(backup, "sha256").digest()
            ):
                raise ValueError("External backup does not match the local file")
            if (
                _identity(os.fstat(original.fileno())) != _identity(before)
                or _identity(source.stat(follow_symlinks=False)) != _identity(before)
                or _identity(os.fstat(backup.fileno())) != _identity(backup_before)
                or _identity(target.stat(follow_symlinks=False)) != _identity(backup_before)
                or not os.path.ismount(volume)
            ):
                raise OSError("File, backup, or volume changed during verification")
            return _identity(before)


def make_icloud_only(source: Path, destination: Path, volume: Path) -> Section:
    section = Section("iCloud-only storage", STATUS_OK)
    candidates: list[dict] = []
    skipped = errors = cloud_only = evicted = 0

    def scan_error(exc: OSError) -> None:
        nonlocal errors
        errors += 1
        section.add("Scan error", str(exc), STATUS_ERROR, "iCloud inventory is incomplete")

    try:
        for path in (source, destination, volume):
            _reject_symlinks(path)
        if not source.is_dir() or not destination.is_dir() or not os.path.ismount(volume):
            raise OSError("iCloud source or mounted external backup is unavailable")
        if destination == volume or not destination.is_relative_to(volume):
            raise ValueError("Backup destination must be inside the external volume")
        for directory, directories, files in os.walk(source, followlinks=False, onerror=scan_error):
            parent = Path(directory)
            links = [name for name in directories if (parent / name).is_symlink()]
            skipped += len(links)
            directories[:] = [name for name in directories if name not in links]
            for name in files:
                path = parent / name
                try:
                    if name.endswith(".icloud") or not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
                        skipped += 1
                    else:
                        _reject_symlinks(path)
                        candidates.append({"path": str(path), "identity": None})
                except (OSError, ValueError) as exc:
                    errors += 1
                    section.add("Inventory error", str(exc), STATUS_ERROR, "A file was not checked")

        inspected = _icloud_operation("inspect", candidates) if candidates else []
        ready: list[dict] = []
        for candidate, result in zip(candidates, inspected):
            status = result["status"]
            if status == "cloud_only":
                cloud_only += 1
            elif status == "eligible":
                path = Path(candidate["path"])
                try:
                    identity = _verified_backup_identity(path, destination / path.relative_to(source), volume)
                    ready.append({"path": str(path), "identity": identity})
                except (OSError, ValueError) as exc:
                    errors += 1
                    section.add("Backup verification error", str(exc), STATUS_ERROR, "Local copy was retained")
            else:
                errors += 1
                section.add("iCloud state error", result["detail"] or f"Unexpected status: {status}", STATUS_ERROR, "Local copy was retained")
        for result in _icloud_operation("evict", ready) if ready else []:
            if result["status"] == "evicted":
                evicted += 1
            elif result["status"] == "cloud_only":
                cloud_only += 1
            else:
                errors += 1
                section.add("iCloud eviction error", result["detail"] or f"Unexpected status: {result['status']}", STATUS_ERROR, "Local copy was retained or state is uncertain")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        errors += 1
        section.add("iCloud-only error", str(exc), STATUS_ERROR, "Operation did not complete")
    section.add("Already cloud-only", str(cloud_only))
    section.add("Eviction requests accepted", str(evicted))
    section.add("Skipped entries", str(skipped), STATUS_WARN if skipped else STATUS_OK, "Symlinks, special files, and legacy placeholders are not evicted" if skipped else "")
    section.add("Errors", str(errors), STATUS_ERROR if errors else STATUS_OK, "Resolve errors before retrying" if errors else "")
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
    dashboard_error = False
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            render_html(sections, title="HAP Backup Status Report", heading="HAP Daily Backup Status"),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"ERROR: Could not write backup dashboard: {exc}", file=sys.stderr)
        dashboard_error = True
    if not dashboard_error:
        print(f"Backup dashboard written to {args.output}")
    if not args.status_only:
        archive = archive_backup(BACKUP_VOLUME, ARCHIVE_DESTINATION, ARCHIVE_VOLUME)
        sections.append(archive)
        if dashboard_error or any(section.status == STATUS_ERROR for section in sections):
            skipped = Section("iCloud-only storage", STATUS_ERROR)
            skipped.add("Action", "Not run", STATUS_ERROR, "A preceding backup, archive, or dashboard failed")
            sections.append(skipped)
        else:
            sections.append(make_icloud_only(DEFAULT_SOURCE, DEFAULT_DESTINATION, BACKUP_VOLUME))
    for section in sections:
        print(f"[{STATUS_LABEL[section.status]}] {section.title}")
        for row in section.rows:
            print(f"  {row.label}: {row.value}" + (f" ({row.reason})" if row.reason else ""))
    return 1 if dashboard_error or worst(*(section.status for section in sections)) == STATUS_ERROR else 0


if __name__ == "__main__":
    raise SystemExit(main())
