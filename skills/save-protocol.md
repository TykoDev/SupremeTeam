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

## §1 Layout

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
      manifest.json                  #   qa, taste, skill-creation, delivery, release
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
`skill-creation/` the skill-maker pipeline, and `release/` the release pipeline
(`ship`). `intake/` and `delivery/` are `admiral`'s own phase directories:
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
| `packages/` | exported archives | `my-skill.skill`, `release-bundle.zip` |

Application source stays in the application's own layout; it is never copied
wholesale into a run. Evidence that depends on it binds to it through typed
record `inputs` (`path` + `sha256`) so stale evidence fails the gate.
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
[save-ownership.yaml](save-ownership.yaml): one writer per path class (core run
record, grilling log, phase manifest, reports, artifacts, evidence, packages,
gate verdict, harness guards, harness trajectories, harness observations).
[ownership.yaml](ownership.yaml) keeps the artifact-level owner map, and
`validation/test_save_contracts.py` checks that the two agree. Writing outside
your class, or writing a core run file by any means other than `save_run.py`,
is a write-ownership violation; the pre-tool hook denies edit-tool writes to
core run files and the reader classifies an incoherent result as corrupt.

Checkpoint discipline: checkpoint before every delegation and at every return or
boundary (`save_run.py checkpoint --expect-revision <n> --evidence <path>`).
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
