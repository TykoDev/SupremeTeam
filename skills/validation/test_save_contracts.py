#!/usr/bin/env python3
"""The save path policy against the resolver and the documents that state it.

Every project kind the output path resolver offers lands under one of the two
generated roots save-ownership.yaml declares, and ownership.yaml,
save-ownership.yaml, pipelines.yaml, and save-protocol.md agree. The writer,
the resolver, the scan recorder, and the package check are tested beside their
code, in harness/hooks/test_run_state.py and scripts/test_output_paths.py,
test_scan_record.py, and test_package_check.py."""
from __future__ import annotations

import fnmatch
import tempfile
import unittest
from pathlib import Path

import _catalog
from output_paths import resolve

ROOT = _catalog.SKILLS


class GeneratedRootPolicyTests(unittest.TestCase):
    """Everything Supreme Team generates lands under skillset-saves/ or .harness-state/."""

    CASES = {
        "manifest": dict(run_id="r1", phase="redesign"),
        "phase_report": dict(run_id="r1", phase="review", name="review-packet.md"),
        "reports": dict(run_id="r1", phase="design", name="report_plan.md"),
        "artifacts": dict(run_id="r1", phase="redesign", name="variants/v1/app.html"),
        "evidence": dict(run_id="r1", phase="redesign", name="parity-v1.json"),
        "coverage": dict(run_id="r1", phase="build", name=".coverage"),
        "packages": dict(run_id="r1", phase="skill-creation", name="my-skill.skill"),
        "verdict": dict(run_id="r1", phase="redesign", boundary="redesign-review"),
        "core": dict(run_id="r1", name="_state.md"),
        "project_preferences": {},
        "trajectory": dict(run_id="r1", session="abc"),
        "guards": {},
        "test_work": dict(name="case-1/README.md"),
        "eval_reports": dict(name="report.html"),
        "eval_workspace": dict(name="my-skill-workspace/iteration-1"),
        "standalone_packages": dict(name="my-skill.skill"),
    }

    def test_every_project_kind_resolves_under_a_generated_root(self):
        from output_paths import GENERATED_ROOTS, KINDS
        self.assertEqual(set(self.CASES) | {"product", "global_preferences"}, KINDS)
        root = Path(tempfile.gettempdir()) / "admiral-generated-roots"
        for kind, kwargs in self.CASES.items():
            with self.subTest(kind=kind):
                target = resolve(root, kind, **kwargs)
                for item in (target if isinstance(target, tuple) else (target,)):
                    first = item.resolve().relative_to(root.resolve()).parts[0]
                    self.assertIn(first, GENERATED_ROOTS, (kind, item))

    def test_save_ownership_declares_exactly_the_two_roots(self):
        save = _catalog.load_spec("save-ownership.yaml")
        self.assertEqual(list(save["generated_roots"]), ["skillset-saves", ".harness-state"])
        self.assertIn("redesign", save["phase_directories"])


class OwnershipAgreementTests(unittest.TestCase):
    def test_save_ownership_agrees_with_ownership_and_pipelines(self):
        ownership = _catalog.load_spec("ownership.yaml")
        save_ownership = _catalog.load_spec("save-ownership.yaml")
        classes = {c["id"]: c for c in save_ownership["classes"]}
        self.assertEqual(classes["core-run-record"]["writer"], "session-memory")
        self.assertEqual(classes["gate-verdict"]["writer"], "gatekeeper")
        self.assertEqual(classes["grilling-log"]["writer"], "admiral")
        self.assertIn("grilling-log", set(ownership["owners"]["admiral"]["writes"]))
        self.assertIn("run-state", set(ownership["owners"]["session-memory"]["writes"]))
        for tool_class in ("core-run-record", "gate-verdict"):
            tool = classes[tool_class]["tool"].split()[0]
            self.assertTrue((ROOT.parent / tool).is_file(), tool)
        for klass in classes.values():
            for pattern in klass["patterns"]:
                self.assertFalse(pattern.startswith("/"), pattern)
                self.assertNotIn("..", pattern)

    #: The kinds of writer `save-ownership.yaml` `writer_vocabulary` declares besides a roster skill.
    ROLES = {"gatekeeper", "safety-guardrails", "phase-lead"}
    COMPOUND_ROLES = {"phase-lead-or-delegated-specialist"}
    PROCESSES = {"harness-hooks", "harness-tests"}

    def test_every_class_has_a_writer_of_a_declared_kind_and_every_tool_exists(self):
        """QR-04: the pin above covers three writers and the tools of two classes; this covers every class."""
        save_ownership = _catalog.load_spec("save-ownership.yaml")
        roster = _catalog.roster()
        owners = set(_catalog.load_spec("ownership.yaml")["owners"])
        vocabulary = save_ownership["writer_vocabulary"]
        for klass in save_ownership["classes"]:
            writer = klass["writer"]
            with self.subTest(klass=klass["id"], writer=writer):
                self.assertIn(writer, roster | self.ROLES | self.COMPOUND_ROLES | self.PROCESSES)
                if writer in roster:
                    self.assertIn(writer, owners, "a skill that writes a class is an ownership.yaml owner")
                    self.assertIn(writer, vocabulary["skills"])
                if writer in self.PROCESSES:
                    self.assertIn(writer, vocabulary["processes"])
                if "tool" in klass:
                    tool = klass["tool"].split()[0]
                    self.assertTrue((ROOT.parent / tool).is_file(), f"{klass['id']} names {tool}, which does not exist")
        self.assertEqual(set(), (self.PROCESSES | self.COMPOUND_ROLES) & roster, "a process or compound role is not a skill")

    def test_startup_probe_has_a_declared_owner(self):
        policy = _catalog.load_spec("save-ownership.yaml")
        matches = [entry for entry in policy["classes"]
                   if any(fnmatch.fnmatchcase("skillset-saves/_probe-audit.tmp", pattern) for pattern in entry["patterns"])]
        self.assertEqual([entry["id"] for entry in matches], ["persistence-probe"])
        self.assertEqual(matches[0]["writer"], "admiral")

    def test_every_pipeline_phase_has_a_save_directory(self):
        save_ownership = _catalog.load_spec("save-ownership.yaml")
        directories = set(save_ownership["phase_directories"])
        pipelines = _catalog.load_spec("pipelines.yaml")["pipelines"]
        for name in pipelines:
            with self.subTest(pipeline=name):
                self.assertIn(name, directories)
        self.assertIn("skills/scripts/scan_record.py", pipelines["security"]["scripts"])
        self.assertIn("skills/taste/taste_prefs.py", pipelines["taste"]["scripts"])

    def test_save_protocol_points_at_the_machine_contracts(self):
        protocol = (ROOT / "save-protocol.md").read_text(encoding="utf-8")
        for reference in ("save-ownership.yaml", "save_run.py", "_journal.json"):
            self.assertIn(reference, protocol)


if __name__ == "__main__":
    unittest.main()
