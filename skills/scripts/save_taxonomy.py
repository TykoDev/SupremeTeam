#!/usr/bin/env python3
"""The save-path taxonomy, stated once.

``save-ownership.yaml`` is the policy; this module is the code's copy of the
parts programs need. The resolver, the run-record writer, and the reader import
these names instead of restating them, and ``validation/test_save_contracts.py``
fails when this module and the policy disagree. Stdlib only and no I/O: the hooks
import it on every host event.
"""
from __future__ import annotations

import re

# Everything Supreme Team writes lives under one of these project-relative roots.
GENERATED_ROOTS = ("skillset-saves", ".harness-state")

# The core run record, written only by harness/hooks/save_run.py.
POINTER = "_latest.md"
RUN_RECORD_FILES = ("_state.md", "_lock.md", "_audit-trail.md")
JOURNAL = "_journal.json"
HISTORY = "_history"
# Mutex every run-record mutation holds; it sits at the save root because the
# pointer and the one-held-run rule span every run.
WRITE_LOCK = "_write.lock"

# The one run-id grammar, matched with fullmatch: the writer creates only these ids and
# the path resolver and the hooks' run scope accept only these (``_state.RUN_ID`` is
# held to it by validation/test_save_taxonomy.py). A run an earlier writer created under
# a looser id stays readable and closable; only a new run is held to this.
RUN_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,127}")
RUN_ID_RULE = "1 to 128 letters, digits, '.', '_' or '-', starting with a letter, digit or '_'"

PHASE_DIRECTORIES = ("intake", "design", "build", "review", "security", "investigation", "qa", "taste",
                     "redesign", "delivery", "release", "skill-creation")
PHASE_SUBDIRECTORIES = ("reports", "artifacts", "evidence", "packages")
# Files a phase lead writes directly in the phase directory; the second group is
# the intake phase's own (class grilling-log).
PHASE_ROOT_FILES = ("report_*.md", "deliverable_*.md", "review-packet.md")
INTAKE_ROOT_FILES = ("report_grilling.md", "intake-brief.md")

PROTOCOL_STATES = frozenset({"INTAKE", "DESIGN", "BUILD", "REVIEW", "GATE", "RELEASE", "SAFETY", "REVISE",
                             "ESCALATE", "BLOCKED", "COMPLETE", "TASTE_ACTIVE", "TASTE_GATE_PENDING", "TASTE_GATE_REVISE"})
PHASE_PROTOCOL = {"INTAKE": "INTAKE", "DESIGN": "DESIGN", "REDESIGN": "DESIGN", "BUILD": "BUILD",
                  "REVIEW": "REVIEW", "SECURITY": "REVIEW", "INVESTIGATION": "BUILD", "QA": "REVIEW",
                  "SKILL_CREATION": "BUILD", "CREATE": "BUILD", "IMPROVE": "BUILD", "OPTIMIZE": "BUILD",
                  "PACKAGE": "BUILD", "DELIVERY": "GATE", "RELEASE": "RELEASE"}


def protocol_state_for(phase_state: str) -> str:
    """Normalize saved phase labels; this maps names, it does not authorize an edge."""
    if phase_state in PROTOCOL_STATES:
        return phase_state
    if phase_state in {"RUN_COMPLETE", "DELIVERED"}:
        return "COMPLETE"
    if phase_state == "DISPUTED_AWAITING_USER":
        return "ESCALATE"
    for suffix, state in (("_GATE_PENDING", "GATE"), ("_GATE_REVISE", "REVISE"), ("_ACTIVE", None)):
        if phase_state.endswith(suffix):
            phase = phase_state[:-len(suffix)].replace("-", "_")
            if phase in PHASE_PROTOCOL:
                # Release preparation is GATE-shaped until approval; RELEASE
                # itself is reserved for the authorized external rollout.
                return "GATE" if phase == "RELEASE" and state is None else state or PHASE_PROTOCOL[phase]
    raise ValueError(f"unknown phase_state {phase_state!r}")


SCHEMA_VERSION = 1
ACTIVE_STATUSES = frozenset({"active", "paused", "awaiting-input"})
TERMINAL_STATUSES = frozenset({"complete", "blocked", "released"})
STALE_AFTER_SECONDS = 30 * 60
# A heartbeat this far ahead of the clock cannot be trusted, so it reads as stale
# and is reclaimed through `recover`, not honoured for ever.
FUTURE_SKEW_SECONDS = 5 * 60
