import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from src import status_report


ROOT = Path(__file__).resolve().parent.parent


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href is not None:
                self.links.add(href)


def links_in(path: Path) -> set[str]:
    parser = LinkCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.links


class StatusReportPathsTest(unittest.TestCase):
    def test_should_write_default_report_under_www(self) -> None:
        sections = [status_report.Section("Test status", status_report.STATUS_OK)]
        with (
            patch.object(sys, "argv", ["status_report.py"]),
            patch.object(status_report, "build_sections", return_value=sections),
            patch.object(Path, "mkdir", autospec=True) as mkdir,
            patch.object(Path, "write_text", autospec=True) as write_text,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = status_report.main()

        self.assertEqual(result, 0)
        mkdir.assert_called_once_with(ROOT / "www", parents=True, exist_ok=True)
        self.assertEqual(write_text.call_args.args[0], ROOT / "www" / "status-report.html")
        self.assertIn("HAP Workspace Status", write_text.call_args.args[1])
        self.assertEqual(write_text.call_args.kwargs, {"encoding": "utf-8"})

    def test_should_allow_an_explicit_output_path(self) -> None:
        sections = [status_report.Section("Test status", status_report.STATUS_OK)]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "custom.html"
            with (
                patch.object(sys, "argv", ["status_report.py", "--output", str(output)]),
                patch.object(status_report, "build_sections", return_value=sections),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = status_report.main()

            self.assertEqual(result, 0)
            self.assertIn("HAP Workspace Status", output.read_text(encoding="utf-8"))

    def test_should_link_home_and_architecture_to_their_new_locations(self) -> None:
        home_links = links_in(ROOT / "www" / "index.html")
        architecture_links = links_in(ROOT / "www" / "architecture.html")

        self.assertTrue({
            "architecture.html",
            "status-report.html",
            "status_report_backup.html",
        }.issubset(home_links))
        self.assertTrue({
            "index.html",
            "architecture.html",
            "status-report.html",
            "status_report_backup.html",
        }.issubset(architecture_links))


class WebGitIgnoreTest(unittest.TestCase):
    def test_should_leave_www_content_visible_without_changing_other_ignores(self) -> None:
        web_paths = [
            "www/index.html",
            "www/architecture.html",
            "www/status-report.html",
            "www/status_report_backup.html",
            "www/nested/snapshot.log",
            "www/nested/snapshot.tmp",
            "www/logs/summary.html",
            "www/nested/venv/example",
            "www/nested/.env",
            "www/credentials/example.key",
        ]
        outside_paths = ["web-ignore-probe.log", "web-ignore-probe.tmp"]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            cwd=ROOT,
            input="\n".join(web_paths + outside_paths) + "\n",
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), set(outside_paths))


if __name__ == "__main__":
    unittest.main()
