#!/usr/bin/env python3
"""Regression tests for the SupremeTeam gatekeeper deterministic gate engine.

Covers the mechanical checks the ``gatekeeper-*`` scripts rely on: frontmatter
parsing, required-artifact pass/fail, conditional artifacts, mixed-revision
detection, skip-record validation, blocked-phrase hits, idempotency drift,
harness-doctrine §5 structure, and fail-loud behavior on a missing package.

Run from the repo root:
    python -m unittest discover -s SupremeTeam/harness/gatekeeper -p "test_*.py"
"""

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

import _gatecheck as gc  # noqa: E402

_TMP_ROOT = Path.cwd() / "gatekeeper-test-work"


@contextmanager
def _package():
    _TMP_ROOT.mkdir(parents=True, exist_ok=True)
    pkg = _TMP_ROOT / f"case-{uuid.uuid4().hex}"
    pkg.mkdir(parents=True, exist_ok=False)
    try:
        yield pkg
    finally:
        shutil.rmtree(pkg, ignore_errors=True)
        try:
            _TMP_ROOT.rmdir()
        except OSError:
            pass


def _write(pkg: Path, name: str, body: str) -> None:
    (pkg / name).write_text(body, encoding="utf-8")


def _manifest(*specs) -> gc.Manifest:
    return gc.Manifest(boundary="test", sub_orchestrator="test", artifacts=specs)


def _codes(report) -> set:
    return {f.code for f in report.findings}


class FrontmatterTests(unittest.TestCase):
    def test_parses_scalars_lists_and_nesting(self):
        text = (
            "---\n"
            "run_id: abc_123\n"
            "revision: 2\n"
            "verdict: APPROVED\n"
            "requested_endpoints: [design, build, review]\n"
            "active_delegation:\n"
            "  target: commander\n"
            "  timeout_seconds: 600\n"
            "---\n"
            "body text\n"
        )
        fm = gc.parse_frontmatter(text)
        self.assertEqual(fm["run_id"], "abc_123")
        self.assertEqual(fm["revision"], 2)
        self.assertEqual(fm["requested_endpoints"], ["design", "build", "review"])
        self.assertEqual(fm["active_delegation"]["target"], "commander")

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(gc.parse_frontmatter("# just a heading\n"), {})

    def test_block_list_form(self):
        text = "---\nitems:\n  - one\n  - two\n---\n"
        self.assertEqual(gc.parse_frontmatter(text)["items"], ["one", "two"])


class RequiredArtifactTests(unittest.TestCase):
    def test_missing_required_artifact_fails(self):
        with _package() as pkg:
            _write(pkg, "readme.md", "nothing useful")
            manifest = _manifest(gc.ArtifactSpec(
                key="impl", label="implementation", patterns=("*implementation*.md",)))
            report = gc.run_gate(pkg, manifest)
        self.assertIn("ARTIFACT_MISSING", _codes(report))
        self.assertTrue(report.has_blocking)
        self.assertEqual(report.exit_code(), 1)

    def test_present_required_artifact_passes(self):
        with _package() as pkg:
            _write(pkg, "deliverable_implementation.md",
                   "# Impl\nchanged file: app.py module updated")
            manifest = _manifest(gc.ArtifactSpec(
                key="impl", label="implementation",
                patterns=("*implementation*.md",), content_marker=r"changed file"))
            report = gc.run_gate(pkg, manifest)
        self.assertIn("ARTIFACT_PRESENT", _codes(report))
        self.assertFalse(report.has_blocking)

    def test_conditional_artifact_absent_is_unchecked_not_fail(self):
        with _package() as pkg:
            _write(pkg, "plan.md", "the plan")
            manifest = _manifest(gc.ArtifactSpec(
                key="api", label="API contracts", patterns=("*api*.md",),
                requirement="conditional"))
            report = gc.run_gate(pkg, manifest)
        self.assertIn("ARTIFACT_CONDITIONAL", _codes(report))
        self.assertFalse(report.has_blocking)
        self.assertTrue(report.unchecked)


class LineageTests(unittest.TestCase):
    def test_mixed_revisions_flagged(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: 1\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: 2\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("MIXED_REVISIONS", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_single_revision_coherent(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: 3\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: 3\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("REVISION_COHERENT", _codes(report))


class SkipRecordTests(unittest.TestCase):
    def test_incomplete_skip_record_fails(self):
        with _package() as pkg:
            _write(pkg, "_skip-record.md", "---\npipeline: review\n---\nno reason")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("SKIP_RECORD_INCOMPLETE", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_complete_skip_record_passes(self):
        with _package() as pkg:
            _write(pkg, "_skip-record.md",
                   "---\npipeline: review\nskipped_at: 2026-06-06\n"
                   "reason: not in scope\napproved_by: user\n---\n")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("SKIP_RECORD_OK", _codes(report))


class BlockedPhraseTests(unittest.TestCase):
    def test_blocked_phrase_is_blocking(self):
        with _package() as pkg:
            _write(pkg, "summary.md", "This is 100% complete, trust me.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("BLOCKED_PHRASE", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_code_rot_marker_is_blocking(self):
        with _package() as pkg:
            _write(pkg, "notes.md", "implementation done\n# TODO wire up auth")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("BLOCKED_PHRASE", _codes(report))

    def test_clean_package_reports_clean(self):
        with _package() as pkg:
            _write(pkg, "summary.md", "The change adds a validated endpoint.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("BLOCKED_PHRASE_CLEAN", _codes(report))


class IdempotencyTests(unittest.TestCase):
    def test_reused_submission_id_with_new_revision_is_drift(self):
        # The prior verdict lives OUTSIDE the package (a previous phase dir).
        with _package() as pkg, _package() as side:
            _write(pkg, "pkg.md", "---\nsubmission_id: S1\nrevision: 4\n---\n")
            prior = side / "prior.md"
            prior.write_text("---\nsubmission_id: S1\nrevision: 3\n"
                             "verdict: REVISE\n---\n", encoding="utf-8")
            report = gc.run_gate(pkg, _manifest(), prior_path=prior)
        self.assertIn("SILENT_DRIFT", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_same_submission_and_revision_is_reusable(self):
        with _package() as pkg, _package() as side:
            _write(pkg, "pkg.md", "---\nsubmission_id: S2\nrevision: 5\n---\n")
            prior = side / "prior.md"
            prior.write_text("---\nsubmission_id: S2\nrevision: 5\n"
                             "verdict: APPROVED\n---\n", encoding="utf-8")
            report = gc.run_gate(pkg, _manifest(), prior_path=prior)
        self.assertIn("VERDICT_REUSABLE", _codes(report))


class HarnessDoctrineTests(unittest.TestCase):
    def test_intervention_without_layer_or_regression_fails(self):
        with _package() as pkg:
            _write(pkg, "change.md",
                   "We add a new PreToolUse hook that blocks risky writes.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("DOCTRINE_GAP", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_intervention_with_layer_and_regression_is_unchecked(self):
        with _package() as pkg:
            _write(pkg, "change.md",
                   "We add a PostToolUse hook at Layer 4. Regression: confirmed "
                   "it does not block a valid command.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("DOCTRINE_NOTE_PRESENT", _codes(report))
        self.assertFalse(report.has_blocking)

    def test_package_without_intervention_is_inert(self):
        with _package() as pkg:
            _write(pkg, "plan.md", "A normal design plan with no runtime hooks.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("NO_RUNTIME_INTERVENTION", _codes(report))


class FailLoudTests(unittest.TestCase):
    def test_missing_package_is_critical_fail(self):
        report = gc.run_gate(_TMP_ROOT / "does-not-exist", _manifest())
        self.assertIn("PACKAGE_NOT_FOUND", _codes(report))
        self.assertEqual(report.exit_code(), 1)

    def test_empty_package_is_critical_fail(self):
        with _package() as pkg:
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("PACKAGE_EMPTY", _codes(report))
        self.assertEqual(report.exit_code(), 1)


if __name__ == "__main__":
    unittest.main()
