# Universal Frameworks

## Contents

- Responsibility
- Governing contract index
- Cross-cutting frameworks
- What this file enforces
- Pointer failure paths
- Unbacked pointer of record: performance-doctrine
- Use

## Responsibility

This file is the index of the shared contract layer. It states which document
governs which concern, and whether that document's rules are mechanically
checked or judgement-only. It carries no invariant of its own: every rule named
here lives in the target, and where this index and its target disagree, the
target is authoritative and the row here is the defect.

"Machine-checked" means a script or test in this repository fails when the rule
is broken, and the row names it. "Judgement" means a reader applies the rule and
nothing detects a violation. A row may be partly backed; the row says which part.

## Governing contract index

| Concern | Governing document | Backing | Comparator |
|---------|--------------------|---------|------------|
| Lifecycle states, transitions, rewind, resume | [workflow-protocol](workflow-protocol.md) | partial | `../harness/gatekeeper/test_gate_manifests.py` (`GateSpecContractTests.test_documented_boundary_table_matches_gate_spec`) compares the boundary-name set of its gate table against [gates.yaml](../gates.yaml). States, edges, revision lineage, rewind, and resume are judgement. |
| Gate boundaries, required evidence, typed records | [gates.yaml](../gates.yaml) | machine-checked | [`check.py`](../harness/gatekeeper/check.py) judges a submission against the boundary; `test_gate_manifests.py`, `test_gate_run_layout.py`, and `test_gate_revise.py` pin the spec shape and the documented mirrors. |
| What can support a claim | [evidence-standards](evidence-standards.md) | partial | `check.py` enforces artifact backing, artifact hashes, source-input binding, waiver shape, and revision lineage. Specificity, trust, calibration, and retention are judgement. |
| One writer per artifact | [ownership.yaml](../ownership.yaml) | machine-checked | [`validate_manifests.py`](../scripts/validate_manifests.py) (`check_ownership`), and `../validation/test_catalog_contracts.py` (`OwnershipProseTests`) for prose that contradicts `does_not_write`. |
| One writer per generated path class | [save-ownership.yaml](../save-ownership.yaml) | partial | `../validation/test_save_contracts.py` (`OwnershipAgreementTests`, `GeneratedRootPolicyTests`) and `test_catalog_contracts.py` (`GuardWriterTests`, `ToolSurfaceTests`). Enforcement at write time exists only for the classes the pre-tool hook names. |
| Where generated output lands | [save-protocol](../save-protocol.md) with [`output_paths.py`](../scripts/output_paths.py) | partial | `output_paths.resolve` refuses traversal and unknown kinds; `GeneratedRootPolicyTests` pins every project kind under a declared generated root; the pre-tool hook denies direct writes to the core run files. The target's own `## Enforcement` section labels several §1 clauses judgement — the `_latest.md` fallback rule, the `verdict_{boundary}.cross-stage.json` naming convention, and which of the four governed subdirectories a file belongs in — so `machine-checked` would overstate the concern as a whole. Per *Pointer failure paths*, the target wins. |
| Pipeline stages, stage owners, closing boundary | [pipelines.yaml](../pipelines.yaml) | machine-checked | `validate_manifests.py` (`check_pipeline_mirrors`) and `../validation/test_pipeline_contracts.py`. |
| Roster and skill count | [team-manifest.yaml](../team-manifest.yaml) | machine-checked | `validate_manifests.py`: `check_team` for the role keys, list keys, state root, and verdict set; `check_pipeline_mirrors` for `skill_count` against the SKILL.md files on disk. |
| Preamble tiers and execution clauses | [execution-contract](../execution-contract.md) | machine-checked | `test_catalog_contracts.py` (`ExecutionContractTests`) requires all six clauses verbatim in every bound orchestrator and gatekeeper. |
| Delegation record fields | [handoff-templates](handoff-templates.md) | partial | `test_catalog_contracts.py` (`SaveContextParityTests`) compares the Save Context field set against the canonical block, but only for a copy that carries the `Run ID` anchor line: 91 files under `skills/` contain the words "Save Context" and the comparator parses 10 of them — the canonical copy and 9 others — skipping the other 81 as prose mentions. Those three counts are a hand count re-run on 2026-09-16 with the comparator's own parser; nothing keeps them current, so treat a mismatch as this row being stale rather than as a defect in the test. Request fields, response fields, and the Taste example are judgement. |
| Final delivery record | [delivery-template](delivery-template.md) | judgement | No comparator opens `delivery-template.md` — verified by searching every `test_*.py` under `skills/` for the filename as a quoted string, the same test the catalog's own `ClaimedEnforcementTests` uses to catch a document denying a comparator it has. |
| Layer triggers, owners, and one-writer prose | [responsibility-matrix](responsibility-matrix.md) | partial | `test_catalog_contracts.py` `DeclaredCoverageTests` opens exactly two passages of it — the `## Specialists` roster against `team-manifest.yaml`, and the `\| RELEASE ` row against `pipelines.yaml` and the `gates.yaml` submitter, the latter satisfied when one cell of that row *is* the owner's name — a cell that merely contains it does not count, though which cell it is goes unchecked. Triggers, Inputs/Outputs, and the one-writer prose are judgement. Its Gate coverage table and Layer matrix Owner column are neither: the target's `## Enforcement` names them as *mirror gaps* — every cell derivable from `gates.yaml`, `pipelines.yaml`, or `team-manifest.yaml`, and no comparator written yet. |
| Runtime floor, launchers, commands | [runtime-manifest.yaml](../runtime-manifest.yaml) | machine-checked | [`check_runtime.py`](../scripts/check_runtime.py) compares the live interpreter against the declared minimum. `validate_manifests.py` (`check_runtime`) covers all three parts of this concern, not only the floor: `major.minor` shape and a 3.9 lower bound, `stdlib_only_for_hooks_and_gates`, an on-disk fallback path for every optional dependency, and the presence of every entry in `REQUIRED_LAUNCHERS` and `REQUIRED_COMMANDS`. That a launcher works is not checked — only that it is declared. |
| Package contents and delivery residue | [package-manifest.yaml](../package-manifest.yaml) | partial | [`package_check.py`](../scripts/package_check.py) enumerates the selected set and rejects residue classes; `validate_manifests.py` (`check_package`) checks required excludes and three delivery-contract booleans. |
| Intake grilling | [grill-me-doctrine](../grill-me-doctrine.md) | partial | The grilling log is a hashed artifact behind the `decisions` gate key; `check.py` enforces the artifact and its hash, never the quality of the grilling. |
| Presentation and interaction preferences | [taste-doctrine](../taste-doctrine.md) | machine-checked at the boundary, judgement in the doctrine | The `taste-review` boundary requires twelve keys, judged by `check.py`. Six are artifact-backed (`preference_diff`, `confirmation`, `conflict_analysis`, `persistence_result`, `effective_profile`, `taste_review_record`) and six carry a typed record shape (the same list with `taste_review_record` replaced by `consumer_handoff`) — two sets of six that overlap in five, not one set of six. Whether a recorded preference reflects what the user actually wants is judgement. |
| Measured optimization | [performance-doctrine](../performance-doctrine.md) | judgement | None. See "Unbacked pointer of record" below. |

## Cross-cutting frameworks

These are the cross-cutting invariants for delivery work. They point to the
specialist references that define the detailed practice instead of duplicating
it here. The `Backing` column states what fails when the invariant is broken.

| Framework | Minimum invariant | Backing | Specialized reference |
|-----------|-------------------|---------|-----------------------|
| Context-first build | Read the repository, neighboring contracts, constraints, and current evidence before choosing an implementation. | judgement | [bob-the-builder](../build/bob-the-builder/SKILL.md) and [researcher](../design/researcher/SKILL.md) |
| Grilled intake | Resolve every load-bearing branch, record rejected options and deferrals with reopen triggers, and hash the log as the decisions artifact. | partial: the hashed artifact is checked, the reasoning is not | [grill-me-doctrine](../grill-me-doctrine.md) |
| Systematic debugging | Reproduce the failure, reduce it to one variable, identify the mechanism, then fix the class and rerun the failing proof. | partial: `investigation-review` requires an artifact-backed `reproduction` and `evidence_chain` | [investigate](../investigate/SKILL.md) and [debugger](../build/debugger/SKILL.md) |
| Stack discipline | Lock the runtime, framework, and interface versions at design time against the registry; a new dependency is a recorded decision, not a side effect. | partial: `stack_lock` is a required typed record at `design-to-build` | [tech-stacks/registry.yaml](../tech-stacks/registry.yaml) and `scripts/check_runtime.py --detect-project` |
| Design system | One component template, one UI/UX handoff, six responsive tiers, accessibility as correctness. | judgement | [design-doctrine](../design-doctrine.md) and [architect](../design/architect/SKILL.md) |
| Redesign parity | Map before changing anything: a stable-id inventory of the current design is the parity contract, four differentiated static mocks are compared on evidence, one is selected, and only then is a living prototype built for the chosen direction. | partial: `redesign-review` requires `mock_set`, `mock_parity`, `selection`, `selected_variant`, and `parity_evidence`; both parity records are produced with [`check_parity.py`](../scripts/check_parity.py) (`--level mock` for the drafts, `--level full` for the selected variant), and `check.py` requires the built variant's id to equal `selection.chosen` | [redesign](../design/redesign/SKILL.md) and [design-mapper](../design/design-mapper/SKILL.md) |
| Taste | Apply user-authored or explicitly confirmed presentation and interaction preferences with scoped provenance and deterministic project-over-global resolution; never override mandatory requirements. | machine-checked at `taste-review` | [taste-doctrine](../taste-doctrine.md) |
| Deployment readiness | Verify configuration, artifacts, permissions, target assumptions, rollback, and runtime evidence before an external release. | partial: `deploy-readiness` requires the evidence keys; the deployment itself is observed by no comparator | [ship](../ship/SKILL.md) and [health-check](../build/health-check/SKILL.md) |
| Adversarial review | Search for failure paths, regressions, missing evidence, and interface risk; grade observed findings separately from inference. | judgement | [code-chief](../review/code-chief/SKILL.md) and [bug-review](../review/bug-review/SKILL.md) |
| Security denial-path tests | Prove that unauthorized, malformed, replayed, expired, and over-broad requests are denied at the trust boundary. | partial: `security-review` requires artifact-backed deny-path evidence; probe adequacy is judgement | [mr-robot](../review/mr-robot/SKILL.md) and [security-review](../review/security-review/SKILL.md) |
| Measured optimization | Baseline, bound, one mechanism at a time, and a preserved threshold. | judgement only: no gate key, no typed record, no script | [performance-doctrine](../performance-doctrine.md) and [benchmark](../benchmark/SKILL.md) |
| Evidence-first reporting | Put claims, gaps, proof, hashes, scope, and revision beside the result; never turn an unavailable check into approval. | partial: hashes, artifact backing, and source binding are checked by `check.py`; calibration is judgement | [evidence-standards](evidence-standards.md) and [gatekeeper-admiral](../gatekeeper-admiral/SKILL.md) |

## What this file enforces

Nothing. No script parses this index and no test names `universal-frameworks.md`,
so a stale row stays invisible until a reader follows it. That is a claim with a
method: search every `test_*.py` under `skills/` for the filename as a quoted
string — a mention in a comment is not a comparator. Re-run it before trusting
this paragraph, because the catalog's `ClaimedEnforcementTests` fails a document
that denies a comparator it actually has, and the failure mode here is the
reverse — a comparator added later leaving this line quietly false.

The rows above are claims about siblings, and the authority for each claim is the
sibling. Every row was re-walked against its named comparator on 2026-09-16.

Two rules are commonly attributed to this file. Neither originates here, and
each holds only where its canonical contract is enforced:

- One writer per artifact is enforced in [ownership.yaml](../ownership.yaml) by
  `validate_manifests.py`, which rejects an artifact whose declared owner is not
  its sole declared writer, and by `test_catalog_contracts.py`, which rejects
  prose claiming authorship of an artifact listed under `does_not_write`. A
  specialist reference cannot weaken it, because neither comparator reads the
  specialist reference.
- Evidence sufficiency is enforced at the gate by
  [`check.py`](../harness/gatekeeper/check.py) for the keys
  [gates.yaml](../gates.yaml) declares. A specialist reference cannot weaken
  those keys, because the boundary contract is read from `gates.yaml` rather
  than from the reference.

A specialist reference may add requirements for its domain. It may not remove a
required gate key or reassign a declared writer, and an attempt to do either
fails at the comparators named above rather than here. Everything a specialist
reference adds beyond those keys is judgement and is checked by nothing.

## Pointer failure paths

- A target is missing or unreadable. The concern is ungoverned. Record the
  broken pointer, treat dependent work as blocked on a contract, and escalate.
  The one-line summary in a row is an index entry, never a substitute for the
  contract it points at.
- A target contradicts its row. The target wins. The row is the defect: correct
  the row, and never edit the target to match the index.
- Two rows point at documents that disagree. Resolve against the governing
  document named for that concern in the Governing contract index. When both are
  governing, the conflict is a contract defect that escalates to the owner of
  the more specific document.
- A row names a comparator that does not exist or no longer runs. The row is
  false, and the concern is judgement until the comparator is restored. An
  unavailable check is never approval.
- A concern has no row here. It is ungoverned by this layer: routing belongs to
  [responsibility-matrix](responsibility-matrix.md) and the write boundary to
  [ownership.yaml](../ownership.yaml).

## Unbacked pointer of record: performance-doctrine

[`../performance-doctrine.md`](../performance-doctrine.md) is reachable from
this index and from the repository documentation, and from no SKILL.md and no
skill reference document in the catalog.

Its scope is claim-triggered, not skill-bound. The file explicitly retires an
earlier revision that declared itself binding on `benchmark`, `frontier`,
`health-check`, and `quality-review` — none of the four names it, so the
assertion bound nothing — and replaces it with a rule keyed to the statement
rather than the code: the doctrine applies whenever a run states that something
is faster, lighter, or cheaper than it was, or that a change will not make it
slower, whatever skill is running. Touching a hot path without making such a
claim engages nothing. Ownership follows the same trigger: the skill that states
the improvement owns the measurement, which inside a delivery run is the phase
lead who accepts the claim into the package (`build-management` for a build-phase
claim, `code-chief` for a review-phase one), and delegating the measurement to
`benchmark` or `frontier` does not transfer the obligation.

The file also records its own reachability as a gap rather than papering over
it: no skill points at it, so in practice it is read by someone who already
knows it exists, and closing that gap means adding pointers from the skills that
make performance claims.

Nothing in it is machine-checked, and it says so: no boundary in
[gates.yaml](../gates.yaml) requires a performance evidence key, no typed
evidence record carries a latency, throughput, or memory field, and no script
checks its steps. The Measured optimization row is therefore a pointer to
guidance a reviewer applies by hand. An approved package proves nothing about
performance, and a performance claim carries only the trust level its own
evidence supports under [evidence-standards](evidence-standards.md).

## Use

Apply the smallest relevant set, record which framework was used, and link its
evidence in the delivery or review record. Where a row reads `judgement`, record
that fact beside the claim rather than implying a check ran.
