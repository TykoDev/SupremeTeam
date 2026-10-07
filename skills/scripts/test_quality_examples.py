"""Execute documented parity examples against disposable, complete fixtures."""
from contextlib import chdir, redirect_stdout
import io
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest import mock

import check_parity
from test_check_parity import CATALOG, FULL_APP, INVENTORY, MOCK

SKILLS = Path(__file__).resolve().parents[1]


class QualityExampleTests(unittest.TestCase):
    def test_parity_examples_use_real_run_inputs_and_outputs(self):
        docs = ("design/design-mapper/references/examples.md", "design/prototyper/references/workflow.md")
        count = 0
        for document in docs:
            text = (SKILLS / document).read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.startswith("python skills/scripts/check_parity.py --"):
                    continue
                with self.subTest(document=document, command=line), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve()
                    args = shlex.split(line.replace("{run-id}", "doc-fixture"))[2:]
                    paths = {flag: root / args[args.index(flag) + 1] for flag in ("--inventory", "--app", "--components", "--out")}
                    for path in paths.values():
                        self.assertTrue(path.is_relative_to(root / "skillset-saves" / "runs" / "doc-fixture"))
                        path.parent.mkdir(parents=True, exist_ok=True)
                    paths["--inventory"].write_text(json.dumps(INVENTORY), encoding="utf-8")
                    paths["--components"].write_text(CATALOG, encoding="utf-8")
                    level = args[args.index("--level") + 1]
                    paths["--app"].write_text(MOCK if level == "mock" else FULL_APP, encoding="utf-8")
                    with chdir(root), mock.patch.object(sys, "argv", ["check_parity.py", *args]), redirect_stdout(io.StringIO()):
                        self.assertEqual(check_parity.main(), 0)
                    record = json.loads(paths["--out"].read_text(encoding="utf-8"))
                    self.assertEqual(record["result"]["status"], "pass")
                    self.assertTrue(all(entry["path"].startswith("skillset-saves/runs/doc-fixture/") for entry in record["inputs"]))
                    count += 1
        self.assertEqual(count, 4, "documented commands must not silently disappear")

    def test_reviewer_toc_example_matches_its_stated_deduction(self):
        text = (SKILLS / "skill-maker/skill-reviewer/references/examples.md").read_text(encoding="utf-8")
        self.assertIn("deducts D5 −1", text)
        self.assertIn("D5 9 → 10", text)
        self.assertIn("Progressive disclosure   | 9/10", text)
