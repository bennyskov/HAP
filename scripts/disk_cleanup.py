"""Clean stale files under the current macOS user's ~/Library/Caches.

Preview by default; --apply deletes approved cache files. No dependencies,
administrator privileges, directory removal, or system-wide cleanup.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DAY = 24 * 60 * 60
PROTECTED_NAMES = {
    ".archive", ".git", ".vs", "credentials", "data", "logs", "logs-Copy",
    "temp", "bin", "swql", "node_modules", "obj", "packages", "TestResults",
}
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@dataclass
class CleanupResult:
    eligible_files: int = 0
    deleted_files: int = 0
    allocated_bytes: int = 0
    skipped_files: int = 0
    errors: int = 0


def _open_directory(path: Path) -> int:
    """Open each path component without following symlinks."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Cache path must be absolute and contain no '..'")
    fd = os.open(path.anchor, DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            child_fd = os.open(component, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child_fd
        return fd
    except OSError:
        os.close(fd)
        raise


def cleanup(home: Path, *, apply: bool = False, now: float | None = None) -> CleanupResult:
    """Scan only Library/Caches beneath home; report failures and retain directories."""
    result = CleanupResult()
    root = home / "Library" / "Caches"
    timestamp = time.time() if now is None else now
    uid = os.geteuid()

    def error(path: Path, exc: OSError) -> None:
        result.errors += 1
        print(f"ERROR: {path}: {exc}", file=sys.stderr)

    def visit(fd: int, relative: Path, device: int) -> None:
        with os.scandir(fd) as entries:
            for entry in entries:
                path = relative / entry.name
                if entry.name in PROTECTED_NAMES:
                    result.skipped_files += 1
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                    if info.st_uid != uid or info.st_dev != device:
                        result.skipped_files += 1
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        child_fd = os.open(entry.name, DIRECTORY_FLAGS, dir_fd=fd)
                        try:
                            opened = os.fstat(child_fd)
                            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                                result.skipped_files += 1
                                continue
                            visit(child_fd, path, device)
                        finally:
                            os.close(child_fd)
                        continue
                    days = 7 if path.parts[0] in {"pip", "Homebrew"} else 30
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or max(info.st_mtime, info.st_atime, info.st_ctime) >= timestamp - days * DAY
                    ):
                        result.skipped_files += 1
                        continue
                    if apply:
                        # Recheck identity and age metadata immediately before unlinking.
                        current = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                        if current != info:
                            result.skipped_files += 1
                            continue
                        os.unlink(entry.name, dir_fd=fd)
                        result.deleted_files += 1
                    result.eligible_files += 1
                    result.allocated_bytes += info.st_blocks * 512
                except OSError as exc:
                    error(root / path, exc)

    try:
        fd = _open_directory(root)
    except FileNotFoundError:
        print(f"SKIP: cache directory does not exist: {root}")
        return result
    except OSError as exc:
        error(root, exc)
        return result
    try:
        info = os.fstat(fd)
        if info.st_uid != uid:
            error(root, PermissionError("Cache directory is not owned by the current user"))
        else:
            try:
                visit(fd, Path(), info.st_dev)
            except OSError as exc:
                error(root, exc)
    finally:
        os.close(fd)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete stale cache files (default: preview)")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("This cleanup is restricted to macOS")
    if os.geteuid() == 0:
        parser.error("Run as your normal user, never with sudo")
    result = cleanup(Path.home(), apply=args.apply)
    mode = "APPLY" if args.apply else "PREVIEW"
    print(
        f"{mode}: eligible={result.eligible_files}, deleted={result.deleted_files}, "
        f"allocated MiB={result.allocated_bytes / (1024 * 1024):.2f}, "
        f"skipped={result.skipped_files}, errors={result.errors}"
    )
    print("Allocated size is not a guarantee of disk space freed; directories are retained.")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
