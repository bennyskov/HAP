import contextlib
import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.disk_cleanup import DAY, cleanup, main


class DiskCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.cache = self.home / "Library" / "Caches"
        self.cache.mkdir(parents=True)
        self.now = time.time() + 60 * DAY

    def cache_file(self, name: str, age: float) -> Path:
        path = self.cache / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("cache")
        os.utime(path, (self.now - age * DAY, self.now - age * DAY))
        return path

    def test_should_preview_without_deleting_when_apply_is_absent(self) -> None:
        path = self.cache_file("app/old", 31)
        result = cleanup(self.home, now=self.now)
        self.assertEqual((result.eligible_files, result.deleted_files, path.exists()), (1, 0, True))

    def test_should_apply_separate_retention_thresholds_and_keep_directories(self) -> None:
        stale = [self.cache_file("pip/old", 8), self.cache_file("Homebrew/old", 8),
                 self.cache_file("app/old", 31)]
        retained = [self.cache_file("pip/boundary", 7), self.cache_file("Homebrew/new", 6),
                    self.cache_file("app/boundary", 30), self.cache_file("app/new", 8)]
        result = cleanup(self.home, apply=True, now=self.now)
        self.assertEqual(
            (result.deleted_files, result.errors, [p.exists() for p in stale],
             [p.exists() for p in retained], (self.cache / "app").is_dir()),
            (3, 0, [False] * 3, [True] * 4, True),
        )

    def test_should_retain_recently_accessed_files(self) -> None:
        accessed = self.cache_file("app/accessed", 31)
        os.utime(accessed, (self.now - DAY, self.now - 31 * DAY))
        result = cleanup(self.home, apply=True, now=self.now)
        self.assertEqual((result.deleted_files, accessed.exists()), (0, True))

    def test_should_retain_recently_changed_files_despite_old_mtime(self) -> None:
        changed = self.cache_file("app/changed", 100)
        result = cleanup(self.home, apply=True, now=time.time())
        self.assertEqual((result.deleted_files, changed.exists()), (0, True))

    def test_should_skip_links_and_protected_content(self) -> None:
        outside = self.home / "keep"
        outside.write_text("keep")
        os.utime(outside, (self.now - 40 * DAY, self.now - 40 * DAY))
        (self.cache / "linked-file").symlink_to(outside)
        (self.cache / "linked-directory").symlink_to(self.home, target_is_directory=True)
        hardlink = self.cache / "hardlink"
        os.link(outside, hardlink)
        protected = self.cache_file("app/credentials/keep", 40)
        result = cleanup(self.home, apply=True, now=self.now)
        self.assertEqual(
            (result.deleted_files, outside.exists(), hardlink.exists(), protected.exists()),
            (0, True, True, True),
        )

    def test_should_refuse_symlinked_cache_ancestor(self) -> None:
        other_home = self.home / "other"
        other_home.mkdir()
        (other_home / "Library").symlink_to(self.home / "Library", target_is_directory=True)
        keep = self.cache_file("app/keep", 40)
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            result = cleanup(other_home, apply=True, now=self.now)
        self.assertEqual((result.errors, keep.exists()), (1, True))
        self.assertIn("ERROR:", errors.getvalue())

    def test_should_report_deletion_failure(self) -> None:
        keep = self.cache_file("app/keep", 40)
        with patch("scripts.disk_cleanup.os.unlink", side_effect=PermissionError("denied")):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                result = cleanup(self.home, apply=True, now=self.now)
        self.assertEqual((result.errors, result.deleted_files, keep.exists()), (1, 0, True))
        self.assertIn("denied", errors.getvalue())

    def test_should_retain_files_changed_since_scan(self) -> None:
        keep = self.cache_file("app/keep", 40)
        original_stat = os.stat

        def changed_stat(path: str, *, dir_fd: int, follow_symlinks: bool) -> os.stat_result:
            keep.write_text("new cache content")
            return original_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

        with patch("scripts.disk_cleanup.os.stat", side_effect=changed_stat):
            result = cleanup(self.home, apply=True, now=self.now)
        self.assertEqual((result.deleted_files, result.errors, keep.read_text()), (0, 0, "new cache content"))

    def test_should_skip_missing_cache_directory_explicitly(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = cleanup(self.home / "missing")
        self.assertEqual((result.errors, result.deleted_files), (0, 0))
        self.assertIn("SKIP:", output.getvalue())

    def test_should_return_failure_from_cli_when_cleanup_fails(self) -> None:
        self.cache_file("app/keep", 40)
        with patch("scripts.disk_cleanup.sys.platform", "darwin"), \
                patch("scripts.disk_cleanup.Path.home", return_value=self.home), \
                patch("scripts.disk_cleanup.time.time", return_value=self.now), \
                patch("scripts.disk_cleanup.os.unlink", side_effect=PermissionError("denied")), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--apply"]), 1)


if __name__ == "__main__":
    unittest.main()
