import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import architecture_refs  # noqa: E402

SKILL = """# **1. Skill Instructions**

## **1.3 Flow**

1. **First step:** do it
2. **Second step** — then this

```text
3. **Not a step** inside a fence
```

## **1.4 Decision flow**
"""


def node(section, name, step=None):
    step_attr = f' data-step="{step}"' if step else ""
    return (
        f'<a data-skill="demo" data-section="{section}"{step_attr} '
        f'data-name="{name}"></a>'
    )


class ArchitectureRefsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        skill_dir = self.root / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(SKILL, encoding="utf-8")

    def run_check(self, *nodes):
        page = self.root / "page.html"
        page.write_text("<main>" + "".join(nodes) + "</main>", encoding="utf-8")
        return architecture_refs.check(page, self.root / "skills")

    def test_real_architecture_page_matches_skills(self):
        errors = architecture_refs.check(
            ROOT / "architecture.html", ROOT / ".github" / "skills"
        )
        self.assertEqual(errors, [])

    def test_matching_references_pass(self):
        errors = self.run_check(
            node("1.3", "first step", 1),
            node("1.3", "Second step", 2),
            node("1.4", "Decision flow"),
        )
        self.assertEqual(errors, [])

    def test_renamed_step_fails(self):
        errors = self.run_check(node("1.3", "First step", 1), node("1.3", "Old name", 2))
        self.assertEqual(len(errors), 1)
        self.assertIn("'Old name' != skill step 'Second step'", errors[0])

    def test_missing_step_on_page_fails(self):
        errors = self.run_check(node("1.3", "First step", 1))
        self.assertEqual(errors, ["demo 1.3 step 2 ('Second step') missing from page.html"])

    def test_unknown_step_section_and_skill_fail(self):
        errors = self.run_check(
            node("1.3", "First step", 1),
            node("1.3", "Second step", 2),
            node("1.3", "Not a step", 3),
            node("9.9", "Nowhere"),
            '<a data-skill="missing" data-section="1.1" data-name="Purpose"></a>',
        )
        self.assertEqual(len(errors), 3)
        self.assertIn("step 3: step not found", errors[0])
        self.assertIn("section 9.9 not found", errors[1])
        self.assertIn("skill file", errors[2])

    def test_section_title_mismatch_fails(self):
        errors = self.run_check(node("1.4", "Other title"))
        self.assertEqual(len(errors), 1)
        self.assertIn("!= heading 'Decision flow'", errors[0])


if __name__ == "__main__":
    unittest.main()
