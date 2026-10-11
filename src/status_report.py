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
class Section:
    """One card in the dashboard."""

    title: str
    status: str
    rows: list[tuple[str, str]] = field(default_factory=list)
    note: str | None = None


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
    rows = [
        ("Hostname", socket.gethostname()),
        ("System", f"{platform.system()} {platform.release()}"),
        ("Machine", platform.machine()),
    ]
    if platform.system() == "Darwin":
        sw_vers = run(["sw_vers", "-productVersion"])
        if sw_vers and sw_vers.returncode == 0:
            rows.append(("macOS version", sw_vers.stdout.strip()))

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    rows.append(("Uptime", str(timedelta(seconds=int(uptime.total_seconds())))))

    cpu_count = psutil.cpu_count(logical=True) or 1
    try:
        load1, load5, load15 = os.getloadavg()
        rows.append(("Load average (1/5/15m)", f"{load1:.2f} / {load5:.2f} / {load15:.2f}"))
    except (AttributeError, OSError):
        load1 = 0.0

    mem = psutil.virtual_memory()
    rows.append(("Memory used", f"{mem.percent:.0f}% of {mem.total / 1e9:.1f} GB"))

    status = STATUS_OK
    if mem.percent >= 90 or load1 >= cpu_count * 2:
        status = STATUS_WARN
    return Section("OS Status", status, rows)


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
    rows: list[tuple[str, str]] = []
    status = STATUS_OK
    try:
        partitions = psutil.disk_partitions(all=False)
    except OSError:
        return Section("Disk Status", STATUS_ERROR, [], note="Unable to read disk partitions.")

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
        part_status = STATUS_OK
        if percent >= 90:
            part_status = STATUS_ERROR
        elif percent >= 80:
            part_status = STATUS_WARN
        status = worst(status, part_status)
        label = "Macintosh HD (Data)" if part.mountpoint == "/System/Volumes/Data" else part.mountpoint
        rows.append((
            f"{label} ({part.fstype})",
            f"{percent:.0f}% used — {usage.free / 1e9:.1f} GB free of {usage.total / 1e9:.1f} GB",
        ))

    if not rows:
        return Section("Disk Status", STATUS_WARN, [], note="No readable partitions found.")
    return Section("Disk Status", status, rows)


# ----------------------------------------------------------------------------
# Homebrew status
# ----------------------------------------------------------------------------
def get_brew_section() -> Section:
    if not shutil.which("brew"):
        return Section("Homebrew", STATUS_ERROR, [], note="brew not found on PATH.")

    env = brew_env()
    rows = []
    version = run(["brew", "--version"], env=env)
    if version and version.returncode == 0:
        rows.append(("Version", version.stdout.splitlines()[0].strip()))

    formulae = run(["brew", "list", "--formula"], env=env)
    casks = run(["brew", "list", "--cask"], env=env)
    formula_count = len(formulae.stdout.split()) if formulae and formulae.returncode == 0 else None
    cask_count = len(casks.stdout.split()) if casks and casks.returncode == 0 else None
    if formula_count is not None:
        rows.append(("Installed formulae", str(formula_count)))
    if cask_count is not None:
        rows.append(("Installed casks", str(cask_count)))

    outdated = run(["brew", "outdated", "--quiet"], timeout=60, env=env)
    status = STATUS_OK
    if outdated and outdated.returncode == 0:
        pending = [line for line in outdated.stdout.splitlines() if line.strip()]
        rows.append(("Outdated packages", str(len(pending)) if pending else "0 — up to date"))
        if pending:
            status = STATUS_WARN
    else:
        rows.append(("Outdated packages", "check failed"))
        status = STATUS_WARN

    return Section("Homebrew", status, rows)


# ----------------------------------------------------------------------------
# Python / venv status
# ----------------------------------------------------------------------------
def get_python_section() -> Section:
    rows = [
        ("Interpreter", sys.version.split()[0]),
        ("Executable", sys.executable),
    ]
    status = STATUS_OK
    for repo in TRACKED_REPOS:
        venv_path = PROJECTS_DIR / repo / ".venv"
        exists = venv_path.is_dir()
        rows.append((f"{repo} .venv", "present" if exists else "missing"))
        if not exists:
            status = STATUS_WARN
    return Section("Python / venv", status, rows)


# ----------------------------------------------------------------------------
# Hermes status
# ----------------------------------------------------------------------------
def get_hermes_section() -> Section:
    if not shutil.which("hermes"):
        return Section("Hermes", STATUS_ERROR, [], note="hermes command not found on PATH.")

    rows = []
    status = STATUS_OK

    version = run(["hermes", "--version"])
    if version and version.returncode == 0:
        first_line = version.stdout.splitlines()[0].strip() if version.stdout else "unknown"
        rows.append(("Version", first_line))
        up_to_date = "up to date" in version.stdout.lower()
        rows.append(("Update status", "up to date" if up_to_date else "update available"))
        if not up_to_date:
            status = STATUS_WARN
    else:
        rows.append(("Version", "unavailable"))
        status = STATUS_WARN

    hstatus = run(["hermes", "status"])
    if hstatus and hstatus.returncode == 0:
        out = hstatus.stdout
        for label, key in (("Model", "Model:"), ("Provider", "Provider:"), ("Gateway", "Gateway:"), ("Jobs", "Jobs:")):
            for line in out.splitlines():
                if key in line:
                    rows.append((label, line.split(key, 1)[1].strip()))
                    break
        if "running" not in out.lower():
            status = worst(status, STATUS_WARN)
    else:
        rows.append(("Gateway", "status check failed"))
        status = worst(status, STATUS_WARN)

    return Section("Hermes", status, rows)


# ----------------------------------------------------------------------------
# Git repo status (HAP / BUD / STRM)
# ----------------------------------------------------------------------------
def get_git_section() -> Section:
    rows = []
    status = STATUS_OK
    for repo in TRACKED_REPOS:
        repo_path = PROJECTS_DIR / repo
        if not repo_path.is_dir():
            rows.append((repo, "directory not found"))
            status = worst(status, STATUS_WARN)
            continue
        result = run(["git", "-C", str(repo_path), "status", "--short", "--branch"])
        if not result or result.returncode != 0:
            rows.append((repo, "not a git repo / status failed"))
            status = worst(status, STATUS_WARN)
            continue
        lines = result.stdout.splitlines()
        branch_line = lines[0] if lines else ""
        dirty_count = len(lines) - 1 if lines else 0
        repo_status = STATUS_OK
        details = branch_line.replace("## ", "")
        if dirty_count:
            details += f" — {dirty_count} changed file(s)"
            repo_status = STATUS_WARN
        if "ahead" in branch_line or "behind" in branch_line:
            repo_status = STATUS_WARN
        if "..." not in branch_line:
            details += " (no remote tracking)"
        status = worst(status, repo_status)
        rows.append((repo, details or "clean"))
    return Section("Git Repos", status, rows)


# ----------------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------------
STATUS_LABEL = {STATUS_OK: "OK", STATUS_WARN: "WARN", STATUS_ERROR: "ERROR"}

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #15181d; color: #e6e6e6; margin: 0; padding: 2rem; }
h1 { font-size: 1.4rem; margin-bottom: 0.2rem; }
.meta { color: #9aa4b2; margin-bottom: 1.5rem; font-size: 0.9rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
.card { background: #1e232b; border-radius: 10px; padding: 1rem 1.25rem; border-left: 5px solid #555; }
.card.ok { border-left-color: #3fb950; }
.card.warn { border-left-color: #d29922; }
.card.error { border-left-color: #f85149; }
.card h2 { margin: 0 0 0.6rem 0; font-size: 1.05rem; display: flex; justify-content: space-between; align-items: center; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 999px; letter-spacing: 0.05em; }
.badge.ok { background: rgba(63,185,80,0.15); color: #3fb950; }
.badge.warn { background: rgba(210,153,34,0.15); color: #d29922; }
.badge.error { background: rgba(248,81,73,0.15); color: #f85149; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; table-layout: fixed; }
td { padding: 0.25rem 0; vertical-align: top; overflow-wrap: anywhere; }
td.label { color: #9aa4b2; width: 40%; padding-right: 0.75rem; }
.note { color: #9aa4b2; font-size: 0.85rem; font-style: italic; }
"""


def render_card(section: Section) -> str:
    rows_html = "".join(
        f"<tr><td class='label'>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>"
        for label, value in section.rows
    )
    note_html = f"<p class='note'>{html.escape(section.note)}</p>" if section.note else ""
    badge = STATUS_LABEL[section.status]
    return f"""
    <div class="card {section.status}">
      <h2>{html.escape(section.title)} <span class="badge {section.status}">{badge}</span></h2>
      <table>{rows_html}</table>
      {note_html}
    </div>"""


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
    return 0 if overall != STATUS_ERROR else 1


if __name__ == "__main__":
    raise SystemExit(main())
