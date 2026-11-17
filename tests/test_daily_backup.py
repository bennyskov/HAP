import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import call, patch

from src.daily_backup import ICLOUD_HELPER, archive_backup, copy_changed_files, main, make_icloud_only, time_machine
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


class ArchiveTests(unittest.TestCase):
    def test_should_archive_nested_hidden_entries_and_retain_latest_five(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, volume = root / "source", root / "volume"
            source.mkdir()
            volume.mkdir()
            (source / ".skip").write_text("excluded")
            (source / ".hidden").mkdir()
            (source / ".hidden" / ".nested").write_text("included")
            (source / "empty").mkdir()
            old_file = source / "old"
            old_file.write_text("old")
            os.utime(old_file, (1, 1))
            destination = volume / "archives"
            with patch("src.daily_backup.os.path.ismount", return_value=True):
                for _ in range(6):
                    self.assertEqual(archive_backup(source, destination, volume).status, STATUS_OK)
            archives = sorted(destination.glob("*.zip"))
            self.assertEqual(len(archives), 5)
            with zipfile.ZipFile(archives[-1]) as archive:
                self.assertEqual(set(archive.namelist()), {".hidden/", ".hidden/.nested", "empty/", "old"})
                self.assertEqual(archive.read(".hidden/.nested"), b"included")
                self.assertEqual(archive.getinfo("old").date_time[0], 1980)

    def test_should_preserve_symlinks_without_following_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, volume = root / "source", root / "volume"
            source.mkdir()
            volume.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "private").write_text("outside")
            (source / "directory-link").symlink_to(outside, target_is_directory=True)
            (source / "file-link").symlink_to(outside / "private")
            destination = volume / "archives"
            with patch("src.daily_backup.os.path.ismount", return_value=True):
                result = archive_backup(source, destination, volume)
            self.assertEqual(result.status, STATUS_OK)
            with zipfile.ZipFile(next(destination.glob("*.zip"))) as archive:
                self.assertEqual(set(archive.namelist()), {"directory-link", "file-link"})
                for name, target in (("directory-link", outside), ("file-link", outside / "private")):
                    self.assertTrue(stat.S_ISLNK(archive.getinfo(name).external_attr >> 16))
                    self.assertEqual(os.fsdecode(archive.read(name)), str(target))

    def test_should_keep_previous_archives_when_source_has_special_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, volume = root / "source", root / "volume"
            source.mkdir()
            volume.mkdir()
            destination = volume / "archives"
            with patch("src.daily_backup.os.path.ismount", return_value=True):
                self.assertEqual(archive_backup(source, destination, volume).status, STATUS_OK)
                previous = list(destination.iterdir())
                os.mkfifo(source / "pipe")
                self.assertEqual(archive_backup(source, destination, volume).status, STATUS_ERROR)
            self.assertEqual(list(destination.iterdir()), previous)

    def test_should_not_create_archive_when_volume_is_unmounted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, volume = root / "source", root / "volume"
            source.mkdir()
            volume.mkdir()
            destination = volume / "archives"
            with patch("src.daily_backup.os.path.ismount", return_value=False):
                result = archive_backup(source, destination, volume)
            self.assertEqual((result.status, destination.exists()), (STATUS_ERROR, False))


class ICloudOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.source = root / "source"
        self.volume = root / "volume"
        self.destination = self.volume / "backup"
        self.source.mkdir()
        self.destination.mkdir(parents=True)
        self.mount = patch("src.daily_backup.os.path.ismount", return_value=True)
        self.mount.start()
        self.addCleanup(self.mount.stop)

    def run_step(self) -> Section:
        return make_icloud_only(self.source, self.destination, self.volume)

    def test_should_evict_only_a_verified_local_file_and_leave_cloud_only_untouched(self) -> None:
        (self.source / "local").write_bytes(b"same")
        (self.destination / "local").write_bytes(b"same")
        (self.source / "cloud").write_bytes(b"not read")

        def operation(mode: str, items: list[dict]) -> list[dict]:
            if mode == "inspect":
                return [{"status": "eligible" if Path(i["path"]).name == "local" else "cloud_only", "detail": ""}
                        for i in items]
            self.assertEqual([Path(i["path"]).name for i in items], ["local"])
            self.assertEqual(len(items[0]["identity"]), 5)
            return [{"status": "evicted", "detail": ""}]

        with patch("src.daily_backup._icloud_operation", side_effect=operation):
            result = self.run_step()
        self.assertEqual(result.status, STATUS_OK)
        self.assertEqual({row.label: row.value for row in result.rows}["Eviction requests accepted"], "1")
        self.assertEqual({row.label: row.value for row in result.rows}["Already cloud-only"], "1")

    def test_should_retain_files_with_unsafe_state_or_mismatched_backup(self) -> None:
        for name in ("unsafe", "mismatch"):
            (self.source / name).write_bytes(b"source")
            (self.destination / name).write_bytes(b"backup")

        def operation(mode: str, items: list[dict]) -> list[dict]:
            self.assertEqual(mode, "inspect")
            return [{"status": "unsafe" if Path(i["path"]).name == "unsafe" else "eligible",
                     "detail": "sync incomplete"} for i in items]

        with patch("src.daily_backup._icloud_operation", side_effect=operation):
            result = self.run_step()
        self.assertEqual(result.status, STATUS_ERROR)
        self.assertEqual({row.label: row.value for row in result.rows}["Errors"], "2")
        self.assertEqual((self.source / "mismatch").read_bytes(), b"source")

    def test_should_report_failure_or_change_detected_by_eviction_helper(self) -> None:
        (self.source / "file").write_bytes(b"same")
        (self.destination / "file").write_bytes(b"same")
        with patch("src.daily_backup._icloud_operation", side_effect=[
            [{"status": "eligible", "detail": ""}],
            [{"status": "unsafe", "detail": "File changed after backup verification"}],
        ]):
            result = self.run_step()
        self.assertEqual(result.status, STATUS_ERROR)
        self.assertTrue(any("changed" in row.value for row in result.rows))

    def test_should_not_evict_when_file_changes_during_backup_verification(self) -> None:
        source = self.source / "file"
        source.write_bytes(b"same")
        (self.destination / "file").write_bytes(b"same")
        from hashlib import file_digest

        def change_source(file, algorithm):
            digest = file_digest(file, algorithm)
            source.write_bytes(b"changed")
            return digest

        with patch("src.daily_backup._icloud_operation", return_value=[{"status": "eligible", "detail": ""}]) as operation, \
                patch("src.daily_backup.hashlib.file_digest", side_effect=change_source):
            result = self.run_step()
        self.assertEqual(result.status, STATUS_ERROR)
        operation.assert_called_once()

    def test_should_skip_links_and_placeholders_without_calling_icloud(self) -> None:
        (self.source / "link").symlink_to(self.destination, target_is_directory=True)
        (self.source / ".missing.icloud").write_bytes(b"placeholder")
        with patch("src.daily_backup._icloud_operation") as operation:
            result = self.run_step()
        self.assertEqual(result.status, STATUS_WARN)
        self.assertEqual({row.label: row.value for row in result.rows}["Skipped entries"], "2")
        operation.assert_not_called()

    def test_should_report_helper_failure(self) -> None:
        (self.source / "file").write_bytes(b"same")
        with patch("src.daily_backup._icloud_operation", side_effect=RuntimeError("helper failed")):
            result = self.run_step()
        self.assertEqual(result.status, STATUS_ERROR)
        self.assertTrue(any("helper failed" in row.value for row in result.rows))

    @unittest.skipUnless(sys.platform == "darwin" and Path("/usr/bin/swift").exists(), "macOS Swift required")
    def test_should_refuse_to_evict_ordinary_local_file(self) -> None:
        local = self.source / "ordinary"
        local.write_text("keep")
        info = local.stat()
        identity = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        for mode, expected_identity in (("inspect", None), ("evict", identity), ("evict", [0] * 5)):
            result = subprocess.run(
                ["/usr/bin/swift", str(ICLOUD_HELPER), mode],
                input=json.dumps([{"path": str(local), "identity": expected_identity}]),
                capture_output=True, text=True, check=True, timeout=60,
            )
            self.assertEqual(json.loads(result.stdout)[0]["status"], "unsafe")
        self.assertEqual(local.read_text(), "keep")


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
    def test_should_write_default_backup_dashboard_under_www(self) -> None:
        output = Path(__file__).resolve().parent.parent / "www" / "status_report_backup.html"
        with (
            patch("src.daily_backup.sys.platform", "darwin"),
            patch("src.daily_backup.os.geteuid", return_value=501),
            patch("src.daily_backup.time_machine", return_value=Section("Time Machine", STATUS_WARN)),
            patch("src.daily_backup.copy_changed_files", return_value=Section("Files", STATUS_WARN)),
            patch.object(Path, "mkdir", autospec=True) as mkdir,
            patch.object(Path, "write_text", autospec=True) as write_text,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(["--status-only"])

        self.assertEqual(result, 0)
        mkdir.assert_called_once_with(output.parent, parents=True, exist_ok=True)
        self.assertEqual(write_text.call_args.args[0], output)
        self.assertIn("HAP Daily Backup Status", write_text.call_args.args[1])
        self.assertEqual(write_text.call_args.kwargs, {"encoding": "utf-8"})

    def test_should_generate_error_dashboard_and_continue_copy_after_time_machine_failure(self) -> None:
        failure = Section("Time Machine", STATUS_OK)
        failure.add("Manual start", "<denied>", STATUS_ERROR, "Not authorized")
        copy = Section("iCloud file backup", STATUS_OK)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "status_report_backup.html"
            with patch("src.daily_backup.sys.platform", "darwin"), \
                    patch("src.daily_backup.time_machine", return_value=failure) as tm, \
                    patch("src.daily_backup.copy_changed_files", return_value=copy) as files, \
                    patch("src.daily_backup.archive_backup", return_value=Section("Archive", STATUS_OK)) as archive, \
                    patch("src.daily_backup.make_icloud_only") as offload, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--output", str(output)])
            dashboard = output.read_text()
        self.assertEqual(result, 1)
        tm.assert_called_once_with(start=True)
        self.assertTrue(files.call_args.kwargs["apply"])
        archive.assert_called_once()
        offload.assert_not_called()
        self.assertIn("HAP Daily Backup Status", dashboard)
        self.assertIn("&lt;denied&gt;", dashboard)
        self.assertIn("ERROR", dashboard)

    def test_should_keep_existing_workspace_dashboard_defaults(self) -> None:
        dashboard = render_html([Section("Example", STATUS_OK)])
        self.assertIn("<title>HAP Status Report</title>", dashboard)
        self.assertIn("<h1>HAP Workspace Status</h1>", dashboard)

    def test_should_report_archive_failure_after_writing_dashboard(self) -> None:
        archive_failure = Section("Archive", STATUS_ERROR)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.html"
            with patch("src.daily_backup.sys.platform", "darwin"), \
                    patch("src.daily_backup.os.geteuid", return_value=501), \
                    patch("src.daily_backup.time_machine", return_value=Section("Time Machine", STATUS_OK)), \
                    patch("src.daily_backup.copy_changed_files", return_value=Section("Files", STATUS_OK)), \
                    patch("src.daily_backup.archive_backup", return_value=archive_failure), \
                    patch("src.daily_backup.make_icloud_only") as offload, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--output", str(output)])
            self.assertTrue(output.is_file())
        self.assertEqual(result, 1)
        offload.assert_not_called()

    def test_should_run_icloud_only_after_successful_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.html"
            with patch("src.daily_backup.sys.platform", "darwin"), \
                    patch("src.daily_backup.os.geteuid", return_value=501), \
                    patch("src.daily_backup.time_machine", return_value=Section("Time Machine", STATUS_WARN)), \
                    patch("src.daily_backup.copy_changed_files", return_value=Section("Files", STATUS_WARN)), \
                    patch("src.daily_backup.archive_backup", return_value=Section("Archive", STATUS_OK)), \
                    patch("src.daily_backup.make_icloud_only", return_value=Section("iCloud", STATUS_OK)) as offload, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--output", str(output)])
        self.assertEqual(result, 0)
        offload.assert_called_once()

    def test_should_not_start_or_copy_when_cli_requests_status_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "status_report_backup.html"
            with patch("src.daily_backup.sys.platform", "darwin"), \
                    patch("src.daily_backup.time_machine", return_value=Section("Time Machine", STATUS_WARN)) as tm, \
                    patch("src.daily_backup.copy_changed_files", return_value=Section("Files", STATUS_WARN)) as files, \
                    patch("src.daily_backup.archive_backup") as archive, \
                    patch("src.daily_backup.make_icloud_only") as offload, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--status-only", "--output", str(output)])
            self.assertTrue(output.is_file())
        self.assertEqual(result, 0)
        tm.assert_called_once_with(start=False)
        self.assertFalse(files.call_args.kwargs["apply"])
        archive.assert_not_called()
        offload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
