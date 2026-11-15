import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from src.daily_backup import copy_changed_files, main, time_machine
from src.status_report import Section, STATUS_ERROR, STATUS_OK, STATUS_WARN, render_html


class FileBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "iCloud" / "PRIVAT"
        self.volume = self.root / "volume"
        self.destination = self.volume / "PRIVAT"
        self.source.mkdir(parents=True)
        self.volume.mkdir()
        self.mount = patch("src.daily_backup.os.path.ismount", return_value=True)
        self.mount.start()
        self.addCleanup(self.mount.stop)

    def backup(self, *, apply: bool = True) -> Section:
        return copy_changed_files(self.source, self.destination, self.volume, apply=apply)

    def value(self, section: Section, label: str) -> str:
        return next(row.value for row in section.rows if row.label == label)

    def test_should_copy_new_and_touched_files_without_pruning_destination(self) -> None:
        folder = self.source / "nested"
        folder.mkdir()
        original = folder / "file"
        original.write_bytes(b"original")
        first = self.backup()
        self.assertEqual((first.status, self.value(first, "Copied files")), (STATUS_OK, "1"))
        target = self.destination / "nested" / "file"
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns),
                         (original.read_bytes(), original.stat().st_mtime_ns))
        destination_only = self.destination / "keep"
        destination_only.write_text("keep")
        second = self.backup()
        self.assertEqual((self.value(second, "Copied files"), self.value(second, "Unchanged files")), ("0", "1"))
        previous = original.stat()
        os.utime(original, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))
        touched = self.backup()
        self.assertEqual((self.value(touched, "Copied files"), destination_only.read_text()), ("1", "keep"))

    def test_should_copy_changed_size_even_when_mtime_is_preserved(self) -> None:
        original = self.source / "file"
        original.write_text("short")
        self.backup()
        previous = original.stat()
        original.write_text("longer content")
        os.utime(original, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        result = self.backup()
        self.assertEqual((result.status, (self.destination / "file").read_text()), (STATUS_OK, "longer content"))

    def test_should_only_inventory_files_in_status_only_mode(self) -> None:
        (self.source / "file").write_text("private")
        result = self.backup(apply=False)
        self.assertEqual(
            (result.status, self.value(result, "Changed or new files"), self.destination.exists()),
            (STATUS_WARN, "1", False),
        )

    def test_should_not_create_local_fallback_when_volume_is_unmounted(self) -> None:
        (self.source / "file").write_text("private")
        with patch("src.daily_backup.os.path.ismount", return_value=False):
            result = self.backup()
        self.assertEqual((result.status, self.destination.exists()), (STATUS_ERROR, False))

    def test_should_report_missing_source(self) -> None:
        result = copy_changed_files(self.root / "missing", self.destination, self.volume, apply=True)
        self.assertEqual((result.status, self.destination.exists()), (STATUS_ERROR, False))

    def test_should_skip_symlinks_and_cloud_placeholders_as_incomplete(self) -> None:
        outside = self.root / "outside"
        outside.write_text("keep")
        (self.source / "link").symlink_to(outside)
        (self.source / "directory").symlink_to(self.root, target_is_directory=True)
        (self.source / ".cloud-file.icloud").write_bytes(b"placeholder")
        result = self.backup()
        self.assertEqual(
            (result.status, self.value(result, "Skipped entries"), self.destination.exists()),
            (STATUS_WARN, "3", False),
        )

    def test_should_not_follow_destination_symlink(self) -> None:
        (self.source / "file").write_text("private")
        self.destination.mkdir()
        outside = self.root / "outside"
        outside.write_text("keep")
        (self.destination / "file").symlink_to(outside)
        result = self.backup()
        self.assertEqual((result.status, outside.read_text()), (STATUS_ERROR, "keep"))

    def test_should_retain_previous_backup_and_clean_staging_on_copy_failure(self) -> None:
        (self.source / "file").write_text("original")
        self.backup()
        (self.source / "file").write_text("new content")
        with patch("src.daily_backup.os.replace", side_effect=OSError("disk disconnected")):
            result = self.backup()
        self.assertEqual(
            (result.status, (self.destination / "file").read_text(),
             list(self.destination.glob(".hap-backup-*"))),
            (STATUS_ERROR, "original", []),
        )

    def test_should_retain_previous_backup_when_source_changes_during_copy(self) -> None:
        original = self.source / "file"
        original.write_text("original")
        self.backup()
        original.write_text("new content")
        real_fsync = os.fsync

        def change_source(fd: int) -> None:
            original.write_text("changed again while copying")
            real_fsync(fd)

        with patch("src.daily_backup.os.fsync", side_effect=change_source):
            result = self.backup()
        self.assertEqual(
            (result.status, (self.destination / "file").read_text(),
             list(self.destination.glob(".hap-backup-*"))),
            (STATUS_ERROR, "original", []),
        )


class TimeMachineTests(unittest.TestCase):
    def test_should_start_manually_then_verify_running_and_latest_backup(self) -> None:
        with patch("src.daily_backup._tmutil", side_effect=[
            "", "Running = 1; BackupPhase = Copying;", "/Volumes/backup/completed-backup",
        ]) as command:
            result = time_machine(start=True)
        self.assertEqual(command.call_args_list, [call("startbackup"), call("status"), call("latestbackup")])
        self.assertEqual(result.status, STATUS_WARN)
        self.assertTrue(any(row.label == "Current state" and "Running" in row.value for row in result.rows))

    def test_should_report_start_failure_and_still_check_status(self) -> None:
        with patch("src.daily_backup._tmutil", side_effect=[
            RuntimeError("not authorized"), "Running = 0;", "/Volumes/backup/previous",
        ]) as command:
            result = time_machine(start=True)
        self.assertEqual((result.status, command.call_count), (STATUS_ERROR, 3))

    def test_should_not_start_in_status_only_and_reject_unknown_status(self) -> None:
        with patch("src.daily_backup._tmutil", side_effect=["unknown output", RuntimeError("no backup")]) as command:
            result = time_machine(start=False)
        self.assertEqual(command.call_args_list, [call("status"), call("latestbackup")])
        self.assertEqual(result.status, STATUS_ERROR)

    def test_should_surface_actual_command_failure(self) -> None:
        failure = subprocess.CompletedProcess(["tmutil"], 1, "", "not authorized")
        with patch("src.daily_backup.subprocess.run", return_value=failure) as command:
            result = time_machine(start=True)
        self.assertEqual(result.status, STATUS_ERROR)
        self.assertEqual(command.call_args_list[0].args[0], ["/usr/bin/tmutil", "startbackup"])


class BackupDashboardTests(unittest.TestCase):
    def test_should_generate_error_dashboard_and_continue_copy_after_time_machine_failure(self) -> None:
        failure = Section("Time Machine", STATUS_OK)
        failure.add("Manual start", "<denied>", STATUS_ERROR, "Not authorized")
        copy = Section("iCloud file backup", STATUS_OK)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "status_report_backup.html"
            with patch("src.daily_backup.sys.platform", "darwin"), \
                    patch("src.daily_backup.time_machine", return_value=failure) as tm, \
                    patch("src.daily_backup.copy_changed_files", return_value=copy) as files, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--output", str(output)])
            dashboard = output.read_text()
        self.assertEqual(result, 1)
        tm.assert_called_once_with(start=True)
        self.assertTrue(files.call_args.kwargs["apply"])
        self.assertIn("HAP Daily Backup Status", dashboard)
        self.assertIn("&lt;denied&gt;", dashboard)
        self.assertIn("ERROR", dashboard)

    def test_should_keep_existing_workspace_dashboard_defaults(self) -> None:
        dashboard = render_html([Section("Example", STATUS_OK)])
        self.assertIn("<title>HAP Status Report</title>", dashboard)
        self.assertIn("<h1>HAP Workspace Status</h1>", dashboard)

    def test_should_not_start_or_copy_when_cli_requests_status_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "status_report_backup.html"
            with patch("src.daily_backup.sys.platform", "darwin"), \
                    patch("src.daily_backup.time_machine", return_value=Section("Time Machine", STATUS_WARN)) as tm, \
                    patch("src.daily_backup.copy_changed_files", return_value=Section("Files", STATUS_WARN)) as files, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--status-only", "--output", str(output)])
            self.assertTrue(output.is_file())
        self.assertEqual(result, 0)
        tm.assert_called_once_with(start=False)
        self.assertFalse(files.call_args.kwargs["apply"])


if __name__ == "__main__":
    unittest.main()
