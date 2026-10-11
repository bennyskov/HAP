"""Generate a self-contained HTML status dashboard for the HAP workspace.

Collects read-only, non-destructive status for the local OS, disk usage,
Homebrew, Python/venv, Hermes, and the HAP/BUD/STRM git repos, then renders
everything into a single HTML file (no external assets, no network calls
beyond the local commands already used by hap-maintenance).

Usage:
    python3 src/status_report.py [--output PATH]

Default output: logs/status-report.html (git-ignored, regenerated each run).
"""

from __future__ import annotations

import argparse
import html
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT.parent
TRACKED_REPOS = ["HAP", "BUD", "STRM"]
DEFAULT_OUTPUT = REPO_ROOT / "logs" / "status-report.html"

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_ERROR = "error"


@dataclass
class Row:
    """One line in a card; status/reason mark the row that caused a WARN/ERROR."""

    label: str
    value: str
    status: str = "ok"
    reason: str = ""


@dataclass
class Section:
    """One card in the dashboard."""

    title: str
    status: str
    rows: list[Row] = field(default_factory=list)
    note: str | None = None

    def add(self, label: str, value: str, status: str = "ok", reason: str = "") -> None:
        self.rows.append(Row(label, value, status, reason))
        self.status = worst(self.status, status)


def run(cmd: list[str], timeout: int = 20, env: dict | None = None) -> subprocess.CompletedProcess | None:
    """Run a read-only command and return the result, or None if it fails."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False, env=env)
    except (OSError, subprocess.SubprocessError):
        return None


def brew_env() -> dict:
    """Environment for brew commands that forbids its own auto-update network call,
    keeping status checks strictly read-only."""
    env = os.environ.copy()
    env["HOMEBREW_NO_AUTO_UPDATE"] = "1"
    return env


def worst(*statuses: str) -> str:
    """Combine section statuses, escalating to the worst one found."""
    order = {STATUS_OK: 0, STATUS_WARN: 1, STATUS_ERROR: 2}
    return max(statuses, key=lambda s: order.get(s, 2)) if statuses else STATUS_OK


# ----------------------------------------------------------------------------
# OS status
# ----------------------------------------------------------------------------
def get_os_section() -> Section:
    section = Section("OS Status", STATUS_OK)
    section.add("Hostname", socket.gethostname())
    section.add("System", f"{platform.system()} {platform.release()}")
    section.add("Machine", platform.machine())
    if platform.system() == "Darwin":
        sw_vers = run(["sw_vers", "-productVersion"])
        if sw_vers and sw_vers.returncode == 0:
            section.add("macOS version", sw_vers.stdout.strip())

    uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
    section.add("Uptime", str(timedelta(seconds=int(uptime.total_seconds()))))

    cpu_count = psutil.cpu_count(logical=True) or 1
    try:
        load1, load5, load15 = os.getloadavg()
        load_limit = cpu_count * 2
        busy = load1 >= load_limit
        section.add(
            "Load average (1/5/15m)",
            f"{load1:.2f} / {load5:.2f} / {load15:.2f}",
            STATUS_WARN if busy else STATUS_OK,
            f"1-min load ≥ {load_limit} (2 × {cpu_count} CPUs)" if busy else "",
        )
    except (AttributeError, OSError):
        pass

    mem = psutil.virtual_memory()
    high_mem = mem.percent >= 90
    section.add(
        "Memory used",
        f"{mem.percent:.0f}% of {mem.total / 1e9:.1f} GB",
        STATUS_WARN if high_mem else STATUS_OK,
        "memory use ≥ 90%" if high_mem else "",
    )
    return section


# ----------------------------------------------------------------------------
# Disk status
# ----------------------------------------------------------------------------
def _is_noise_mount(mountpoint: str, fstype: str) -> bool:
    """Filter out macOS system-volume splits and sandboxed container mounts
    that duplicate or distort the real, user-relevant disk usage."""
    if fstype in {"autofs", "devfs", "nullfs"}:
        return True
    if mountpoint.startswith("/private/var/folders"):
        return True
    if mountpoint == "/Volumes/Recovery":
        return True
    if mountpoint.startswith("/System/Volumes/") and mountpoint != "/System/Volumes/Data":
        return True
    return False


def get_disk_section() -> Section:
    section = Section("Disk Status", STATUS_OK)
    try:
        partitions = psutil.disk_partitions(all=False)
    except OSError:
        section.status = STATUS_ERROR
        section.note = "Unable to read disk partitions."
        return section

    candidates = [p for p in partitions if not _is_noise_mount(p.mountpoint, p.fstype)]
    # On macOS, "/" is the read-only sealed system volume and "/System/Volumes/Data"
    # is the writable volume that actually holds user data; prefer Data when both exist.
    if any(p.mountpoint == "/System/Volumes/Data" for p in candidates):
        candidates = [p for p in candidates if p.mountpoint != "/"]

    for part in candidates:
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        percent = usage.percent
        if percent >= 90:
            part_status, reason = STATUS_ERROR, "≥ 90% full"
        elif percent >= 80:
            part_status, reason = STATUS_WARN, "≥ 80% full"
        else:
            part_status, reason = STATUS_OK, ""
        label = "Macintosh HD (Data)" if part.mountpoint == "/System/Volumes/Data" else part.mountpoint
        section.add(
            f"{label} ({part.fstype})",
            f"{percent:.1f}% used — {usage.free / 1e9:.1f} GB free of {usage.total / 1e9:.1f} GB",
            part_status,
            reason,
        )

    if not section.rows:
        section.status = STATUS_WARN
        section.note = "No readable partitions found."
    return section


# ----------------------------------------------------------------------------
# Homebrew status
# ----------------------------------------------------------------------------
def get_brew_section() -> Section:
    section = Section("Homebrew", STATUS_OK)
    if not shutil.which("brew"):
        section.status = STATUS_ERROR
        section.note = "brew not found on PATH."
        return section

    env = brew_env()
    version = run(["brew", "--version"], env=env)
    if version and version.returncode == 0:
        section.add("Version", version.stdout.splitlines()[0].strip())

    formulae = run(["brew", "list", "--formula"], env=env)
    casks = run(["brew", "list", "--cask"], env=env)
    if formulae and formulae.returncode == 0:
        section.add("Installed formulae", str(len(formulae.stdout.split())))
    if casks and casks.returncode == 0:
        section.add("Installed casks", str(len(casks.stdout.split())))

    outdated = run(["brew", "outdated", "--quiet"], timeout=60, env=env)
    if outdated and outdated.returncode == 0:
        pending = [line.strip() for line in outdated.stdout.splitlines() if line.strip()]
        if pending:
            section.add("Outdated packages", f"{len(pending)} — {', '.join(pending)}",
                        STATUS_WARN, "upgrades available")
        else:
            section.add("Outdated packages", "0 — up to date")
    else:
        section.add("Outdated packages", "check failed", STATUS_WARN, "brew outdated failed")
    return section


# ----------------------------------------------------------------------------
# Python / venv status
# ----------------------------------------------------------------------------
def get_python_section() -> Section:
    section = Section("Python / venv", STATUS_OK)
    section.add("Interpreter", sys.version.split()[0])
    section.add("Executable", sys.executable)
    for repo in TRACKED_REPOS:
        if (PROJECTS_DIR / repo / ".venv").is_dir():
            section.add(f"{repo} .venv", "present")
        else:
            section.add(f"{repo} .venv", "missing", STATUS_WARN, "no .venv in project")
    return section


# ----------------------------------------------------------------------------
# Hermes status
# ----------------------------------------------------------------------------
def get_hermes_section() -> Section:
    section = Section("Hermes", STATUS_OK)
    if not shutil.which("hermes"):
        section.status = STATUS_ERROR
        section.note = "hermes command not found on PATH."
        return section

    version = run(["hermes", "--version"])
    if version and version.returncode == 0:
        first_line = version.stdout.splitlines()[0].strip() if version.stdout else "unknown"
        section.add("Version", first_line)
        if "up to date" in version.stdout.lower():
            section.add("Update status", "up to date")
        else:
            section.add("Update status", "update available", STATUS_WARN, "newer Hermes available")
    else:
        section.add("Version", "unavailable", STATUS_WARN, "hermes --version failed")

    hstatus = run(["hermes", "status"])
    if hstatus and hstatus.returncode == 0:
        lines = hstatus.stdout.splitlines()
        for label, key in (("Model", "Model:"), ("Provider", "Provider:"), ("Gateway", "Gateway:"), ("Jobs", "Jobs:")):
            value = next((line.split(key, 1)[1].strip() for line in lines if key in line), None)
            if value is None:
                if label == "Gateway":
                    section.add("Gateway", "not reported", STATUS_WARN, "gateway state missing")
                continue
            if label == "Gateway" and "running" not in value.lower():
                section.add(label, value, STATUS_WARN, "gateway not running")
            else:
                section.add(label, value)
    else:
        section.add("Gateway", "status check failed", STATUS_WARN, "hermes status failed")
    return section


# ----------------------------------------------------------------------------
# Git repo status (HAP / BUD / STRM)
# ----------------------------------------------------------------------------
def get_git_section() -> Section:
    section = Section("Git Repos", STATUS_OK)
    for repo in TRACKED_REPOS:
        repo_path = PROJECTS_DIR / repo
        if not repo_path.is_dir():
            section.add(repo, "directory not found", STATUS_WARN, "repo folder missing")
            continue
        result = run(["git", "-C", str(repo_path), "status", "--short", "--branch"])
        if not result or result.returncode != 0:
            section.add(repo, "not a git repo / status failed", STATUS_WARN, "git status failed")
            continue
        lines = result.stdout.splitlines()
        branch_line = lines[0] if lines else ""
        dirty_count = len(lines) - 1 if lines else 0
        details = branch_line.replace("## ", "")
        reasons = []
        if dirty_count:
            details += f" — {dirty_count} changed file(s)"
            reasons.append("uncommitted changes")
        if "ahead" in branch_line or "behind" in branch_line:
            reasons.append("not in sync with remote")
        if "..." not in branch_line:
            details += " (no remote tracking)"
        section.add(repo, details or "clean", STATUS_WARN if reasons else STATUS_OK, ", ".join(reasons))
    return section


# ----------------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------------
STATUS_LABEL = {STATUS_OK: "OK", STATUS_WARN: "WARN", STATUS_ERROR: "ERROR"}
STATUS_ICON = {STATUS_WARN: "⚠", STATUS_ERROR: "✖"}

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #15181d; color: #e6e6e6; margin: 0; padding: 2rem; }
h1 { font-size: 1.4rem; margin-bottom: 0.2rem; }
.meta { color: #9aa4b2; margin-bottom: 1rem; font-size: 0.9rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
.card { background: #1e232b; border-radius: 10px; padding: 1rem 1.25rem; border-left: 5px solid #555; }
.card.ok { border-left-color: #3fb950; }
.card.warn { border-left-color: #d29922; }
.card.error { border-left-color: #f85149; }
.card h2 { margin: 0 0 0.6rem 0; font-size: 1.05rem; display: flex; justify-content: space-between; align-items: center; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 999px; letter-spacing: 0.05em; white-space: nowrap; }
.badge.ok { background: rgba(63,185,80,0.15); color: #3fb950; }
.badge.warn { background: rgba(210,153,34,0.15); color: #d29922; }
.badge.error { background: rgba(248,81,73,0.15); color: #f85149; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; table-layout: fixed; }
td { padding: 0.25rem 0.4rem; vertical-align: top; overflow-wrap: anywhere; }
td.label { color: #9aa4b2; width: 40%; }
tr.warn td { background: rgba(210,153,34,0.12); }
tr.error td { background: rgba(248,81,73,0.15); }
tr.warn td.label, tr.error td.label { font-weight: 600; }
tr.warn td.label { color: #d29922; box-shadow: inset 3px 0 0 #d29922; }
tr.error td.label { color: #f85149; box-shadow: inset 3px 0 0 #f85149; }
.reason { display: block; font-size: 0.75rem; margin-top: 0.15rem; }
tr.warn .reason { color: #d29922; }
tr.error .reason { color: #f85149; }
.note { color: #9aa4b2; font-size: 0.85rem; font-style: italic; }
.summary { background: #1e232b; border-radius: 10px; padding: 0.75rem 1.25rem; margin-bottom: 1.25rem; font-size: 0.9rem; }
.summary h2 { font-size: 0.95rem; margin: 0 0 0.4rem 0; }
.summary ul { margin: 0; padding-left: 1.2rem; }
.summary li { margin: 0.2rem 0; }
.summary li.warn { color: #d29922; }
.summary li.error { color: #f85149; }
.summary .ok { color: #3fb950; }
"""


def render_row(row: Row) -> str:
    icon = STATUS_ICON.get(row.status, "")
    label = f"{icon} {row.label}" if icon else row.label
    reason = (
        f"<span class='reason'>{STATUS_LABEL[row.status]}: {html.escape(row.reason)}</span>"
        if row.status != STATUS_OK else ""
    )
    return (
        f"<tr class='{row.status}'><td class='label'>{html.escape(label)}</td>"
        f"<td>{html.escape(row.value)}{reason}</td></tr>"
    )


def render_card(section: Section) -> str:
    rows_html = "".join(render_row(r) for r in section.rows)
    note_html = f"<p class='note'>{html.escape(section.note)}</p>" if section.note else ""
    badge = STATUS_LABEL[section.status]
    return f"""
    <div class="card {section.status}">
      <h2>{html.escape(section.title)} <span class="badge {section.status}">{badge}</span></h2>
      <table>{rows_html}</table>
      {note_html}
    </div>"""


def problems(sections: list[Section]) -> list[tuple[str, str]]:
    """List (status, message) for every row or card that is not OK, worst first."""
    found = []
    for s in sections:
        for r in s.rows:
            if r.status != STATUS_OK:
                found.append((r.status, f"{s.title} → {r.label}: {r.value} ({r.reason})"))
        if s.note and s.status != STATUS_OK:
            found.append((s.status, f"{s.title}: {s.note}"))
    return sorted(found, key=lambda p: 0 if p[0] == STATUS_ERROR else 1)


def render_summary(sections: list[Section]) -> str:
    items = problems(sections)
    if not items:
        return "<div class='summary'><span class='ok'>✔ All checks OK</span></div>"
    lis = "".join(
        f"<li class='{status}'>{STATUS_ICON[status]} <strong>{STATUS_LABEL[status]}</strong> "
        f"{html.escape(msg)}</li>"
        for status, msg in items
    )
    return f"<div class='summary'><h2>What is causing WARN / ERROR</h2><ul>{lis}</ul></div>"


def render_html(sections: list[Section]) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cards = "".join(render_card(s) for s in sections)
    overall = worst(*(s.status for s in sections))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>HAP Status Report</title>
<style>{CSS}</style>
</head>
<body>
<h1>HAP Workspace Status</h1>
<p class="meta">Generated {generated} on {socket.gethostname()} &middot; overall: <strong>{STATUS_LABEL[overall]}</strong></p>
{render_summary(sections)}
<div class="grid">{cards}</div>
</body>
</html>"""


def build_sections() -> list[Section]:
    return [
        get_os_section(),
        get_disk_section(),
        get_brew_section(),
        get_python_section(),
        get_hermes_section(),
        get_git_section(),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="HTML output path")
    args = parser.parse_args()

    sections = build_sections()
    output_html = render_html(sections)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_html, encoding="utf-8")
    print(f"Status report written to {args.output}")

    overall = worst(*(s.status for s in sections))
    for section in sections:
        print(f"  [{STATUS_LABEL[section.status]:>5}] {section.title}")
        for row in section.rows:
            if row.status != STATUS_OK:
                print(f"          -> {row.label}: {row.value} ({row.reason})")
    return 0 if overall != STATUS_ERROR else 1


if __name__ == "__main__":
    raise SystemExit(main())
