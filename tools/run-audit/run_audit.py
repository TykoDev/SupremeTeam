#!/usr/bin/env python3
"""run-audit: audit Supreme Team saved-run history and harness observations.

A zero-dependency console (ADR-1) that reads the two governed state roots of a
Supreme Team checkout, renders an audit report as JSON and HTML, and exits
according to a findings threshold. Inputs are read-only (ADR-2); every value
that reaches HTML is escaped (ADR-3); the output is findings with severity, not
a score (ADR-4); output is deterministic apart from `generated_at` (ADR-5).

Interfaces: IF-1 (command line), IF-2 (report.json schema), IF-3 (report.html
surface), IF-4 (exit codes). See the design package of run pi-deploy-02.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOL_NAME = "run-audit"
TOOL_VERSION = "1.1.0"

SEVERITIES = ("Critical", "Major", "Minor", "Info")
SINK_LIMIT = 200
_EVENT_LINE = re.compile(r"^\s*\{.*\}\s*$")


# --------------------------------------------------------------------- hashing
_TEXT_PROBE = 8192


def content_sha256(path: Path) -> str:
    """The line-ending-agnostic digest the gate tooling uses: text (no NUL in
    the first 8 KiB) has CRLF folded to LF, binary is hashed byte for byte.
    This mirrors skills/scripts/data_formats.py content_sha256 exactly, so drift
    found here is the drift the gates would find (AC-2's premise;
    regression-tested)."""
    data = path.read_bytes()
    if b"\x00" not in data[:_TEXT_PROBE]:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# -------------------------------------------------------------------- scanning
def _load_json(path: Path, findings: list, root: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        findings.append({
            "severity": "Major",
            "statement": f"unparseable {what}: {type(exc).__name__}: {exc}",
            "where": _rel(path, root),
        })
        return None


def _trail_events(path: Path, findings: list, root: Path) -> list:
    events = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        findings.append({"severity": "Major", "statement": f"unreadable audit trail: {exc}",
                         "where": _rel(path, root)})
        return events
    for number, line in enumerate(lines, start=1):
        if not _EVENT_LINE.match(line):
            if line.strip():
                findings.append({"severity": "Minor",
                                 "statement": f"audit trail line {number} is not a JSON event",
                                 "where": _rel(path, root)})
            continue
        try:
            event = json.loads(line)
        except ValueError:
            findings.append({"severity": "Minor",
                             "statement": f"audit trail line {number} is not valid JSON",
                             "where": _rel(path, root)})
            continue
        events.append({
            "event": str(event.get("event", "")),
            "revision": event.get("revision"),
            "owner": event.get("owner"),
        })
    return events


def _max_revision(events: list, state: dict) -> int:
    best = 0
    for event in events:
        revision = event.get("revision")
        if isinstance(revision, int) and not isinstance(revision, bool):
            best = max(best, revision)
        elif isinstance(revision, str) and revision.isdigit():
            best = max(best, int(revision))
    state_revision = state.get("revision") if isinstance(state, dict) else None
    if isinstance(state_revision, int) and not isinstance(state_revision, bool):
        best = max(best, state_revision)
    return best


def _scan_manifest(path: Path, project_root: Path, findings: list, artifacts: list[str] | None = None) -> dict:
    data = _load_json(path, findings, project_root, "manifest")
    result = {"manifest": _rel(path, project_root), "boundary": None, "schema_version": None,
              "evidence_drift": [], "declared_artifacts": 0}
    if not isinstance(data, dict):
        return result
    result["boundary"] = data.get("boundary")
    result["schema_version"] = data.get("schema_version")
    hashes = data.get("artifact_hashes")
    if not isinstance(hashes, dict):
        findings.append({"severity": "Major", "statement": "manifest declares no artifact_hashes map",
                         "where": _rel(path, project_root)})
        return result
    result["declared_artifacts"] = len(hashes)
    if artifacts:
        for missing in sorted(set(artifacts) - set(hashes)):
            findings.append({"severity": "Major", "statement": f"selected artifact is not declared: {missing}",
                             "where": _rel(path, project_root)})
        hashes = {key: value for key, value in hashes.items() if key in artifacts}
    result["checked_artifacts"] = len(hashes)
    for rel, expected in sorted(hashes.items()):
        target = (path.parent / str(rel))
        entry = {"manifest": _rel(path, project_root), "path": str(rel), "expected": str(expected),
                 "actual": None, "kind": None}
        try:
            resolved = target.resolve()
            resolved.relative_to(project_root.resolve())
        except (OSError, ValueError):
            entry["kind"] = "unresolvable"
            result["evidence_drift"].append(entry)
            continue
        if not resolved.is_file():
            entry["kind"] = "missing"
            result["evidence_drift"].append(entry)
            continue
        actual = content_sha256(resolved)
        entry["actual"] = actual
        if actual != str(expected).lower():
            entry["kind"] = "hash-drift"
            result["evidence_drift"].append(entry)
    return result


def _scan_verdicts(phase_dir: Path, project_root: Path, findings: list) -> list:
    verdicts = []
    for path in sorted(p for p in phase_dir.glob("verdict_*.json")
                       if not p.name.endswith((".judgment.json", ".cycles.json"))):
        data = _load_json(path, findings, project_root, "verdict record")
        if not isinstance(data, dict):
            continue
        judgment = data.get("judgment") if isinstance(data.get("judgment"), dict) else {}
        verdicts.append({
            "file": _rel(path, project_root),
            "boundary": data.get("boundary"),
            "verdict": judgment.get("verdict"),
            "gate": judgment.get("gate"),
            "pass": data.get("pass"),
            "gate_spec_is_shipped": data.get("gate_spec_is_shipped"),
        })
    return verdicts


def scan_runs(project_root: Path, run_ids: list[str] | None = None, phases: list[str] | None = None,
              artifacts: list[str] | None = None) -> tuple[list, list]:
    """Every run under skillset-saves/runs with its revisions, terminal state,
    events, gate verdicts, and evidence drift. Parse errors become findings."""
    findings: list = []
    runs: list = []
    for selector in (run_ids or []) + (phases or []):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", selector):
            raise ValueError("run and phase selectors must be single path components")
    runs_root = project_root / "skillset-saves" / "runs"
    if not runs_root.is_dir():
        findings.append({"severity": "Major" if run_ids else "Info", "statement": "no saved runs directory to audit",
                         "where": _rel(runs_root, project_root)})
        return runs, findings
    selected = [runs_root / name for name in sorted(set(run_ids))] if run_ids else sorted(runs_root.iterdir())
    for run_dir in selected:
        if run_dir.is_symlink() or not run_dir.is_dir():
            if run_ids:
                findings.append({"severity": "Major", "statement": "selected run is missing or a symlink",
                                 "where": _rel(run_dir, project_root)})
            continue
        state = _load_json(run_dir / "_state.md", findings, project_root, "run state")
        state = state if isinstance(state, dict) else {}
        trail = run_dir / "_audit-trail.md"
        events = _trail_events(trail, findings, project_root) if trail.is_file() else []
        manifests = []
        drift = []
        verdicts = []
        phase_dirs = [run_dir / name for name in sorted(set(phases))] if phases else sorted(run_dir.iterdir())
        for phase_dir in phase_dirs:
            if phase_dir.is_symlink() or not phase_dir.is_dir():
                if phases:
                    findings.append({"severity": "Major", "statement": "selected phase is missing or a symlink",
                                     "where": _rel(phase_dir, project_root)})
                continue
            manifest = phase_dir / "manifest.json"
            if manifest.is_file():
                scanned = _scan_manifest(manifest, project_root, findings, artifacts)
                manifests.append(scanned["manifest"])
                drift.extend(scanned["evidence_drift"])
            elif artifacts:
                findings.append({"severity": "Major", "statement": "selected phase has no manifest for artifact audit",
                                 "where": _rel(manifest, project_root)})
            verdicts.extend(_scan_verdicts(phase_dir, project_root, findings))
        runs.append({
            "run_id": run_dir.name,
            "revisions": _max_revision(events, state),
            "terminal": str(state.get("run_status") or state.get("status") or "unknown"),
            "phase_state": state.get("phase_state"),
            "event_count": len(events),
            "events": events[:SINK_LIMIT],
            "manifests": manifests,
            "gate_verdicts": verdicts,
            "evidence_drift": drift,
        })
        for entry in drift:
            findings.append({
                "severity": "Major",
                "statement": f"evidence {entry['kind']} in {entry['manifest']}: {entry['path']}",
                "where": entry["manifest"],
            })
    return runs, findings


def scan_harness(project_root: Path) -> dict:
    """Hook observations and trajectory volume from .harness-state."""
    harness = {"observations": {}, "trajectories": {}}
    state_root = project_root / ".harness-state"
    observations = state_root / "observations"
    if observations.is_dir():
        for path in sorted(observations.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                observed = data.get("observed") if isinstance(data, dict) else None
                harness["observations"][path.stem] = observed if isinstance(observed, dict) else {}
            except (OSError, ValueError):
                harness["observations"][path.stem] = {"error": "unparseable"}
    trajectories = state_root / "trajectories"
    if trajectories.is_dir():
        for run_dir in sorted(p for p in trajectories.iterdir() if p.is_dir()):
            files = [p for p in run_dir.iterdir() if p.is_file()]
            harness["trajectories"][run_dir.name] = {
                "files": len(files),
                "bytes": sum(p.stat().st_size for p in files),
            }
    return harness


def build_model(project_root: Path, run_ids: list[str] | None = None, phases: list[str] | None = None,
                include_harness: bool = False, artifacts: list[str] | None = None) -> dict:
    if phases and not run_ids:
        raise ValueError("phase scope requires at least one run id")
    if artifacts and (not run_ids or not phases or len(phases) != 1):
        raise ValueError("artifact scope requires --run-id and exactly one --phase")
    runs, findings = scan_runs(project_root, run_ids, phases, artifacts)
    harness = scan_harness(project_root) if include_harness or not run_ids else {"not_run": "outside selected run scope"}
    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"F-{index}"
    order = {name: pos for pos, name in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order.get(f["severity"], len(SEVERITIES)), f["id"]))
    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"F-{index}"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool_version": TOOL_VERSION,
        "project_root": str(project_root),
        "runs": runs,
        "harness": harness,
        "findings": findings,
        "scope": {"run_ids": run_ids, "phases": phases, "artifacts": artifacts,
                  "harness_included": include_harness or not run_ids},
    }


# ------------------------------------------------------------------- rendering
def render_json(model: dict) -> str:
    return json.dumps(model, sort_keys=True, indent=2) + "\n"


_CSS = """
:root{--bg:#ffffff;--fg:#1a1d21;--muted:#5c6470;--card:#f6f7f9;--accent:#2563eb;
--sev-critical:#b91c1c;--sev-major:#b45309;--sev-minor:#4d7c0f;--sev-info:#5c6470;
--border:#d8dce2}
@media (prefers-color-scheme: dark){
:root{--bg:#111418;--fg:#e6e9ec;--muted:#9aa4b0;--card:#1a1f26;--accent:#7aa2f7;
--sev-critical:#f87171;--sev-major:#fbbf24;--sev-minor:#a3e635;--sev-info:#9aa4b0;
--border:#2a313a}}
html[data-theme="dark"]{--bg:#111418;--fg:#e6e9ec;--muted:#9aa4b0;--card:#1a1f26;
--accent:#7aa2f7;--sev-critical:#f87171;--sev-major:#fbbf24;--sev-minor:#a3e635;
--sev-info:#9aa4b0;--border:#2a313a}
html[data-theme="light"]{--bg:#ffffff;--fg:#1a1d21;--muted:#5c6470;--card:#f6f7f9;
--accent:#2563eb;--sev-critical:#b91c1c;--sev-major:#b45309;--sev-minor:#4d7c0f;
--sev-info:#5c6470;--border:#d8dce2}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:60rem;margin:0 auto;padding:32px 16px}
h1{font-size:20px}h2{font-size:17px}h3{font-size:15px}
.summary{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid var(--border);padding:8px 12px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}
.chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;
color:#fff;white-space:nowrap}
.chip.critical{background:var(--sev-critical)}.chip.major{background:var(--sev-major);
color:#1a1d21}.chip.minor{background:var(--sev-minor);color:#1a1d21}
.chip.info{background:var(--sev-info)}
a,button{color:var(--accent)}
button{background:var(--card);border:1px solid var(--border);border-radius:8px;
padding:6px 12px;cursor:pointer}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{overflow-x:auto}
@media (max-width: 960px){.summary{grid-template-columns:1fr}}
@media (max-width: 640px){main{padding:16px 8px}th,td{display:block;border:none;
border-bottom:1px solid var(--border)}.chip{margin-bottom:4px}}
"""


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def render_html(model: dict) -> str:
    """IF-3: one self-contained document; every model-derived string escaped."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(TOOL_NAME)} report</title>",
        f"<style>{_CSS}</style>",
        "</head><body><main>",
        f"<h1>{_esc(TOOL_NAME)} report</h1>",
        f"<p>Generated {_esc(model['generated_at'])} - tool {_esc(model['tool_version'])}"
        f" - root {_esc(model['project_root'])}</p>",
        '<button type="button" id="theme-toggle" aria-pressed="false">Toggle theme</button>',
    ]
    findings = model["findings"]
    counts = {sev: sum(1 for f in findings if f["severity"] == sev) for sev in SEVERITIES}
    parts.append("<h2>Summary</h2><div class=\"summary\">")
    parts.append(f"<div class=\"card\">Runs audited<br><strong>{_esc(len(model['runs']))}</strong></div>")
    for sev in SEVERITIES:
        parts.append(f"<div class=\"card\">{sev} findings<br><strong>{_esc(counts[sev])}</strong></div>")
    parts.append("</div>")

    parts.append("<h2>Runs</h2>")
    for run in model["runs"]:
        parts.append('<div class="card">')
        parts.append(f"<h3>Run {_esc(run['run_id'])}</h3>")
        parts.append(f"<p>Revisions {_esc(run['revisions'])} - terminal {_esc(run['terminal'])}"
                     f" - phase {_esc(run['phase_state'])} - events {_esc(run['event_count'])}</p>")
        if run["gate_verdicts"]:
            parts.append('<div class="wrap"><table><tr><th>Boundary</th><th>Gate</th>'
                         "<th>Verdict</th><th>Mechanical pass</th><th>Shipped spec</th></tr>")
            for verdict in run["gate_verdicts"]:
                parts.append(
                    "<tr>"
                    f"<td>{_esc(verdict['boundary'])}</td><td>{_esc(verdict['gate'])}</td>"
                    f"<td>{_esc(verdict['verdict'])}</td><td>{_esc(verdict['pass'])}</td>"
                    f"<td>{_esc(verdict['gate_spec_is_shipped'])}</td></tr>")
            parts.append("</table></div>")
        for entry in run["evidence_drift"]:
            parts.append(f"<p>Evidence drift ({_esc(entry['kind'])}): {_esc(entry['path'])}"
                         f" in {_esc(entry['manifest'])}</p>")
        parts.append("</div>")

    parts.append("<h2>Findings</h2>")
    if not findings:
        parts.append("<p>No findings.</p>")
    for finding in findings:
        sev = str(finding["severity"]).lower()
        parts.append('<div class="card">')
        parts.append(f'<p><span class="chip {_esc(sev)}">{_esc(finding["severity"])}</span> '
                     f"<strong>{_esc(finding['id'])}</strong> {_esc(finding['statement'])}</p>")
        parts.append(f"<p>Where: {_esc(finding['where'])}</p>")
        parts.append("</div>")

    observations = model["harness"].get("observations", {})
    parts.append("<h2>Harness</h2><div class=\"wrap\"><table><tr><th>Hook</th><th>Last observed</th></tr>")
    for name, observed in sorted(observations.items()):
        parts.append(f"<tr><td>{_esc(name)}</td>"
                     f"<td>{_esc(observed.get('at', 'never'))} "
                     f"({_esc(observed.get('count', 0))} calls)</td></tr>")
    parts.append("</table></div>")
    parts.append(
        "<script>(function(){var b=document.getElementById('theme-toggle');"
        "b.addEventListener('click',function(){var r=document.documentElement;"
        "var d=r.getAttribute('data-theme')==='dark';"
        "r.setAttribute('data-theme',d?'light':'dark');"
        "b.setAttribute('aria-pressed',String(!d));});})();</script>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


# ------------------------------------------------------------------------- cli
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--format", choices=("json", "html", "both"), default="both")
    parser.add_argument("--fail-on", choices=("none", "high", "any"), default="none")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--run-id", action="append", help="audit only this changed run; repeat to select several")
    parser.add_argument("--phase", action="append", help="audit only this affected phase (requires --run-id)")
    parser.add_argument("--include-harness", action="store_true", help="also audit global harness observations in a scoped run")
    parser.add_argument("--artifact", action="append", help="hash only this changed manifest-relative artifact (requires one --phase)")
    args = parser.parse_args(argv)
    if args.version:
        print(f"{TOOL_NAME} {TOOL_VERSION}")
        return 0
    if not args.out:
        parser.error("--out is required unless --version is given")
    root = Path(args.project_root)
    if not root.is_dir():
        parser.error(f"--project-root is not a directory: {root}")
    try:
        model = build_model(root, args.run_id, args.phase, args.include_harness, args.artifact)
    except ValueError as exc:
        parser.error(str(exc))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    if args.format in ("json", "both"):
        (out / "report.json").write_text(render_json(model), encoding="utf-8")
        written.append("report.json")
    if args.format in ("html", "both"):
        (out / "report.html").write_text(render_html(model), encoding="utf-8")
        written.append("report.html")
    findings = model["findings"]
    high = sum(1 for f in findings if f["severity"] in ("Critical", "Major"))
    print(f"{TOOL_NAME}: {len(model['runs'])} runs, {len(findings)} findings, wrote {', '.join(written)}")
    if args.fail_on == "high" and high:
        return 1
    if args.fail_on == "any" and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
