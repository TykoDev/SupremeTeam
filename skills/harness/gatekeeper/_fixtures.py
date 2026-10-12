"""Test support: source-of-truth evidence the gate accepts, and an approved upstream verdict.

The typed source-of-truth records (gates.yaml evidence_types decision_log,
acceptance_table, interface_set, change_set, trace_map, revision_ref) read the
content of the artifacts they name, so a fixture cannot point them at an
arbitrary file. ``source_of_truth`` writes one Markdown body that is at once a
grilling log, a plan acceptance table, an interface note, a diff and a test log;
``records`` returns a record per kind that names it; ``approved_upstream`` writes
the upstream manifest and the gatekeeper-admiral cross-stage verdict a
revision_ref binds to, with the fingerprint check.py recomputes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _path in (_HERE.parents[1] / "scripts", _HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from data_formats import content_sha256  # noqa: E402

TEST_NAME = "test_items_ok"


def source_of_truth(changed: str) -> str:
    """One body every source-of-truth kind can read; ``changed`` is the file the diff names."""
    return f"""# Source of truth

## Resolved decisions

| ID | Decision | Chosen | Source |
| --- | --- | --- | --- |
| D-1 | API style | REST | user |

## Deferred decisions

| ID | Decision | Why deferral is safe | Owner | Reopen phase |
| --- | --- | --- | --- | --- |
| D-2 | Pagination | one page fits every tenant today | API lead | build |

## Rejected options

| ID | Option | Rationale |
| --- | --- | --- |
| D-3 | GraphQL | no client needs it |

## Non-goals and YAGNI deferrals

| ID | Non-goal | Reopen trigger | Owner |
| --- | --- | --- | --- |
| D-4 | Bulk export | a tenant asks for it | product owner |

## Acceptance criteria

| ID | Slice | Observable condition | Check that proves it | Acceptor |
| --- | --- | --- | --- | --- |
| AC-1 | items | GET /items returns 200 | {TEST_NAME} passes | API lead |

## Interfaces

IF-1 is GET /items.

## Diff

    --- a/{changed}
    +++ b/{changed}

## Test log

    {TEST_NAME} PASSED
"""


def write(root: Path, rel: str, text: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return content_sha256(path)


def records(artifact: str, changed: str, changed_sha256: str) -> dict:
    """A passing record per source-of-truth kind, every one naming ``artifact``."""
    return {
        "decision_log": artifact,
        "acceptance_table": artifact,
        "interface_set": {"artifacts": [artifact], "change": "changed",
                          "items": [{"id": "IF-1", "kind": "endpoint", "name": "GET /items"}]},
        "change_set": {"artifacts": [artifact],
                       "changed_files": [{"path": changed, "sha256": changed_sha256, "status": "modified"}]},
        "trace_map": {"items": [{"acceptance": "AC-1", "changes": [changed], "tests": [TEST_NAME]}]},
    }


def fingerprint(data: dict) -> str:
    """check.py's package fingerprint, restated so a fixture never imports the engine it tests."""
    stable = {k: v for k, v in data.items() if k not in {"gate_verdict", "checked_at", "package_fingerprint"}}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def approved_upstream(package_dir: Path, upstream_dir: Path, boundary: str, revision, run_id,
                      upstream_artifacts: dict[str, Path], evidence: dict | None = None) -> tuple[str, str]:
    """Write an approved upstream manifest and its cross-stage verdict; return (verdict path, its sha256).

    ``upstream_artifacts`` maps the upstream manifest's relative names to files it
    hashes; the returned path is relative to ``package_dir`` for the downstream
    manifest's ``verdict`` field and ``artifact_hashes``."""
    upstream_dir.mkdir(parents=True, exist_ok=True)
    hashes = {rel: content_sha256(path) for rel, path in upstream_artifacts.items()}
    manifest = {"schema_version": 2, "boundary": boundary, "revision": revision, "revisions": [revision],
                "run_id": run_id, "submission_id": f"{boundary}-1", "artifact_hashes": hashes,
                "evidence": evidence or {}}
    (upstream_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    verdict = {"boundary": boundary, "pass": True, "failures": [], "manifest": "manifest.json",
               "revision": revision, "run_id": run_id, "submission_id": f"{boundary}-1",
               "package_fingerprint": fingerprint(manifest), "gate_spec_is_shipped": True,
               "mechanical_only": False,
               "judgment": {"gate": "gatekeeper-admiral", "verdict": "APPROVED", "findings": [], "valid": True}}
    path = upstream_dir / f"verdict_{boundary}.cross-stage.json"
    path.write_text(json.dumps(verdict), encoding="utf-8")
    rel = os.path.relpath(path, package_dir).replace(os.sep, "/")
    return rel, content_sha256(path)
