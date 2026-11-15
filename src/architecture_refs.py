"""Check that architecture.html step references match the HAP skill files.

Each referenced element carries data-skill, data-section, data-step (optional)
and data-name. The skill heading/step with that number must exist and have the
same name, and every numbered step of a referenced section must be on the page.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADING_RE = re.compile(r"^#+\s+\*\*(\d+(?:\.\d+)*)\.?\s+(.+?)\*\*")
STEP_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*")


def normalize(name: str) -> str:
    return " ".join(name.strip().rstrip(":").split()).casefold()


def parse_skill(text: str) -> dict[str, tuple[str, dict[str, str]]]:
    """Return {section: (title, {step: name})} for numbered bold headings."""
    sections: dict[str, tuple[str, dict[str, str]]] = {}
    current: dict[str, str] | None = None
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            current = {}
            sections[heading.group(1)] = (heading.group(2), current)
            continue
        step = STEP_RE.match(line)
        if step and current is not None:
            current[step.group(1)] = step.group(2)
    return sections


class _RefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: v or "" for k, v in attrs}
        if "data-skill" in data:
            self.refs.append(data)


def collect_refs(html: str) -> list[dict[str, str]]:
    parser = _RefCollector()
    parser.feed(html)
    return parser.refs


def check(page: Path, skills_dir: Path) -> list[str]:
    errors: list[str] = []
    refs = collect_refs(page.read_text(encoding="utf-8"))
    if not refs:
        return [f"{page.name}: no data-skill references found"]

    cache: dict[str, dict[str, tuple[str, dict[str, str]]]] = {}
    seen_steps: dict[tuple[str, str], set[str]] = {}

    for ref in refs:
        skill = ref.get("data-skill", "")
        section = ref.get("data-section", "")
        step = ref.get("data-step", "")
        name = ref.get("data-name", "")
        label = f"{skill} {section}" + (f" step {step}" if step else "")

        if skill not in cache:
            path = skills_dir / skill / "SKILL.md"
            if not path.is_file():
                errors.append(f"{label}: skill file {path} not found")
                cache[skill] = {}
                continue
            cache[skill] = parse_skill(path.read_text(encoding="utf-8"))
        sections = cache[skill]
        if not sections:
            continue

        if section not in sections:
            errors.append(f"{label}: section {section} not found")
            continue
        title, steps = sections[section]

        if not step:
            if normalize(name) != normalize(title):
                errors.append(f"{label}: name '{name}' != heading '{title}'")
            continue

        seen_steps.setdefault((skill, section), set()).add(step)
        if step not in steps:
            errors.append(f"{label}: step not found")
        elif normalize(name) != normalize(steps[step]):
            errors.append(f"{label}: name '{name}' != skill step '{steps[step]}'")

    for (skill, section), seen in sorted(seen_steps.items()):
        steps = cache.get(skill, {}).get(section, ("", {}))[1]
        for missing in sorted(set(steps) - seen, key=int):
            errors.append(
                f"{skill} {section} step {missing} ('{steps[missing]}') missing from {page.name}"
            )
    return errors


def main() -> int:
    page = ROOT / "architecture.html"
    errors = check(page, ROOT / ".github" / "skills")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        return 1
    print(f"OK {page.name}: all references match the skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
