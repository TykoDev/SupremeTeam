#!/usr/bin/env python3
"""The save-path taxonomy, stated once.

``save-ownership.yaml`` is the policy; this module is the code's copy of the
parts programs need. The resolver, the run-record writer, and the reader import
these names instead of restating them, and ``validation/test_save_contracts.py``
fails when this module and the policy disagree. Stdlib only and no I/O: the hooks
import it on every host event.
"""
from __future__ import annotations

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

PHASE_DIRECTORIES = ("intake", "design", "build", "review", "security", "investigation", "qa", "taste",
                     "redesign", "delivery", "release", "skill-creation")
PHASE_SUBDIRECTORIES = ("reports", "artifacts", "evidence", "packages")
# Files a phase lead writes directly in the phase directory; the second group is
# the intake phase's own (class grilling-log).
PHASE_ROOT_FILES = ("report_*.md", "deliverable_*.md", "review-packet.md")
INTAKE_ROOT_FILES = ("report_grilling.md", "intake-brief.md")

SCHEMA_VERSION = 1
ACTIVE_STATUSES = frozenset({"active", "paused", "awaiting-input"})
TERMINAL_STATUSES = frozenset({"complete", "blocked", "released"})
STALE_AFTER_SECONDS = 30 * 60
# A heartbeat this far ahead of the clock cannot be trusted, so it reads as stale
# and is reclaimed through `recover`, not honoured for ever.
FUTURE_SKEW_SECONDS = 5 * 60
