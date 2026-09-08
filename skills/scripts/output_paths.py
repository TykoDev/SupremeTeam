#!/usr/bin/env python3
"""Resolve the declared destination for every generated Supreme Team output.

Workflows name bare files (``DESIGN.md``, ``tokens.css``, ``design-system.html``,
``eval-0-.../outputs``); this resolver maps each output class to one governed
location so nothing lands in an ambiguous current directory.

    python skills/scripts/output_paths.py --project-root . --run-id <run> \
        --phase design-system --kind artifacts --name tokens.css

Kinds and destinations (relative to the project root):

    core        skillset-saves/runs/<run>/{_state.md,_lock.md,_audit-trail.md}   writer: session-memory via save_run.py
    manifest    skillset-saves/runs/<run>/<phase>/manifest.json                     writer: phase lead
    reports     skillset-saves/runs/<run>/<phase>/reports/<name>                   writer: phase lead or delegated specialist
    artifacts   skillset-saves/runs/<run>/<phase>/artifacts/<name>                 normalized data, HTML, generated assets
    evidence    skillset-saves/runs/<run>/<phase>/evidence/<name>                  command logs, scan records, captures
    packages    skillset-saves/runs/<run>/<phase>/packages/<name>                  exported archives
    verdict     skillset-saves/runs/<run>/<phase>/verdict_<boundary>.json          writer: gatekeeper
    preferences skillset-saves/preferences/taste.md                                writer: taste via taste_prefs.py
    trajectory  .harness-state/trajectories/<run>/<session>.json                   writer: post_tool_use hook
    guards      .harness-state/guard-state.json                                    writer: guard/freeze/unfreeze
    product     <project>/<name>  (application source stays in the application's layout; snapshot into evidence with provenance)
    design_spec <project>/DESIGN.md (durable project design spec; an immutable copy goes to <phase>/artifacts/DESIGN.md)

Every resolved path is validated to stay inside the project root. Exit 0 with
a JSON object; exit 1 on an unsafe or unknown request.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

KINDS = {"core", "manifest", "reports", "artifacts", "evidence", "packages", "verdict", "preferences", "trajectory", "guards", "product", "design_spec"}
PHASES = {"intake", "design", "architecture", "design-system", "build", "frontend", "security", "investigation", "qa", "review", "delivery", "release", "preferences", "skill-creation", "explore", "improve", "documentation"}
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def resolve(project_root: Path, kind: str, *, run_id: str = "", phase: str = "", name: str = "", boundary: str = "", session: str = "") -> Path:
    if kind not in KINDS:
        raise ValueError(f"unknown output kind {kind!r}")
    root = project_root.resolve()
    saves = root / "skillset-saves"

    def seg(value: str, label: str) -> str:
        if not SAFE_SEGMENT.match(value or ""):
            raise ValueError(f"{label} must be a single safe path segment, got {value!r}")
        return value

    def rel_name(value: str) -> Path:
        candidate = Path(value or "")
        if not value or candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
            raise ValueError(f"name must be a relative path without traversal, got {value!r}")
        return candidate

    if kind == "preferences":
        target = saves / "preferences" / "taste.md"
    elif kind == "guards":
        target = root / ".harness-state" / "guard-state.json"
    elif kind == "trajectory":
        target = root / ".harness-state" / "trajectories" / seg(run_id or "no-run", "run_id") / (seg(session, "session") + ".json")
    elif kind == "product":
        target = root / rel_name(name)
    elif kind == "design_spec":
        target = root / "DESIGN.md"
    else:
        run_dir = saves / "runs" / seg(run_id, "run_id")
        if kind == "core":
            if name not in {"_state.md", "_lock.md", "_audit-trail.md"}:
                raise ValueError("core name must be _state.md, _lock.md, or _audit-trail.md")
            target = run_dir / name
        else:
            if phase not in PHASES:
                raise ValueError(f"phase must be one of {sorted(PHASES)}, got {phase!r}")
            phase_dir = run_dir / phase
            if kind == "manifest":
                target = phase_dir / "manifest.json"
            elif kind == "verdict":
                target = phase_dir / f"verdict_{seg(boundary, 'boundary')}.json"
            else:
                target = phase_dir / kind / rel_name(name)
    target = Path(target)
    try:
        Path(target).resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"resolved path escapes project root: {target}") from exc
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a governed output destination.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--kind", required=True, choices=sorted(KINDS))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--phase", default="")
    parser.add_argument("--name", default="")
    parser.add_argument("--boundary", default="")
    parser.add_argument("--session", default="")
    parser.add_argument("--mkdir", action="store_true", help="create the parent directory")
    args = parser.parse_args()
    try:
        target = resolve(Path(args.project_root), args.kind, run_id=args.run_id, phase=args.phase, name=args.name, boundary=args.boundary, session=args.session)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    if args.mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"ok": True, "kind": args.kind, "path": str(target), "relative": target.resolve().relative_to(Path(args.project_root).resolve()).as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
