"""Durable, gate-owned REVISE streaks; the third round always goes to the user.

Called only for a valid judgment with --verdict-out. Mechanical self-checks do
not write or count. The canonical sidecar lives beside the manifest, independent
of --prior, submission ids and output filenames. A held boundary needs a new
user-decision reference to reopen; that reference is an operator attestation,
not authentication. History is retained across reopenings.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))
from _fsutil import AdvisoryLock, atomic_write  # noqa: E402


def _fresh(result: dict) -> dict:
    return {"schema_version": 1, "boundary": result["boundary"], "run_id": result.get("run_id"),
            "gates": {}, "rounds": [], "held": False, "events": [], "reopen_refs": []}


def _read(path: Path, result: dict, out: Path, reopening: bool) -> dict:
    if not path.exists():
        # A lost sidecar or an upgrade from legacy verdicts cannot silently
        # manufacture a first round. Preserve the old evidence for the user.
        candidates = set(path.parent.glob("verdict_*.json")) | {out}
        legacy = []
        for candidate in sorted(candidates):
            if candidate.name.endswith((".judgment.json", ".cycles.json")) or not candidate.is_file():
                continue
            record = json.loads(candidate.read_text(encoding="utf-8"))
            if (isinstance(record, dict) and record.get("boundary") == result["boundary"]
                    and isinstance(record.get("judgment"), dict)):
                legacy.append(record)
        if legacy and not reopening:
            raise ValueError("gate cycle history is missing beside existing judgments; preserve them and request a user-decision reference")
        state = _fresh(result)
        if legacy:
            state["held"] = True
            state["events"] = [{"history_unavailable": True, "preserved_verdicts": legacy}]
        return state
    state = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or state.get("schema_version") != 1
            or state.get("boundary") != result["boundary"] or state.get("run_id") != result.get("run_id")
            or not isinstance(state.get("gates"), dict)
            or not isinstance(state.get("held"), bool)
            or any(not isinstance(state.get(k), list) for k in ("rounds", "events", "reopen_refs"))
            or any(not isinstance(v, list) for v in state.get("gates", {}).values())):
        raise ValueError("gate cycle history is malformed or belongs to another boundary/run; preserve it and escalate to user")
    streaks = [state["rounds"], *state["gates"].values()]
    if (any(any(not isinstance(value, str) for value in streak) or len(set(streak)) != len(streak)
            for streak in streaks)
            or (not state["held"] and any(len(streak) >= 3 for streak in streaks))):
        raise ValueError("gate cycle streaks are inconsistent; preserve history and escalate to user")
    return state


def advance(state: dict, result: dict, reopen_reference: str | None = None) -> dict:
    """Update a copied state and the effective judgment; unique revisions count once.

    Per-gate streaks reset on that gate's APPROVED. The shared boundary streak
    resets only on cross-stage APPROVED, so switching gatekeepers cannot evade
    the cap. Once held, even a later APPROVED cannot silently clear it.
    """
    state = copy.deepcopy(state)
    judgment = result["judgment"]
    requested = judgment["verdict"]
    for event in state["events"]:
        if (event.get("revision") is not None and str(event["revision"]).strip() == str(result["revision"]).strip()
                and event.get("package_fingerprint") != result["package_fingerprint"]):
            raise ValueError("idempotency drift on recorded revision; increment revision and preserve prior evidence")
    if reopen_reference is not None:
        if (not reopen_reference.strip() or not state["held"]
                or reopen_reference in state["reopen_refs"]):
            raise ValueError("reopen needs a held boundary and a new, non-empty user-decision reference")
        state["events"].append({"reopened_by_user": reopen_reference, "checked_at": result["checked_at"]})
        state["reopen_refs"].append(reopen_reference)
        state.update(gates={}, rounds=[], held=False)

    gate = judgment["gate"]
    revision = str(result["revision"]).strip()
    streak = state["gates"].setdefault(gate, [])
    if not state["held"]:
        if requested == "REVISE":
            if revision not in streak:
                streak.append(revision)
            if revision not in state["rounds"]:
                state["rounds"].append(revision)
            # This is a safety floor, not a custom-spec setting.
            state["held"] = len(streak) >= 3 or len(state["rounds"]) >= 3
        elif requested == "APPROVED":
            state["gates"][gate] = []
            if gate == "gatekeeper-admiral":
                state["gates"], state["rounds"] = {}, []

    if state["held"]:
        judgment["requested_verdict"] = requested
        judgment["verdict"] = "ESCALATE"
        judgment["escalation"] = {
            "to": "user", "via": "admiral",
            "reason": "Three consecutive REVISE rounds reached cycle_cap: 3; user decision required before further work.",
        }
    result["revision_cycle"] = {"gate": gate, "consecutive_revise": len(state["gates"].get(gate, [])),
                                "boundary_revise_rounds": len(state["rounds"]), "held_for_user": state["held"],
                                "history": f"verdict_{result['boundary']}.cycles.json"}
    # Retain the three actionable packets and deltas, even if a verdict file is
    # overwritten. Retries on the same revision do not grow duplicate events.
    event = {key: copy.deepcopy(result.get(key)) for key in (
        "boundary", "revision", "submission_id", "package_fingerprint", "checked_at", "judgment",
        "revise_packet", "changed_evidence", "unchanged_evidence")}
    signature = (gate, revision, result["package_fingerprint"], judgment["verdict"])
    if not state["events"] or signature != tuple(state["events"][-1].get("signature", [])):
        state["events"].append({**event, "signature": signature})
    return state


def write_verdict(result: dict, manifest: Path, out: Path, reopen_reference: str | None = None) -> None:
    """Lock, advance history, then publish; failed history persistence never approves.

    History is committed first. If publishing fails, a retry sees the same
    revision and does not count it again. Symlinked state/output paths fail loud.
    """
    history = manifest.parent / f"verdict_{result['boundary']}.cycles.json"
    lock_path = history.with_suffix(".lock")
    for path in (history, lock_path, out):
        if path.is_symlink():
            raise ValueError("gate verdict/history paths must not be symlinks")
    if out.resolve() in {history.resolve(), lock_path.resolve(), manifest.resolve()}:
        raise ValueError("verdict output must not overwrite the manifest or cycle history")
    with AdvisoryLock(lock_path, wait=5) as lock:
        if not lock.held:
            raise ValueError("cannot lock gate cycle history; escalate to user")
        state = advance(_read(history, result, out, reopen_reference is not None), result, reopen_reference)
        atomic_write(history, json.dumps(state, indent=2, sort_keys=True), in_place=False)
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(out, json.dumps(result, indent=2, sort_keys=True), in_place=False)


def write_mechanical(result: dict, manifest: Path, out: Path) -> None:
    """A pre-check cannot erase a semantic verdict, cycle history or manifest."""
    if out.is_symlink() or out.resolve() == manifest.resolve() or out.name.endswith((".cycles.json", ".cycles.lock")):
        raise ValueError("mechanical output must not overwrite the manifest or cycle history")
    lock_path = manifest.parent / f"verdict_{result['boundary']}.cycles.lock"
    if lock_path.is_symlink():
        raise ValueError("gate history mutex must not be a symlink")
    with AdvisoryLock(lock_path, wait=5) as lock:
        if not lock.held:
            raise ValueError("cannot lock gate verdict output")
        if out.is_file():
            record = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(record, dict) and isinstance(record.get("judgment"), dict):
                raise ValueError("mechanical pre-check must not overwrite a semantic judgment; omit --verdict-out")
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(out, json.dumps(result, indent=2, sort_keys=True), in_place=False)
