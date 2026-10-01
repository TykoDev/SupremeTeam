#!/usr/bin/env python3
"""Resolve the declared destination for every generated Supreme Team output.

Workflows name bare files (``design-system.md``, ``tokens.css``, ``app.html``,
``eval-0-.../outputs``); this resolver maps each output class to one governed
location so nothing lands in an ambiguous current directory.

    python skills/scripts/output_paths.py --project-root . --run-id <run> \
        --phase design --kind artifacts --name tokens.css

Kinds and destinations (relative to the project root):

    core        skillset-saves/runs/<run>/{_state.md,_lock.md,_audit-trail.md}   writer: session-memory via save_run.py
    manifest    skillset-saves/runs/<run>/<phase>/manifest.json                     writer: phase lead
    phase_report skillset-saves/runs/<run>/<phase>/<name>                          report_*.md, deliverable_*.md, review-packet.md; intake also report_grilling.md, intake-brief.md
    reports     skillset-saves/runs/<run>/<phase>/reports/<name>                   writer: phase lead or delegated specialist
    artifacts   skillset-saves/runs/<run>/<phase>/artifacts/<name>                 normalized data, HTML, generated assets
    evidence    skillset-saves/runs/<run>/<phase>/evidence/<name>                  command logs, scan records, captures
    coverage    skillset-saves/runs/<run>/<phase>/evidence/coverage/<name>         coverage data files and reports (phase-evidence, one directory below evidence/)
    packages    skillset-saves/runs/<run>/<phase>/packages/<name>                  exported archives
    verdict     skillset-saves/runs/<run>/<phase>/verdict_<boundary>.json          writer: gatekeeper
    project_preferences skillset-saves/preferences/{taste.json,taste.md}           writer: taste via skills/taste/taste_prefs.py
    global_preferences <deterministic user-data>/SupremeTeam/preferences/{taste.json,taste.md}
    trajectory  .harness-state/trajectories/<run>/<session>.json                   writer: post_tool_use hook
    guards      .harness-state/guard-state.json                                    writer: guard/freeze/unfreeze
    test_work   .harness-state/test-work/<name>                                    regression-test scratch
    eval_reports .harness-state/eval-reports/<name>                                skill-creator live reports
    eval_workspace .harness-state/eval-workspaces/<name>                           skill-creator eval workspaces outside a run
    standalone_packages .harness-state/packages/<name>                             .skill or zip archives built outside a run
    product     <project>/<name>  (application source stays in the application's layout; snapshot into evidence with provenance)

Every kind except product resolves under skillset-saves/ or .harness-state/
(GENERATED_ROOTS); a durable design specification is the run's
<phase>/reports/design-system.md, not a file at the project root. `product` is open
except for what naming a path "product" must not bless: the version-control
directory (a hook there runs code), the generated roots, `skills/harness/` (the guard
and the gate validators) and the host hook-registration files. A name under any of
them is refused, however it is spelled or reached through a link.

The phase-scoped kinds accept the phase directories save-ownership.yaml declares
and no others. The grilling log is `--kind phase_report --phase intake --name
report_grilling.md`, which is the intake/report_grilling.md the gate references;
`--kind reports` would place it one directory lower, in intake/reports/.

`coverage` is the one destination a test runner is told about through its own
environment rather than written to directly: point COVERAGE_FILE, --data-file,
--cov-report=<fmt>:<dest>/..., --report-dir/--temp-dir, or
--coverage.reportsDirectory at the resolved directory so coverage data lands in
the run instead of accumulating as `.coverage*` residue at the project root.

Project paths are validated for project containment; global preferences are
validated separately to remain outside the checkout. Exit 0 with a JSON object;
exit 1 on an unsafe or unknown request.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

import save_taxonomy as taxonomy

# Every generated kind resolves under one of these project-relative roots; the
# only exception is `product`, which is the application's own source layout.
GENERATED_ROOTS = taxonomy.GENERATED_ROOTS
KINDS = {"core", "manifest", "phase_report", "reports", "artifacts", "evidence", "coverage", "packages", "verdict", "project_preferences", "global_preferences", "trajectory", "guards", "test_work", "eval_reports", "eval_workspace", "standalone_packages", "product"}
PHASES = set(taxonomy.PHASE_DIRECTORIES)
# Matched with fullmatch: `$` also accepts a trailing newline.
SAFE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# Project-relative paths a `product` name may not point at or below.
PRODUCT_DENIED = (".git", *GENERATED_ROOTS, "skills/harness", ".claude/settings.json", ".claude/settings.local.json",
                  ".codex/hooks.json", ".github/hooks.json")


def denied_product_path(relative: Path) -> str | None:
    """The ``PRODUCT_DENIED`` entry a project-relative path is at or under, compared without regard to case."""
    parts = tuple(part.casefold() for part in relative.parts)
    for denied in PRODUCT_DENIED:
        wanted = tuple(part.casefold() for part in Path(denied).parts)
        if parts[:len(wanted)] == wanted:
            return denied
    return None


def global_data_root(env: dict[str, str] | None = None) -> Path:
    """Return a deterministic, checkout-independent SupremeTeam data root."""
    env = os.environ if env is None else env
    if env.get("SUPREMETEAM_HOME"):
        return Path(env["SUPREMETEAM_HOME"]).expanduser().resolve()
    for key in ("CODEX_HOME", "AGENTS_HOME"):
        if env.get(key):
            return (Path(env[key]).expanduser().resolve() / "supremeteam")
    if sys.platform == "win32":
        base = Path(env.get("LOCALAPPDATA") or env.get("APPDATA") or Path.home() / "AppData" / "Local")
        return (base / "SupremeTeam").resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "SupremeTeam").resolve()
    # The XDG spec ignores an empty or relative value; either would otherwise
    # resolve against the working directory, which may be the project itself.
    xdg = env.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".local" / "share"
    return (base / "supremeteam").resolve()


def resolve(project_root: Path, kind: str, *, run_id: str = "", phase: str = "", name: str = "", boundary: str = "", session: str = "") -> Path | tuple[Path, Path]:
    if kind not in KINDS:
        raise ValueError(f"unknown output kind {kind!r}")
    root = project_root.resolve()
    saves = root / "skillset-saves"

    def seg(value: str, label: str) -> str:
        if not SAFE_SEGMENT.fullmatch(value or ""):
            raise ValueError(f"{label} must be a single safe path segment, got {value!r}")
        return value

    def run_segment(value: str) -> str:
        if not taxonomy.RUN_ID.fullmatch(value or ""):
            raise ValueError(f"run_id must be {taxonomy.RUN_ID_RULE}, got {value!r}")
        return value

    def rel_name(value: str) -> Path:
        candidate = Path(value or "")
        if not value or candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
            raise ValueError(f"name must be a relative path without traversal, got {value!r}")
        return candidate

    def root_file(value: str, phase: str) -> Path:
        candidate = rel_name(value)
        allowed = taxonomy.PHASE_ROOT_FILES + (taxonomy.INTAKE_ROOT_FILES if phase == "intake" else ())
        if len(candidate.parts) != 1 or not any(fnmatch.fnmatchcase(candidate.name, pattern) for pattern in allowed):
            raise ValueError(f"{phase} phase-root files must be named like one of {list(allowed)}, got {value!r}")
        return candidate

    if kind == "project_preferences":
        base = saves / "preferences"
        targets = (base / "taste.json", base / "taste.md")
    elif kind == "global_preferences":
        base = global_data_root() / "preferences"
        targets = (base / "taste.json", base / "taste.md")
    elif kind == "guards":
        target = root / ".harness-state" / "guard-state.json"
    elif kind == "trajectory":
        target = root / ".harness-state" / "trajectories" / run_segment(run_id or "no-run") / (seg(session, "session") + ".json")
    elif kind == "product":
        target = root / rel_name(name)
    elif kind == "test_work":
        target = root / ".harness-state" / "test-work" / rel_name(name)
    elif kind == "eval_reports":
        target = root / ".harness-state" / "eval-reports" / rel_name(name)
    elif kind == "eval_workspace":
        target = root / ".harness-state" / "eval-workspaces" / rel_name(name)
    elif kind == "standalone_packages":
        target = root / ".harness-state" / "packages" / rel_name(name)
    else:
        run_dir = saves / "runs" / run_segment(run_id)
        if kind == "core":
            if name not in taxonomy.RUN_RECORD_FILES:
                raise ValueError("core name must be " + ", ".join(taxonomy.RUN_RECORD_FILES[:-1]) + ", or " + taxonomy.RUN_RECORD_FILES[-1])
            target = run_dir / name
        else:
            if phase not in PHASES:
                raise ValueError(f"phase must be one of {sorted(PHASES)}, got {phase!r}")
            phase_dir = run_dir / phase
            if kind == "manifest":
                target = phase_dir / "manifest.json"
            elif kind == "phase_report":
                target = phase_dir / root_file(name, phase)
            elif kind == "verdict":
                target = phase_dir / f"verdict_{seg(boundary, 'boundary')}.json"
            elif kind == "coverage":
                # Coverage data files and reports are phase evidence held one
                # directory below evidence/ so a sweep can relocate a whole
                # residue tree without colliding with hashed evidence files.
                target = phase_dir / "evidence" / "coverage" / rel_name(name)
            else:
                target = phase_dir / kind / rel_name(name)
    if kind in {"project_preferences", "global_preferences"}:
        if kind == "project_preferences":
            for target in targets:
                try:
                    target.resolve().relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"project preference path escapes project root: {target}") from exc
        elif any(root == target.resolve() or root in target.resolve().parents for target in targets):
            raise ValueError("global preference path must not be inside the project checkout")
        return targets
    target = Path(target)
    try:
        target.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"resolved path escapes project root: {target}") from exc
    if kind == "product":
        denied = denied_product_path(Path(name)) or denied_product_path(target.resolve().relative_to(root))
        if denied:
            raise ValueError(f"product path {name!r} is at or under {denied}, which no product output may target")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a governed output destination.", epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
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
    if isinstance(target, tuple):
        if args.mkdir:
            target[0].parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps({"ok": True, "kind": args.kind, "canonical": str(target[0]), "rendered": str(target[1])}))
    else:
        if args.mkdir:
            target.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps({"ok": True, "kind": args.kind, "path": str(target), "relative": target.resolve().relative_to(Path(args.project_root).resolve()).as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
