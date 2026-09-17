#!/usr/bin/env python3
"""Build (or dry-run) the Supreme Team distribution archive and verify its contents.

Ignore rules do not control what a packager includes; this script enumerates
the files that ``skills/package-manifest.yaml`` selects from the chosen root,
rejects runtime residue classes, confirms required assets are present, and
optionally writes the archive.

    python skills/scripts/package_check.py --root . [--out .harness-state/packages/supremeteam.zip]

Exit 0 when the enumerated set is clean, 1 when residue or a missing required
file is found, 2 on manifest/engine error. The JSON report lists every
violation with the class it matched.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import zipfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1]
if str(SKILLS / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import DataFormatError, load_data  # noqa: E402

RESIDUE_CLASSES = {
    "interpreter-cache": ["**/__pycache__/**", "**/*.pyc"],
    "runtime-state": [".harness-state/**", "**/.harness-state/**"],
    "save-state": ["skillset-saves/**", "**/skillset-saves/**"],
    "test-scratch": ["harness-test-work/**", "**/harness-test-work/**", "gatekeeper-test-work/**", "**/gatekeeper-test-work/**", "**/.harness-state/test-work/**"],
    "render-scratch": [".playwright-mcp/**", "**/.playwright-mcp/**"],
    # Coverage data and reports are run evidence under
    # skillset-saves/runs/*/*/evidence/coverage/ (output_paths.py --kind coverage),
    # never project-root residue and never part of a package.
    "coverage-residue": ["**/.coverage", "**/.coverage.*", "**/.coverage/**", "**/htmlcov/**", "**/.nyc_output/**"],
    "eval-workspace": ["**/*-workspace/**", "**/evals/workspace/**"],
    "archives": ["**/*.skill", "**/*.zip"],
    "secrets": ["**/.env", "**/.env.*", "**/*.pem", "**/*.key"],
}
REQUIRED_ASSET_GLOBS = [
    "skills/gates.yaml",
    "skills/pipelines.yaml",
    "skills/ownership.yaml",
    "skills/save-ownership.yaml",
    "skills/team-manifest.yaml",
    "skills/runtime-manifest.yaml",
    "skills/tech-stacks/registry.yaml",
    "skills/harness/gatekeeper/check.py",
    "skills/harness/hooks/save_run.py",
]


def matches(relative: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        # Unlike fnmatch, a recursive glob also matches zero directories.
        while pattern.startswith("**/"):
            pattern = pattern[3:]
            if fnmatch.fnmatch(relative, pattern):
                return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Enumerate and verify the Supreme Team package.")
    parser.add_argument("--root", default=".", help="delivery root (the directory containing skills/)")
    parser.add_argument("--manifest", default=str(SKILLS / "package-manifest.yaml"))
    parser.add_argument("--out", help="write a zip archive here after a clean enumeration")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        manifest = load_data(Path(args.manifest))
    except DataFormatError as exc:
        print(json.dumps({"ok": False, "engine_error": str(exc)}))
        return 2
    include = [str(p) for p in manifest.get("include", ["**/*"])]
    exclude = [str(p) for p in manifest.get("exclude", [])]
    selected: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/"):
            continue
        if not matches(relative, include):
            continue
        if matches(relative, exclude):
            continue
        selected.append(relative)
    violations = []
    for relative in selected:
        for klass, patterns in RESIDUE_CLASSES.items():
            if matches(relative, patterns):
                violations.append({"path": relative, "class": klass})
                break
    missing = [glob for glob in REQUIRED_ASSET_GLOBS if not any(fnmatch.fnmatch(rel, glob) for rel in selected)]
    ok = not violations and not missing
    report = {"ok": ok, "root": str(root), "selected_count": len(selected), "violations": violations, "missing_required": missing}
    if ok and args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in sorted(selected):
                archive.write(root / relative, relative)
        report["archive"] = str(out)
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
