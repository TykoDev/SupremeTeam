---
name: audit-improve
description: >-
  Audits SupremeTeam harness and saved-run failures, then routes observed skill
  defects through skill-maker to develop, verify, and propose self-improvements.
  Use for an explicit /audit-improve trigger or a harness failure advisory.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Audit and improve the harness

## Boundary

This skill interprets a bounded runtime audit and coordinates a proposed change.
The hook at `../harness/hooks/audit_improve.py` is a deterministic evidence
collector. It cannot invoke an AI skill, determine root cause, or make changes.
An explicit `/audit-improve` invocation can run its read-only audit directly.
When a defect is supported and an improvement is requested, route the scoped
change through `admiral` and `skill-maker` so it joins the appropriate run and
approval lineage. An active session pin still governs its run.

The hook's automatic call writes only a cooldown timestamp to the harness
observations class. It reads run state, audit events, gate verdicts, and tool
trajectories. Its report is not gate evidence and must not be treated as a
definitive defect list. An explicit `--run` is read-only.

## Trigger

- User invokes `/audit-improve`, asks to audit harness or skill reliability, or
  requests self-improvements based on runtime failures.
- The `PostToolUse` hook emits an `audit-improve` advisory after repeated
  failures and the audit cooldown allows a new report.
- Do not start an improvement loop from a lone failed tool call or a generic
  informational count.

## Procedure

1. **Collect.** Run `python skills/harness/hooks/audit_improve.py --run` from the
   project root. Keep its JSON output in the active run's appropriate report or
   evidence class through the phase owner; outside a run, retain it in the
   current task context. Never write a new file under a generated root without
   a declared writer and destination. Record the audit time and the run
   revision inspected. If the command exits unsuccessfully or emits no valid
   JSON, report the audit unavailable and inspect the source of that failure;
   do not infer that the runtime is healthy. Missing generated roots are
   reported as `save_root_missing` or `harness_root_missing` and may simply
   mean no run has started.
2. **Classify coverage.** Check `coverage.runs_truncated`,
   `coverage.phase_files_truncated`, `coverage.trajectories_truncated`,
   `coverage.time_truncated`, `coverage.audit_tails_truncated`, and any
   `unreadable_records`. If coverage is
   incomplete, narrow the run or source evidence before drawing a conclusion.
   The 24-run, 80-phase-file-per-run, 80-trajectory, 256 KiB record, and two
   second time limits are deliberate. Do not enlarge them just to make an
   anomaly disappear.
3. **Corroborate.** For each Major finding and recurring failure, inspect the
   named canonical source and the relevant owner code. The report hashes run
   identifiers and excludes raw errors, so use authorized local files to
   correlate a finding with the actual run. Match `run_history[].run` and
   `trajectory_history[].run` to the SHA-256 prefix of local run directory
   names; match `trajectory_history[].trajectory` to the hashed file name.
   Use `record_errors[].run` and `record_errors[].trajectory` to locate
   unreadable records without exposing their content in the report.
   Read `_audit-trail.md` and `_state.md`
   without editing them. Use `save_run.py status` for authoritative run status.
   Distinguish malformed state, a test fixture, a transient environment error,
   and a reproducible skill or harness defect. Record exact source paths,
   revisions, and a minimal reproduction, with credentials redacted.
4. **Route improvement.** If a skill defect is supported, hand the scoped
   finding, reproduction, acceptance criteria, and target skill path through
   `admiral` to `skill-maker` in Improve or Review mode. Skill-maker delegates writing to
   `skill-creator` and independent judgment to `skill-reviewer`. A harness code
   defect routes to the owning build or investigation phase; request
   `skill-maker` only if the skill instructions also need revision. Preserve
   the difference between an observed failure and an inferred cause.

   Use this handoff payload in the active run, preserving its Save Context and
   session pin: target skill and owner; exact source path and revision; hashed
   audit finding and correlated canonical run path; redacted reproduction;
   expected behavior and acceptance tests; known coverage limits. Ask
   `skill-maker` for an Improve or Review result with its scorecard, changed
   artifact list, validation evidence, and remaining findings.
5. **Develop and verify.** Produce a concrete diff under the owning phase's
   write boundary, focused tests for the reproduced failure, a baseline versus
   changed result, and the skill-maker scorecard or validation report when a
   skill changes. Run the appropriate gate self-check; report a failed or
   unavailable check as such. Use the designated writers and recovery procedures
   for save, guard, and preference records.
6. **Propose.** Give the user the source-linked finding, proposed diff, tests,
   scorecard or reviewer verdict, and residual risks. Do not auto-register
   hooks, install skills, publish packages, or apply a proposed change to an
   external host. Keep the proposal reviewable. If no defect is corroborated,
   report that result and the evidence limit; do not manufacture an improvement.

## Report shape

Return:

- Outcome: proposed improvement, no supported defect, or investigation needed.
- Evidence: report summary, source paths, run revision, reproduction and test
  results; label inference separately.
- Proposed change: target owner, changed files or patch, skill-maker handoff and
  reviewer result where applicable.
- Open risks and next action: including missing coverage, failed validation, and
  any external activation step left for an authorized owner.

Use Critical | Major | Minor | Info for findings. Never describe a hook's
advisory as proof that skill-maker has run; verify the actual review and
validation records before claiming an improvement is ready.

## Worked handoff example

An audit reports `record_errors: [{record: "state", reason: "too_large",
run: "<hash>"}]` and a matching `run_history` entry with `degraded: 2`.
After matching the hash to a local run, read its canonical audit trail and
reproduce the same failure in a disposable fixture. A suitable handoff reads:

> Active Save Context: run `<run-id>`, revision 4, owner `admiral`; target
> `skills/session-memory/SKILL.md` at revision `<commit>`; source
> `skillset-saves/runs/<run-id>/_state.md` (hashed run key `<hash>`). Observed:
> two degraded writes and an oversized state record. Reproduction: a redacted
> fixture with a large checkpoint fails. Hypothesis: the skill's checkpoint
> guidance permits unbounded payloads; verify against the writer before editing.
> Acceptance: a bounded checkpoint succeeds, the save contract suite passes,
> and skill-maker returns an Improve scorecard, changed artifact list, and
> residual findings.

If the evidence points only to a missing external dependency, report that
finding without proposing a skill edit.
