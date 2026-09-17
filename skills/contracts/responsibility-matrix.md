# Responsibility Matrix

## Contents

- Responsibility
- Layer matrix
- Specialists
- Gate coverage
- One-writer rule
- Enforcement
- Failure paths

## Responsibility

This matrix assigns one writer to each lifecycle layer and states the trigger,
inputs, and output. A layer may consult another owner, but it may not silently
take that owner's write boundary.

The matrix mirrors facts that live in the machine manifests. Where it disagrees
with [`../pipelines.yaml`](../pipelines.yaml),
[`../ownership.yaml`](../ownership.yaml),
[`../gates.yaml`](../gates.yaml), or
[`../team-manifest.yaml`](../team-manifest.yaml), the manifest is authoritative
and this file is the defect.

## Layer matrix

| Layer | Trigger | Owner | Inputs | Output | One writer |
|-------|---------|-------|--------|--------|------------|
| INTAKE | New request, resume, or explicit scope change | admiral | User intent, active run evidence, constraints | Bounded brief, tier, grilling log with deferrals and reopen triggers, initial owner, next phase | admiral writes intake, run routing, and the grilling log |
| TASTE | An explicit preference lifecycle request is made: record, scope, promote, revoke, or explain an effective profile | taste | Request intent, target scope, existing global and project entries, outranking requirements | Preference diff, confirmation record, conflict analysis, persistence result, effective profile, consumer handoff | taste writes the preference store and the taste package; taste-review writes the review record |
| DESIGN | Intake is accepted and the problem needs a build decision | commander | Brief, current evidence, constraints | Build contract, architecture, interface contracts, design system, stack lock, traceability, non-goals, risks | commander writes the design package and stack lock; each specialist writes only its named artifact |
| REDESIGN | An existing user-facing surface needs a new design with alternatives to compare | redesign | Surface in scope, parity-defining flows, current source or captures, Taste snapshot | Design inventory, taste grilling log, four directions, four static mocks with their parity and rendering, the recorded selection, then the one living variant built from it with parity and rendered and accessibility evidence, comparison, recorded decision | redesign writes the selection and the redesign package; design-mapper the inventory and both parity records; taste the grilling log; architect the directions; design-qa the mock rendering; prototyper one mock per delegation and the single selected build |
| BUILD | The build contract is approved | build-management | Build contract, locked stack, named artifact boundary | Changed artifact set, test and runtime evidence, security evidence | build-management writes the build package |
| REVIEW | Build output is submitted or a risk requires recheck | code-chief | Submission, hashes, tests, evidence, known risks | Findings, proof gaps, rendered verification, verdict recommendation | code-chief writes the review packet and verdict |
| SECURITY | Security audit, threat model, hardening, or remediation is requested | cso | Scope, threat model inputs, target surface, authorization | Threat model, graded findings, deny-path evidence, remediation plan, residual risk | cso writes the security packet; security-review writes the scan, mr-robot the deny-path evidence |
| INVESTIGATION | The failure mechanism is unclear | investigate | Symptom, logs, runtime clues, environment | Reproduction, evidence chain, mechanism, bounded fix path, residual uncertainty | investigate writes the investigation package and changes no product code |
| QA | Product testing with recorded evidence is requested | qa | Built surface, declared scope, environment | Test matrix, executed probes, defects, fixes applied, residual risk | qa writes the QA package; a report-only run records the sanctioned `fixes_applied` applicability instead of a fix record |
| SKILL CREATION | A skill or coordinated team is requested | skill-maker | Skill intent, trigger language, packaging target | Skills, review scorecard, link and validation reports, package | skill-maker writes the package; skill-creator drafts; skill-reviewer scores |
| GATE | A phase boundary requests advancement | the boundary's gatekeeper | Required artifact, revision lineage, hashes, evidence | APPROVED, REVISE, or ESCALATE with missing facts | the gatekeeper writes the verdict only |
| RELEASE | Gate approves an externally visible delivery | ship | Approved package, deployment settings, rollback, owner intent | Release result, verification evidence, follow-up | ship owns the `release` pipeline and submits `deploy-readiness`; land-and-deploy writes the release record, setup-deploy the deploy config, document-release the notes |
| SAFETY | A destructive, guarded, frozen, or boundary-sensitive action is requested | guard, freeze, or unfreeze | Explicit intent, path boundary, current run, risk evidence | Allow, deny, or guarded next action with audit evidence | the selected guard, freeze, or unfreeze owner writes its record |
| MEMORY | A checkpoint, resume, or durable learning is required | session-memory | Run state, evidence paths, boundary | Run record, audit trail, checkpoint | session-memory writes the run record through save_run.py only |

The RELEASE row's owner agrees with both machine sources: `pipelines.yaml` gives
the `release` pipeline `"owner": "ship"`, and `gates.yaml` names `ship` as the
submitter of `deploy-readiness`. `land-and-deploy` is a stage owner inside that
pipeline and the declared writer of `release-record` in `ownership.yaml`; it
does not own the layer.

## Specialists

The twenty-one specialists declared under `specialists` in
[`../team-manifest.yaml`](../team-manifest.yaml) (researcher, planner,
architect, engineer, design-mapper, prototyper, bob-the-builder, test-builder,
security-builder, cross-check-build-confirm, debugger, health-check,
bug-review, code-review, quality-review, security-review, mr-robot, frontier,
design-qa, devex-review, taste-review) work inside these layers under the
owning lead. That manifest list is the source; this one mirrors it in the same
order. Their write boundaries are the artifact ids in
[`../ownership.yaml`](../ownership.yaml).

The mirror is compared, in one direction. `../validation/test_catalog_contracts.py`
(`DeclaredCoverageTests.test_responsibility_matrix_specialists_match_the_manifest`)
reads this section and fails when a `team-manifest.yaml` specialist is missing
from it, or when the stated count no longer matches. Adding a specialist to the
manifest without adding it here turns that test red. The reverse does not: a name
listed here that the manifest never declares passes, and so does a reordering —
the order above matches the manifest because it was checked by hand, not because
anything compares it.

## Gate coverage

A layer that ends at a gate does not always have a phase gatekeeper. Four of the
ten boundaries in [`../gates.yaml`](../gates.yaml) are validated twice — once
inside the sub-pipeline by a phase gatekeeper, then again by `gatekeeper-admiral`
as the cross-stage handoff. The other six are validated once, by
`gatekeeper-admiral` alone.

| Boundary | Phase gatekeeper | Cross-stage validator | Explicit `phase-gate` stage in `pipelines.yaml` |
|----------|------------------|-----------------------|--------------------------------------------------|
| `design-to-build` | gatekeeper-design | gatekeeper-admiral | yes |
| `redesign-review` | gatekeeper-design | gatekeeper-admiral | yes |
| `build-to-review` | gatekeeper-build | gatekeeper-admiral | yes |
| `review-to-delivery` | gatekeeper-code | gatekeeper-admiral | yes |
| `security-review` | none | gatekeeper-admiral | no |
| `investigation-review` | none | gatekeeper-admiral | no |
| `qa-review` | none | gatekeeper-admiral | no |
| `taste-review` | none | gatekeeper-admiral | no |
| `skill-maker-to-delivery` | none | gatekeeper-admiral | no |
| `deploy-readiness` | none | gatekeeper-admiral | no |

The two columns agree: a boundary has a phase gatekeeper exactly when its
pipeline carries a `phase-gate` stage, and the gatekeeper named is that stage's
declared `owner`. Both columns are mechanically derivable and mechanically
unverified — see *Mirror gaps* under [Enforcement](#enforcement). For the six without one, the GATE row's
"the boundary's gatekeeper" resolves to `gatekeeper-admiral`, and there is no
in-pipeline rehearsal before the cross-stage check. The submitter is the only
owner between the work and that single gate, so its self-check under the
`revise_policy` in `gates.yaml` is the only thing standing in for a phase
gatekeeper.

## One-writer rule

Each active artifact has exactly one writer identified by owner, path, and
revision. Readers may comment, validate, or return findings, but they do not
edit the artifact. Transfer ownership only through a new handoff with a new
revision, and keep the artifact hash unchanged until the new writer records a
change.

`admiral` writes lifecycle routing and cross-layer handoffs; `session-memory`
writes the run record. A phase owner writes only its phase artifact. A
gatekeeper never repairs the submission. `land-and-deploy` never changes an
approved package without a new revision. The selected `guard` or `freeze` owner
never widens a path boundary while applying a check.

## Enforcement

Exactly two passages of this file are opened by a comparator: the `## Specialists`
roster and the `| RELEASE ` row, both by `DeclaredCoverageTests`. Everything else
here is a hand-maintained mirror of a machine manifest.

That distinction is the point of this section, and the reason each row below
carries two columns rather than one. Most rows name a guarantee that is real but
whose *subject is the manifest*, not the sentence here mirroring it: the check
would still pass with this file's corresponding cell rewritten to nonsense. The
right column states what the same comparator lets through, so a reader can tell a
verified row from a plausible one.

| Statement in this file | What is asserted, and by what | What that check does not cover |
|------------------------|-------------------------------|--------------------------------|
| A layer owner is a real team member | `../scripts/validate_manifests.py` (`check_pipeline_mirrors`) emits `pipelines.yaml: {name} owner is not a team member`, and the per-stage form for every stage owner; `../validation/test_pipeline_contracts.py` (`test_every_pipeline_owner_is_a_team_member`, `test_every_stage_owner_is_a_team_member`) asserts the same two facts. | Both read `../pipelines.yaml`. The Owner column of the Layer matrix above is never opened, so an owner invented *here* is caught by nothing. See the mirror gaps below. |
| Each artifact has exactly one writer | `validate_manifests.py` (`check_ownership`) emits `ownership.yaml: {id} must have exactly {owner!r} as writer; found {writers}`, and rejects an artifact whose owner is not a declared owner. | Reads `../ownership.yaml`. The three role owners — `gatekeeper`, `safety-guardrails`, `phase-lead` — are exempt from the exactly-one rule: a role artifact needs only *some* declared writer, so two writers on one pass. |
| A skill does not claim an artifact it may not write | `../validation/test_catalog_contracts.py` (`OwnershipProseTests`) matches write verbs against the `does_not_write` ids in `ownership.yaml` across SKILL.md prose. | Best-effort text matching, not a proof. A disclaiming clause anywhere in the sentence (`never`, `rather than`, `belongs to`, …) exonerates it, and single-stem ids — `plan`, `tests`, `findings`, `architecture` — are excluded outright as ordinary English. |
| A stage that produces an artifact is run by that artifact's owner | `test_pipeline_contracts.py` (`StageArtifactOwnershipTests.test_every_artifact_bearing_stage_is_owned_by_the_artifact_owner`) compares every artifact-bearing stage in `pipelines.yaml` against the artifact's owner in `ownership.yaml`. | Nothing material: across the two manifests it reads, this one is exact. It does not read this file. |
| A gatekeeper never repairs the submission | `test_catalog_contracts.py` (`ToolSurfaceTests.test_gatekeepers_and_single_writers_do_not_grant_edit`) asserts that no gatekeeper and no declared single-writer lists `Edit` in `allowed-tools`. | Only the `Edit` grant. Gatekeepers legitimately hold `Write` and `Bash` — `../build/gatekeeper-build` grants both — so a gatekeeper *can* write. The no-repair rule is policy backed by the single `gate-verdict` path class in [`../save-ownership.yaml`](../save-ownership.yaml), not by the tool surface. |
| The RELEASE owner is `ship` | `DeclaredCoverageTests.test_release_layer_owner_matches_the_pipeline_and_the_gate` asserts `pipelines.yaml` `release.owner` equals the `gates.yaml` `deploy-readiness` submitter, then that this file's `| RELEASE ` row contains that name. `validate_manifests.py` independently requires exactly one pipeline per gate boundary. | The name must *be* one of the row's cells, not merely appear inside one: emptying the Owner cell fails the assertion even though `ship` still occurs in the notes cell. What is not covered is *which* cell — any cell equal to `ship` satisfies it, so the Owner column itself is not identified. |
| The specialist roster matches the team manifest | `DeclaredCoverageTests.test_responsibility_matrix_specialists_match_the_manifest` asserts that every `specialists` entry in `../team-manifest.yaml` appears in the `## Specialists` block, and that the count stated in prose matches the manifest's length. | One direction only: a name listed here that the manifest does not declare passes. The "same order" claim in that section is not compared — it holds today by hand, not by test. |
| `session-memory` writes the run record through `save_run.py` only | `../harness/hooks/pre_tool_use.py` denies direct edit-tool writes to the core run files; `../validation/test_save_contracts.py` (`test_direct_edit_of_core_files_is_denied_by_hook`) executes the hook against `_state.md`, `_latest.md`, and a `_history/*.state.json`, requiring `save_run.py` in each denial. | Phase reports under the same run are deliberately not denied — the same test asserts that a write to `design/reports/report_plan.md` produces no denial. The rule covers the run record, not the run directory. |
| The guard record has a single sanctioned writer | `test_catalog_contracts.py` (`GuardWriterTests`) requires the `harness-guards` class to name `guard_state.py`, requires that file to exist, and requires `pre_tool_use.py` to contain both `guard-state.json` and `guard_state.py`. | The hook is matched by substring, never executed. That the mention is a working denial is untested — unlike the run-record row above, which runs the hook. |

### Mirror gaps — checkable, and currently unchecked

The two tables below are not judgement. Every cell in them is derivable from a
machine manifest, so a comparator would be short, and until one is written a
drifted cell is silent. Naming them here is the honest alternative to calling
them judgement:

- **The Gate coverage table.** All three columns restate [`../gates.yaml`](../gates.yaml) and [`../pipelines.yaml`](../pipelines.yaml): a boundary has a phase gatekeeper exactly when its pipeline carries a `phase-gate` stage, and the gatekeeper named is that stage's `owner`. All ten rows were verified against both manifests by hand on 2026-09-16 and agreed. A test reading the table and diffing it against the two manifests would make the verification durable.
- **The Layer matrix Owner column.** Ten of the fourteen owners are the `owner` of the same-named pipeline in `../pipelines.yaml` — TASTE, DESIGN, REDESIGN, BUILD, REVIEW, SECURITY, INVESTIGATION, QA, SKILL CREATION, RELEASE. The remaining four come from [`../team-manifest.yaml`](../team-manifest.yaml): INTAKE from `front_door`, MEMORY from `session_memory`, SAFETY from the `safety` list, GATE from `phase_gatekeepers` plus `cross_stage_gatekeeper`. Only the `RELEASE` row is compared today, and only loosely.

### Judgement, with no manifest to compare against

Every Trigger cell, every Inputs and every Outputs cell, the "One writer" column
of the Layer matrix, the prose of the one-writer rule, and the Failure paths.
These state intent that no manifest records; they are read, not diffed. Weigh
them as authored assertions, and when one disagrees with a manifest, apply the
rule at the top of this file: the manifest is authoritative and the row is the
defect.

## Failure paths

- Two layers claim the same artifact. `ownership.yaml` decides; the layer whose
  claim it does not support stops writing and returns findings instead. If
  `ownership.yaml` names neither, the artifact is undeclared: escalate rather
  than letting the first writer take it.
- A row here and a manifest disagree. The manifest wins. Correct the row, and
  never edit a manifest to match this file.
- A layer's owner is unavailable, unroutable, or not a member of the roster.
  The layer cannot start. Enter `BLOCKED` under
  [workflow-protocol](workflow-protocol.md) with the missing owner named.
- A boundary has no phase gatekeeper and `gatekeeper-admiral` is unavailable.
  The boundary cannot be closed by the submitter. No self-check substitutes for
  a verdict; the run enters `ESCALATE`.
- An artifact needs a new writer mid-run. Transfer only through a new handoff at
  a new revision, per [handoff-templates](handoff-templates.md). A silent
  transfer invalidates every verdict that depended on the prior writer.
- A layer is required that no row covers. The work is unassigned: escalate to
  `admiral` for a routing decision and record the gap, rather than attaching it
  to the nearest-looking layer.
