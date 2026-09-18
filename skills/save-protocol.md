# Save Protocol

Persist lifecycle state under `skillset-saves/` so another session can resume
from evidence rather than memory. `admiral` orchestrates; `session-memory` owns
the run record and writes it only through `harness/hooks/save_run.py`.

## Contents

- §1 Layout
- §2 Startup
- §3 Ownership
- §4 State and audit
- §5 Resume and rewind
- Save Context block
- Enforcement
- Failure paths

## §1 Layout

Everything Supreme Team creates inside a project lives under `skillset-saves/`
or `.harness-state/` ([save-ownership.yaml](save-ownership.yaml)
`generated_roots`). `skillset-saves/` holds run state, run artifacts, and
project preferences; `.harness-state/` holds guard records, trajectories,
observations, test scratch (`test-work/`), skill-creator reports and
workspaces, and packages built outside a run (`packages/`). The only exception
is application source, which stays in the application's layout. A script run
from a subdirectory still writes at the project root, because the hook state
helper and every `--project-root` default walk up to the nearest
`skillset-saves/`, `.harness-state/`, or `.git`; `scripts/output_paths.py`
resolves every kind under these roots and rejects escapes.

```text
skillset-saves/
  _latest.md                         # pointer (schema 1): run_id, revision, updated_at
  runs/{run-id}/
    _state.md                        # run state (writer: save_run.py)
    _lock.md                         # run lock with heartbeat (writer: save_run.py)
    _audit-trail.md                  # append-only events (writer: save_run.py)
    _journal.json                    # publish journal; present only mid-publish
    _history/                        # rev-<n>.state.json / rev-<n>.lock.json snapshots
    intake/report_grilling.md        # decisions artifact (writer: admiral)
    {phase}/                         # design, build, review, security, investigation,
      manifest.json                  #   qa, taste, redesign, skill-creation, delivery, release
      reports/
      artifacts/
      evidence/
      packages/
      verdict_{boundary}.json        # writer: the phase gatekeeper (check.py --verdict-out)
      verdict_{boundary}.cross-stage.json  # writer: gatekeeper-admiral, beside the phase record
```

`design/`, `build/`, and `review/` hold the three delivery phases owned by
`commander`, `build-management`, and `code-chief`. `security/` holds the
security pipeline (`cso`), `investigation/` the investigation pipeline
(`investigate`), `qa/` the testing pipeline (`qa`), `taste/` the Taste
preference pipeline (`taste`; the durable preference store itself lives at
`skillset-saves/preferences/` and is written only by `taste_prefs.py`),
`redesign/` the redesign pipeline (`redesign`), `skill-creation/` the skill-maker
pipeline, and `release/` the release pipeline (`ship`). `intake/` and `delivery/` are `admiral`'s own phase directories:
`delivery/reports/handoff_{boundary}.md` is the cross-stage handoff record for
each boundary and `delivery/reports/delivery-package.md` the final delivery
package. A gate produces two verdict records in the phase directory: the phase
gatekeeper writes `verdict_{boundary}.json`, and `gatekeeper-admiral` re-validates
with `--prior` and writes `verdict_{boundary}.cross-stage.json` beside it, so
neither record overwrites the other. The grilling
log lives at `intake/report_grilling.md` and is the hashed artifact behind the
`decisions` gate key; a phase manifest references it as
`../intake/report_grilling.md`, which the gate admits because the run directory
is the authorised evidence root ([gates.yaml](gates.yaml)
`evidence_rules.evidence_root`).

Each phase directory has four governed subdirectories:

| Subdirectory | Holds | Examples |
| --- | --- | --- |
| `reports/` | reports, plans, summaries | `report_plan.md`, `architecture.md`, `review-packet.md` |
| `artifacts/` | normalized data, generated tokens and components, snapshots | `tokens.css`, `component-template.md` |
| `evidence/` | command logs, scan records, captures | `tests.log`, `scan-pip-audit.json`, `capture-1280-dark.png` |
| `evidence/coverage/` | coverage data files and reports | `.coverage`, `coverage.xml`, `html/index.html` |
| `packages/` | exported archives | `my-skill.skill`, `release-bundle.zip` |

Coverage output is run evidence, never project-root residue. Resolve its
destination with `scripts/output_paths.py --kind coverage`
(`skillset-saves/runs/<run>/<phase>/evidence/coverage/<name>`) and point the
runner at it before it starts — `COVERAGE_FILE` / `--data-file`,
`--cov-report=<fmt>:<dest>/...`, `--coverage.reportsDirectory`, or
`--report-dir` plus `--temp-dir`. Never run coverage in parallel or per-process
mode (`-p`, `--parallel-mode`, `parallel = True`) unless the same command
finishes with `coverage combine` into that destination, and never loop a
coverage run per test file: per-process mode with nothing combining it is how an
observed run produced a `.coverage` tree of over three thousand files at a
project root in under two minutes. When a step ends, nothing named `.coverage`,
`.coverage.*`, `.coverage/`, `htmlcov/`, or `.nyc_output/` remains at the project
root. `harness/hooks/post_tool_use.py` relocates what is left after a command
action — into the active run's `evidence/coverage/`, or, with no active run,
into `.harness-state/test-work/coverage-residue/<timestamp>/` — and never
deletes anything; a sweep that had to run means the destination was never named.

Application source stays in the application's own layout; it is never copied
wholesale into a run. Evidence that depends on it binds to it through typed
record `inputs` (`path` + `sha256`) so stale evidence fails the gate. Every
sha256 the protocol records is line-ending agnostic: text is folded to LF before
hashing and binary is hashed byte-for-byte (`scripts/data_formats.py`
`content_sha256`, printed by `python skills/scripts/content_hash.py <path>`), so
a CRLF checkout and an LF checkout agree and `sha256sum` on a CRLF file is the
wrong value.
`scripts/output_paths.py` resolves every kind to its destination and rejects
escapes.

`_latest.md` is only a pointer. Scan `runs/` when it is absent, stale, or
conflicts with a reclaimable active run.

Canonical pointer and run records use schema version 1 and are written as JSON
(valid YAML, read by `harness/hooks/_saves.py` through
`scripts/data_formats.py`). The pointer is deliberately small and must
dereference one run without relying on a text scan:

~~~yaml
schema_version: 1
run_id: 2026-04-23_dashboard-redesign_a3f9k2
revision: 1
updated_at: 2026-04-23T12:00:00Z
~~~

Each run state records `run_id`, `status`, `session_pin`, `revision`,
`parent_revision`, `active_owner`, `evidence_paths`, `artifact_hashes`, and
`timestamp`. Its lock records `run_id`, `owner`, `status` (`held` or
`released`), `session_pin`, `revision`, and an ISO-8601 `heartbeat`. Evidence
paths are relative to the project root and must exist. Active state requires a
pinned, held lock; terminal state requires an unpinned, released lock. The
shared parser is `harness/hooks/_saves.py`, used by readiness, the
prompt-submit hook, and the gate checker's run-root verification.

## §2 Startup

1. Classify state as active, inactive, complete, stale, orphaned, conflicting,
   corrupt, interrupted, missing, or unreadable with
   `python skills/harness/hooks/save_run.py status --run-id <id>` (or the
   readiness diagnostic). Only a coherent fresh active or orphaned record
   reinforces the session pin.
2. Verify lock owner, heartbeat, status, revision lineage, and referenced
   artifacts. Heartbeat contract: the heartbeat is an ISO-8601 `heartbeat:`
   timestamp field inside the run's `_lock.md`, refreshed on every checkpoint or
   `heartbeat` operation and, between operations, by the harness hooks on real
   host tool activity (`harness/hooks/_state.py` `refresh_run_heartbeat`: only a
   payload carrying a host session id, only a held, pinned, coherent,
   non-interrupted, still-fresh lock, throttled to once per five minutes,
   written through `save_run.py`'s `heartbeat` as the lock owner with
   `heartbeat_source: hook:<event>`; it never revives a stale lock). A lock is
   stale when its heartbeat is older than 30 minutes, which with hooks
   registered means 30 minutes without any host activity in the project.
   Reclaim only through `save_run.py recover --reason ...`, which records the
   stale lock (path, heartbeat, owner, sha256) in the audit trail first and
   refuses a fresh lock or a competing active run.
3. Resume a single coherent active run automatically. A stale pointer, stale
   lock, released run, conflicting active set, schema-invalid record, invalid
   revision lineage, or missing evidence never reinforces the session pin.
   Rebuild a stale pointer only after proving the target run (`heartbeat`
   rewrites it from the run).
4. For a new run, `save_run.py create --run-id <id> --evidence <path>` performs
   the write/read/delete probe, refuses while another run holds the pin
   (active, orphaned, conflicting, or stale: reclaim the old run with
   `recover --reason` and close it with `complete`, `block`, or `release`
   first, because a second held run beside a stale one leaves both
   `conflicting` and neither pinnable), and publishes revision 1 with the
   pointer.
4b. **Manual write-capability probe (agent mode).** `create`'s internal probe
   runs *inside* `create`, so it reports a read-only workspace only by failing the
   run's first write. An agent host that must know before it commits to a run —
   and that re-checks at every heartbeat — runs this probe instead, at a path
   deliberately outside the core-run-record class so no sanctioned writer is
   bypassed:

   - Path: `skillset-saves/_probe-{run-id}.tmp`, one per run, never under
     `runs/`. `pre_tool_use.py` Rule C covers `_latest.md` and `runs/*/` core
     files; this path is neither, so an ordinary edit tool may write it.
   - Steps: write a short ASCII payload, read it back and verify byte equality,
     then delete it. Any step failing is a probe failure.
   - Recording: the result is state, not a trail line — carry it as
     `--set persistence_active=<true|false> --set persistence_probe_result=<ok|failed|skipped>`
     on the next `save_run.py checkpoint`. There is no audit operation that
     accepts a probe event.
   - Cadence: before the first save, and again at every heartbeat refresh.
   - On failure: set `Persistence active: no`, warn once, attempt read-only
     resume from any readable latest artifacts, and continue transiently only
     when no coherent boundary can be proven.

   The two probes are complementary, not alternatives: this one is a pre-flight
   check the agent controls, `create`'s is the writer proving its own first
   write. Neither substitutes for the other, and the temp file is deleted in
   both the pass and the fail path — a `_probe-*.tmp` left behind is a defect.

5. Mark persistence active only after `create` returns `result: ok`. A
   `degraded` result (exit 2) means the write failed and nothing coherent was
   published: warn once, keep readable evidence, and use transient mode only
   when resume cannot be proven. A `refused` result (exit 1) is a contract
   violation to resolve, never something to work around by hand-editing files.

## §3 Ownership

`admiral` orchestrates; `session-memory` owns the run lifecycle record and
writes it only through `save_run.py` (`create`, `checkpoint`, `heartbeat`,
`complete`, `block`, `release`, `recover`, `status`). Each phase lead owns its
phase directory (`admiral` leads `intake/` and `delivery/`); a lead never
creates nested per-specialist directories or phase-state files, because no
declared path class covers them and phase state lives in the run record.
Specialists write only the artifact named in their delegation,
at the destination the delegation names. Gatekeepers write verdict records but
never modify submissions.

The authoritative, machine-readable path policy is
[save-ownership.yaml](save-ownership.yaml): one writer per path class. Sixteen
are declared; the run-facing ones are the core run record, grilling log, phase
manifest, reports, artifacts, evidence, packages, gate verdict, harness guards,
harness trajectories, and harness observations, with the preference store, test
scratch, the two skill-eval classes, and standalone packages alongside them.
[ownership.yaml](ownership.yaml) keeps the artifact-level owner map, and
`validation/test_save_contracts.py` checks that the two agree. Writing outside
your class, or writing a core run file by any means other than `save_run.py`,
is a write-ownership violation; the pre-tool hook denies edit-tool writes to
core run files and the reader classifies an incoherent result as corrupt.

Checkpoint discipline: checkpoint before every delegation and at every return or
boundary (`save_run.py checkpoint --run-id <run-id> --owner <owner> --expect-revision <n> --evidence <path>`).
Each checkpoint snapshots the previous revision into `_history/`, registers
evidence hashes, refreshes the heartbeat, and publishes state, lock, and pointer
atomically behind a `_journal.json`; an interrupted publish is visible as
`interrupted` and is repaired with `recover --rollback`. While the journal is
present, `checkpoint`, `heartbeat`, `complete`, `block`, `release`, and a
non-rollback `recover` are all refused. A checkpoint resumes a `released` run
(audit event `resume`) only when no other run holds the pin; a checkpoint on a
`complete` or `blocked` run is refused unless `--reopen` is passed (audit event
`reopen`), because a post-completion change re-enters through REVISE as a
deliberate new revision, never as a routine checkpoint landing on a closed run.
A checkpoint or heartbeat on a stale lock is refused; reclaim it with
`recover --reason` so the reclaim leaves evidence.

## §4 State and audit

Record run id, status, session pin, execution mode, persistence result, active
owner, skills engaged, artifact revisions and hashes, verdicts, earliest
incomplete boundary, blockers, and next action (`--set key=value` for
non-reserved fields). Append events; never erase prior evidence. Preserve
superseded revisions with clear lineage (`parent_revision`, `_history/`).

## §5 Resume and rewind

Re-probe execution capabilities on every resume and before every boundary. If an
upstream revision changes, invalidate only verdicts that depend on it and rewind
to the earliest affected boundary; the gate's verdict record (`verdict_id`,
`gate_spec_digest`, `package_fingerprint`) is reusable only when
`check.py --prior` reports `prior_reusable: true`. Never combine conflicting
histories silently.

## Save Context block

Include this block verbatim in every governed delegation. The canonical field
set lives in [contracts/handoff-templates.md](contracts/handoff-templates.md);
neither file may drop a field the other carries.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: {phase}
- Save path: skillset-saves/runs/{run-id}/{phase}/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Preamble tier: {0|1|2|3} + rationale
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {owner}
- Expected artifact: {artifact}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: {gate boundary for the returned package}
```

A delegate that receives `Persistence active: no` treats every save call as a
no-op and returns its deliverable inline. A delegate that receives
`Session pin: true` honors admiral routing and does not spawn a parallel run.

## Enforcement

This is one of the more mechanical contracts in the layer: the destination
resolver refuses an unsafe path, the lifecycle writer refuses an incoherent
operation, and the pre-tool hook refuses a direct write to a core run file. What
none of them checks is whether the *right owner* wrote a file that is otherwise
legal, so the ownership rules in §3 stay judgement even where the paths they
govern are declared machine-readably.

Every clause of §1–§5 is labelled below; a clause not named here is judgement.
This file is itself read by a comparator:
`validation/test_save_contracts.py`
`OwnershipAgreementTests.test_save_protocol_points_at_the_machine_contracts`
asserts that it names `save-ownership.yaml`, `save_run.py`, and `_journal.json`,
so deleting any of those three pointers fails the suite.

| Clause of §1–§5 | Backing | What fails |
|-----------------|---------|------------|
| §1 Everything generated lands under `skillset-saves/` or `.harness-state/` | Machine-checked by `validation/test_save_contracts.py` `GeneratedRootPolicyTests` and by [`scripts/validate_manifests.py`](scripts/validate_manifests.py) | `save-ownership.yaml: generated_roots must be exactly skillset-saves and .harness-state`; a resolver kind landing outside a declared root fails `test_every_project_kind_resolves_under_a_generated_root` |
| §1 `scripts/output_paths.py` resolves every kind and rejects escapes | Machine-checked by `resolve()`; the *refusal* is pinned by `OutputPathTests`, the *kind set* by `GeneratedRootPolicyTests` | `resolve()` raises `ValueError` with `unknown output kind`, `name must be a relative path without traversal`, `run_id must be a single safe path segment`, `core name must be _state.md, _lock.md, or _audit-trail.md`, `phase must be one of [...]`, or `resolved path escapes project root`. Read the boundary of the test carefully: `OutputPathTests.test_every_kind_resolves_inside_project` asserts only that `ValueError` is raised, for three of those six cases, and never inspects the message — so the wording above is the script's, verified by running it, not a string any test asserts. `GeneratedRootPolicyTests.test_every_project_kind_resolves_under_a_generated_root` does pin `KINDS`, and the CLI declares `--kind ... choices=sorted(KINDS)`, so the two cannot drift apart. |
| §1 A script run from a subdirectory still writes at the project root | Machine-checked by `GeneratedRootPolicyTests.test_hook_state_root_walks_up_to_the_project_marker` | `_state.find_project_root` returning a subdirectory instead of the nearest marker |
| §1 Every pipeline has a phase directory under a run | Machine-checked by `validate_manifests.py` and `OwnershipAgreementTests.test_every_pipeline_phase_has_a_save_directory` | `save-ownership.yaml: missing phase directory 'qa' for qa` — the pipeline name appears twice in the real message. The test asserts membership directly rather than matching that string. |
| §1 The four governed subdirectories (`reports/`, `artifacts/`, `evidence/`, `packages/`) | Partly machine-checked | `scripts/test_runtime_utilities.py` pins the exact `reports/` destination for every declared pipeline phase, and `output_paths.resolve` composes the other three the same way. That a file was filed under the right one of the four is judgement. |
| §1 Evidence paths are project-relative and must exist | Machine-checked by `save_run.py` and `harness/hooks/_saves.py` | `evidence path must be project-relative without traversal`, `evidence path escapes project root`, `evidence path missing`, `missing evidence path <p>` |
| §1 The run directory is the authorised evidence root, so a phase manifest may reference `../intake/report_grilling.md` | Machine-checked by [`harness/gatekeeper/check.py`](harness/gatekeeper/check.py) against [gates.yaml](gates.yaml) `evidence_rules.evidence_root`, pinned by `harness/gatekeeper/test_gate_run_layout.py` `EvidenceRootTests` | The root widens to the run directory only when the manifest `run_id` matches the directory and `_state.md`; otherwise it is the manifest directory. `test_other_run_evidence_is_rejected`, `test_traversal_absolute_and_unc_paths_are_rejected`, `test_symlink_escape_is_rejected`, and `test_run_id_mismatch_shrinks_root_to_package` each fail a package that reaches outside it. |
| §1 The preference store under `skillset-saves/preferences/` is written only by `taste_prefs.py` | Machine-checked where hooks are registered | `pre_tool_use.py` denies an edit-tool write to `taste.json`, `taste.md`, `taste.journal.jsonl`, `taste.lock`, and `_history/*` under that directory, naming `skills/taste/taste_prefs.py` as the sanctioned writer; `SaveLifecycleTests.test_direct_edit_of_project_taste_state_is_denied_but_reads_pass` executes the hook on all five and confirms a `Read` of the same file is not denied |
| §1 Pointer and run records carry schema version 1 | Machine-checked by `_saves.py` | a record whose `schema_version` is not 1 is classified `corrupt` and never reinforces the pin |
| §1 `_latest.md` is only a pointer; scan `runs/` when it is absent, stale, or conflicting | Judgement | Nothing. `_saves.py` classifies the pointer and `heartbeat` rewrites it from the run, but whether a caller falls back to scanning `runs/` instead of trusting a stale pointer is the caller's discipline. |
| §1 A gate writes two verdict records: `verdict_{boundary}.json` and `verdict_{boundary}.cross-stage.json` beside it | Judgement | Nothing compares those two filenames. `--verdict-out` writes wherever it is pointed, so the `.cross-stage.` suffix that keeps `gatekeeper-admiral` from overwriting the phase record is a naming convention this file carries, not a check. Passing the same `--verdict-out` path twice would silently overwrite. |
| §1 Active state requires a pinned, held lock; terminal state an unpinned, released lock | Machine-checked by `save_run.py` and `_saves.py` | asserted end to end by `SaveLifecycleTests.test_create_checkpoint_heartbeat_complete_lifecycle` |
| §2.1–2.2 State classification, lock verification, and the heartbeat contract | Machine-checked | `save_run.py status` returns the classification; `_state.refresh_run_heartbeat` applies its preconditions and the five-minute throttle; a checkpoint or heartbeat on a stale lock is refused, and `recover --reason` records the stale lock in the audit trail first (`test_stale_lock_recovery_records_evidence`) |
| §2.3 Resume a single coherent active run automatically | Judgement | Nothing. The classification the rule reads is mechanical; acting on it is the orchestrator's discipline. |
| §2.4 `create` probes, refuses a competing pin, and publishes revision 1 | Machine-checked by `save_run.py` | `another run holds the session pin`, plus the write/read/delete probe result (`test_competing_owner_and_wrong_owner_are_refused`) |
| §2.5 Persistence is marked active only after `result: ok` | Judgement | Nothing. The exit codes (0 `ok`, 1 `refused`, 2 `degraded`) are mechanical; whether the caller honours them is not. |
| §3 The core run record has one writer and one tool | Machine-checked by `OwnershipAgreementTests` | the `core-run-record` writer is pinned to `session-memory` and its `save_run.py` tool must exist on disk |
| §3 A direct edit-tool write to a core run file is denied | Machine-checked where hooks are registered | [`harness/hooks/pre_tool_use.py`](harness/hooks/pre_tool_use.py) Rule C denies `Edit`, `Write`, and `NotebookEdit` on `_state.md`, `_lock.md`, `_audit-trail.md`, `_latest.md`, `_journal.json`, and `_history/*`, and denies a *mutating* shell command naming one of them unless it invokes `save_run.py`; pinned by `SaveLifecycleTests.test_direct_edit_of_core_files_is_denied_by_hook` |
| §3 `save-ownership.yaml` and `ownership.yaml` agree | Machine-checked by `OwnershipAgreementTests` | a class whose writer, tool, or pattern contradicts the artifact-level owner map |
| §3 A gatekeeper holds no edit tool | Machine-checked by `validation/test_catalog_contracts.py` `ToolSurfaceTests` | `<name> is a gatekeeper or declared single-writer but grants Edit`. That a gatekeeper never modifies a submission by some other route is judgement. |
| §3 A phase lead owns its phase directory; a specialist writes only its delegated artifact | Judgement | Nothing. No comparator matches a written file against the patterns of its class, so a report written to the wrong phase subdirectory by the right owner fails nothing here — [save-ownership.yaml](save-ownership.yaml) `enforcement.judgement` records the same gap. |
| §3 Checkpoint discipline: expected revision, `_history/` snapshot, journal, `--reopen`, stale-lock refusal | Machine-checked by `save_run.py` | `revision conflict`, `run is <status>; pass --reopen ...`, an `interrupted` classification while `_journal.json` is present, and refusal of `checkpoint`, `heartbeat`, `complete`, `block`, `release`, and non-rollback `recover` until the journal is resolved |
| §4 Reserved state fields cannot be overwritten | Machine-checked by `save_run.py` | `--set may not override reserved field <key>` |
| §4 The audit trail is append-only and superseded revisions are preserved | Machine-checked | the event sequence and `_history/rev-<n>.state.json` are asserted in `SaveLifecycleTests` |
| §4 That the recorded values are true — skills engaged, blockers, next action, verdicts | Judgement | Nothing. No comparator reads a recorded value for accuracy. |
| §5 A verdict is reusable only when `check.py --prior` reports `prior_reusable: true` | Machine-checked by [`harness/gatekeeper/check.py`](harness/gatekeeper/check.py) | a `verdict_id`, `gate_spec_digest`, or `package_fingerprint` mismatch; pinned by `harness/gatekeeper/test_gate_run_layout.py` |
| §5 Re-probe on resume, rewind to the earliest affected boundary, never merge conflicting histories | Judgement | Nothing. The lock and revision mechanics are checked; the choice of rewind point is not. |
| The Save Context field set | Partly machine-checked by `test_catalog_contracts.py` `SaveContextParityTests` | the comparator is discovery-based and anchored on a `Run ID` line, so it compares this copy against the canonical one and skips any file that mentions `Save Context` without carrying that anchor |

## Failure paths

- `create` returns `degraded` (exit 2). The write failed and nothing coherent
  was published. Warn once, keep readable inline evidence, and use transient mode
  only while resume cannot be proven. Do not hand-write the records the probe
  could not write.
- `create`, `checkpoint`, `heartbeat`, `complete`, `block`, `release`, or
  `recover` returns `refused` (exit 1). That is a contract violation with a named
  reason — a revision conflict, a competing pin, a wrong owner, a stale lock, or
  an unresolved journal. Resolve the reason. Editing the record by hand to make
  the next call succeed is the exact bypass Rule C exists to prevent.
- `_journal.json` is present. The run is `interrupted`, and every operation
  except `recover --rollback` is refused so a half-published revision is never
  built on. Roll back, then re-checkpoint.
- The lock is stale (heartbeat older than 30 minutes). Reclaim only with
  `recover --reason`, which records the stale lock's path, heartbeat, owner, and
  sha256 in the audit trail before issuing a new one. A reclaim with no recorded
  reason is refused.
- Two runs are active, or one is active beside a stale one. The state is
  `conflicting` and neither is pinnable. Reclaim the old run and close it with
  `complete`, `block`, or `release` before creating a new one.
- The pointer is stale, missing, or contradicts `runs/`. It is only a pointer:
  scan `runs/`, prove the target run, and let `heartbeat` rewrite the pointer
  from the run. Never rebuild the pointer by hand to name a run you have not
  verified.
- An evidence path named in a checkpoint no longer exists or has moved outside
  the project root. The operation is refused before publication. Restore the path
  or register the evidence at its real destination, resolved with
  `scripts/output_paths.py`.
- A write is attempted at a path no class in
  [save-ownership.yaml](save-ownership.yaml) covers. That is a policy gap, not
  implicit permission: resolve the destination with `output_paths.py` first, and
  if the path is sanctioned but unclassified, record the gap and add the class as
  a contract change rather than writing under an undeclared path.
- This file and [save-ownership.yaml](save-ownership.yaml) disagree about a
  path. The YAML is the machine-readable policy and wins; this file is the prose
  protocol and is the defect. Where this file and [gates.yaml](gates.yaml)
  disagree about what a boundary admits as evidence, `gates.yaml` wins.
