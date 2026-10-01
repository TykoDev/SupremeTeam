#!/usr/bin/env python3
"""The save-path taxonomy in code equals save-ownership.yaml, and every resolver
kind and phase lands in exactly one declared class.

`save-ownership.yaml` is the policy. The parts programs need are copied into
`scripts/save_taxonomy.py`, and a few hooks still restate them. Nothing compared
any of it: the resolver accepted seven phases the policy never declared, and no
kind could produce the phase-root files the policy declares (the grilling log
among them). Each check below fails when one side moves without the other.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "harness" / "hooks"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HOOKS))
import save_taxonomy as taxonomy  # noqa: E402
from data_formats import load_data  # noqa: E402
from output_paths import KINDS, PHASES, resolve  # noqa: E402

POLICY = load_data(ROOT / "save-ownership.yaml")
CLASSES = {entry["id"]: entry for entry in POLICY["classes"]}

# Each phase-scoped kind and the class that owns what it resolves.
PHASE_KINDS = {"manifest": "phase-manifest", "reports": "phase-reports", "artifacts": "phase-artifacts",
               "evidence": "phase-evidence", "coverage": "phase-evidence", "packages": "phase-packages",
               "verdict": "gate-verdict"}
# Kinds with no phase, each with the arguments that resolve it and the class that owns the result.
PLAIN_KINDS = {
    "trajectory": (dict(run_id="r1", session="s1"), "harness-trajectories"),
    "guards": ({}, "harness-guards"),
    "test_work": (dict(name="case/x.txt"), "harness-test-scratch"),
    "eval_reports": (dict(name="report.html"), "skill-eval-reports"),
    "eval_workspace": (dict(name="ws/iteration-1"), "skill-eval-workspaces"),
    "standalone_packages": (dict(name="a.skill"), "standalone-packages"),
}
# Outside the project-relative policy by design: application source, and the per-user data root.
OUTSIDE_POLICY = {"product", "global_preferences"}


def owning_classes(relative: str) -> list[str]:
    """Ids of the classes that own a project-relative path.

    Where two classes match, the narrower one wins (`unowned_path_rule`); narrower
    is the pattern with more literal characters."""
    scored = {}
    for entry in POLICY["classes"]:
        matching = [pattern for pattern in entry["patterns"] if fnmatch.fnmatchcase(relative, pattern)]
        if matching:
            scored[entry["id"]] = max(len(pattern.replace("*", "")) for pattern in matching)
    best = max(scored.values(), default=0)
    return sorted(class_id for class_id, score in scored.items() if score == best)


def relative(root: Path, target: Path) -> str:
    return target.resolve().relative_to(root.resolve()).as_posix()


class TaxonomyMatchesThePolicyTests(unittest.TestCase):
    def test_constants_equal_the_policy(self):
        self.assertEqual(list(taxonomy.GENERATED_ROOTS), POLICY["generated_roots"])
        self.assertEqual(list(taxonomy.PHASE_DIRECTORIES), POLICY["phase_directories"])
        self.assertEqual(list(taxonomy.PHASE_SUBDIRECTORIES), POLICY["phase_subdirectories"])

    def test_the_core_run_record_class_is_the_taxonomys_file_names(self):
        expected = {f"skillset-saves/{taxonomy.POINTER}", f"skillset-saves/{taxonomy.WRITE_LOCK}",
                    f"skillset-saves/runs/*/{taxonomy.HISTORY}/*", f"skillset-saves/runs/*/{taxonomy.JOURNAL}"}
        expected |= {f"skillset-saves/runs/*/{name}" for name in taxonomy.RUN_RECORD_FILES}
        self.assertEqual(set(CLASSES["core-run-record"]["patterns"]), expected)

    def test_phase_root_names_are_the_policys_phase_root_patterns(self):
        """Patterns of the shape runs/*/<phase or *>/<one name>, in the two classes that hold them."""
        found = {"*": set(), "intake": set()}
        for class_id in ("phase-reports", "grilling-log"):
            for pattern in CLASSES[class_id]["patterns"]:
                match = re.fullmatch(r"skillset-saves/runs/\*/([^/]+)/([^/]+)", pattern)
                if match:
                    found[match.group(1)].add(match.group(2))
        self.assertEqual(found["*"], set(taxonomy.PHASE_ROOT_FILES))
        self.assertEqual(found["intake"], set(taxonomy.INTAKE_ROOT_FILES))

    def test_the_resolver_accepts_exactly_the_declared_phases(self):
        self.assertEqual(PHASES, set(POLICY["phase_directories"]))
        root = Path(tempfile.gettempdir()) / "save-taxonomy"
        for phase in ("architecture", "design-system", "frontend", "preferences", "explore", "improve", "documentation"):
            with self.subTest(phase=phase):
                with self.assertRaises(ValueError):
                    resolve(root, "reports", run_id="r1", phase=phase, name="x.md")


class RunIdGrammarIsStatedOnceTests(unittest.TestCase):
    """The writer, the resolver and the hooks' run scope each had a run-id pattern, and they disagreed."""

    PROBES = ("run-1", "2026-09-29_full-review-audit_k7q2xd", "_x", "_", "a.b_c-d", "x" * 128, "x" * 129, "", ".", "..", ".hidden",
              "-dash", "my run", "a/b", "a\\b", "run\n", "a;b", "é")

    def test_the_writer_the_resolver_and_the_hooks_accept_the_same_ids(self):
        import _state
        import save_run

        root = Path(tempfile.gettempdir()) / "run-id-grammar"
        for run_id in self.PROBES:
            with self.subTest(run_id=run_id):
                expected = taxonomy.RUN_ID.fullmatch(run_id) is not None
                try:
                    save_run.new_run_id(run_id)
                    writer = True
                except save_run.Refused:
                    writer = False
                try:
                    resolve(root, "core", run_id=run_id, name="_state.md")
                    resolver = True
                except ValueError:
                    resolver = False
                self.assertEqual((writer, resolver, _state.RUN_ID.fullmatch(run_id) is not None), (expected,) * 3)

    def test_a_new_id_is_one_the_path_resolver_can_resolve_for_every_run_scoped_kind(self):
        root = Path(tempfile.gettempdir()) / "run-id-grammar"
        for kind, extra in (("core", dict(name="_state.md")), ("trajectory", dict(session="s1")), ("reports", dict(phase="design", name="x.md"))):
            with self.subTest(kind=kind):
                self.assertTrue(resolve(root, kind, run_id="_x", **extra))


class ResolverKindsMapToOneClassTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def test_every_kind_has_an_expectation(self):
        covered = set(PHASE_KINDS) | set(PLAIN_KINDS) | {"core", "phase_report", "project_preferences"} | OUTSIDE_POLICY
        self.assertEqual(covered, KINDS, "a new resolver kind needs a class here and in save-ownership.yaml")

    def test_every_phase_scoped_kind_in_every_declared_phase_has_one_owner(self):
        for phase in taxonomy.PHASE_DIRECTORIES:
            for kind, class_id in PHASE_KINDS.items():
                with self.subTest(phase=phase, kind=kind):
                    name = ".coverage" if kind == "coverage" else "x.md"
                    target = resolve(self.root, kind, run_id="r1", phase=phase, name=name, boundary="a-to-b")
                    self.assertEqual(owning_classes(relative(self.root, target)), [class_id])

    def test_phase_root_files_have_one_owner_in_every_phase(self):
        for phase in taxonomy.PHASE_DIRECTORIES:
            names = {"report_plan.md": "phase-reports", "deliverable_x.md": "phase-reports", "review-packet.md": "phase-reports"}
            if phase == "intake":
                names |= {"report_grilling.md": "grilling-log", "intake-brief.md": "grilling-log"}
            for name, class_id in names.items():
                with self.subTest(phase=phase, name=name):
                    target = resolve(self.root, "phase_report", run_id="r1", phase=phase, name=name)
                    self.assertEqual(owning_classes(relative(self.root, target)), [class_id])

    def test_run_record_files_and_the_plain_kinds_have_one_owner(self):
        for name in taxonomy.RUN_RECORD_FILES:
            with self.subTest(kind="core", name=name):
                self.assertEqual(owning_classes(relative(self.root, resolve(self.root, "core", run_id="r1", name=name))),
                                 ["core-run-record"])
        for target in resolve(self.root, "project_preferences"):
            with self.subTest(kind="project_preferences", target=target.name):
                self.assertEqual(owning_classes(relative(self.root, target)), ["project-taste-preferences"])
        for kind, (arguments, class_id) in PLAIN_KINDS.items():
            with self.subTest(kind=kind):
                self.assertEqual(owning_classes(relative(self.root, resolve(self.root, kind, **arguments))), [class_id])

    def test_every_declared_phase_root_pattern_can_be_produced(self):
        """The gap: a class declared intake/report_grilling.md and no kind could resolve it."""
        for class_id in ("phase-reports", "grilling-log"):
            for pattern in CLASSES[class_id]["patterns"]:
                match = re.fullmatch(r"skillset-saves/runs/\*/([^/]+)/([^/]+)", pattern)
                if not match:
                    continue
                phase = "design" if match.group(1) == "*" else match.group(1)
                with self.subTest(pattern=pattern):
                    target = resolve(self.root, "phase_report", run_id="r1", phase=phase, name=match.group(2).replace("*", "x"))
                    self.assertTrue(fnmatch.fnmatchcase(relative(self.root, target), pattern), (pattern, target))


class RestatedTaxonomyStillAgreesTests(unittest.TestCase):
    """Sites that keep their own copy of the taxonomy, held to it by what they do."""

    CORE_PATHS = ("skillset-saves/_latest.md",
                  *(f"skillset-saves/runs/r1/{name}" for name in (*taxonomy.RUN_RECORD_FILES, taxonomy.JOURNAL)),
                  f"skillset-saves/runs/r1/{taxonomy.HISTORY}/rev-1.state.json")

    def test_the_pre_tool_hook_guards_every_core_run_file_and_not_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "CLAUDE_PROJECT_DIR": tmp}
            for path in (*self.CORE_PATHS, "skillset-saves/runs/r1/design/reports/report_plan.md"):
                with self.subTest(path=path):
                    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(Path(tmp) / path)}})
                    proc = subprocess.run([sys.executable, str(HOOKS / "pre_tool_use.py")], input=payload, text=True,
                                          capture_output=True, env=env, check=False)
                    self.assertEqual("save_run.py" in proc.stdout, path in self.CORE_PATHS, proc.stdout)

    def test_the_size_audit_never_offers_a_core_run_file_for_removal(self):
        import size_audit

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (*self.CORE_PATHS, "skillset-saves/runs/r1/design/evidence/big.log"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x" * 64)
                with self.subTest(path=path):
                    offered = [item["path"] for item in size_audit.scan(root, threshold_bytes=1)["files"]]
                    self.assertEqual(path in offered, path.endswith("big.log"), offered)
                target.unlink()

    def test_the_coverage_sweep_falls_back_to_the_declared_phases(self):
        import post_tool_use

        self.assertEqual(set(getattr(post_tool_use, "_FALLBACK_PHASES", taxonomy.PHASE_DIRECTORIES)), set(POLICY["phase_directories"]))
        self.assertEqual(tuple(getattr(post_tool_use, "_GENERATED_ROOTS", taxonomy.GENERATED_ROOTS)), tuple(POLICY["generated_roots"]))


if __name__ == "__main__":
    unittest.main()
