"""The prose that sends people and agents to the packager and the optimizer, checked against the tools.

Both documents live in a checkout, not in an installed copy of the skill, so the
tests skip where they are absent.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CREATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CREATOR))
from scripts import package_skill  # noqa: E402

SKILLS = CREATOR.parents[1]
REPO = SKILLS.parent
QUICK_START = REPO / "QUICK-START.md"
STAGE_5_HANDOFFS = (SKILLS / "skill-maker" / "SKILL.md", SKILLS / "skill-maker" / "references" / "handoff-templates.md")
RESOLVER = SKILLS / "scripts" / "output_paths.py"


@unittest.skipUnless(QUICK_START.is_file(), "QUICK-START.md is not part of an installed skill")
class PrerequisiteTests(unittest.TestCase):
    def test_quick_start_lists_the_claude_cli_as_the_optimizers_prerequisite(self):
        prerequisites = QUICK_START.read_text(encoding="utf-8").split("## 1.")[0]
        for needle in ("`claude` CLI", "PATH", "signed in", "paid"):
            self.assertIn(needle, prerequisites)


@unittest.skipUnless(RESOLVER.is_file() and all(path.is_file() for path in STAGE_5_HANDOFFS), "needs the whole skills tree")
class PackageHandoffTests(unittest.TestCase):
    """The resolver prints the archive's file path and the packager takes a directory."""

    def test_the_documented_output_directory_is_the_parent_of_the_path_the_resolver_prints(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            process = subprocess.run(
                [sys.executable, str(RESOLVER), "--project-root", str(project), "--run-id", "2026-01-01_demo_abc123",
                 "--phase", "skill-creation", "--kind", "packages", "--name", "demo.skill"],
                capture_output=True, text=True, encoding="utf-8", check=True,
            )
            printed = Path(json.loads(process.stdout)["path"])
            self.assertEqual(printed.suffix, ".skill", "the resolver's path names the archive, not a directory")

            skill = project / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Does a thing\n---\nbody\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                archive = package_skill.package_skill(skill, printed.parent)
            self.assertEqual(archive, printed)

    def test_both_stage_5_handoffs_say_so(self):
        for path in STAGE_5_HANDOFFS:
            with self.subTest(file=path.name):
                text = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("parent of the `path`", text)
                self.assertIn("absolute", text.lower())


if __name__ == "__main__":
    unittest.main()
