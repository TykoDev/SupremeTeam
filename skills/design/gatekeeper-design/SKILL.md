---
name: gatekeeper-design
description: >-
  Design-phase gatekeeper for `design-to-build` and `redesign-review`, invoked by
  `design/commander` or `design/redesign`; reached cold, route to `admiral`.
  Use when either submits a package, or the user asks to validate the design
  deliverable or redesign package, review design phase output, check design
  readiness, or challenge the packet — even when they only ask "is the design
  done?". Defers the other gates to `build/gatekeeper-build`,
  `review/gatekeeper-code`, `gatekeeper-admiral`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Gatekeeper Design

## Purpose

Hold two boundaries that share a phase and almost nothing else.

`design-to-build` asks whether a plan is specific enough to build from.
`redesign-review` asks whether four real alternatives were explored, compared
honestly against an existing surface, and one was chosen for a stated reason.
The evidence sets overlap on a single key, `taste_snapshot`, so the first move at
this gate is always classification — judging a redesign package against the
design-to-build list checks almost nothing that package actually owes.

What this gate is protecting downstream is narrow and concrete: build reads the
package as a specification, not as a suggestion, and cannot tell a decision that
was made from one that was implied.

## Entry Routing

This skill is the design-phase gatekeeper of the **Admiral** delivery pipeline and is reached through its sub-orchestrators `design/commander` and `design/redesign`, never as a front door (`../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly submits a `design-to-build` or `redesign-review` package for a verdict.

- **Handoff present** → proceed; a run is active and the declared boundary is being validated inside it.
- **No handoff (cold/direct invocation)** → do not run standalone. Route to `admiral` first so a real design or redesign package, evidence bundle, and approval lineage exist to validate, then accept the submission back. This is the loop guard: a routed call arrives with the handoff signal and proceeds immediately, so the check never re-bootstraps a run that is already open.

## Use This Skill When

This skill holds two boundaries — **design→build** and **redesign-review** — and in both it decides whether design evidence can advance:

- "validate the design deliverable" / "check design readiness" — confirm requirements, plan, and architecture are present and coherent
- "review design phase output" — verify the package is complete enough for build consumption
- "challenge this design packet" — pressure the evidence rather than the intent behind it
- "validate the redesign package" — at `redesign-review`, check the inventory, taste grilling, four directions, four variants, and their parity, rendered, and accessibility evidence
- "is the design done?" — the bare question, before any package has been named

Route elsewhere for a different boundary: the build→review gate (`build/gatekeeper-build`), the review→delivery gate (`review/gatekeeper-code`), or the cross-stage delivery gate (`gatekeeper-admiral`).

## Inputs

- Design packet for the current phase exit, including research, plan, architecture, API/UI contracts, stack locks, immutable `taste_snapshot`, and implementation spec as applicable.
- Pipeline context from `design/commander` with scope, approval lineage, revision delta, skip records, and deterministic pre-check output.
- Prior design-gate verdict when the same package is being resubmitted for idempotency or drift review.
- YAGNI deferrals, migration/deprecation commitments, proof-first test expectations, and threat-model seeds when those surfaces are in scope.

## Outputs

- Design-exit verdict with `APPROVED`, `REVISE`, or `ESCALATE`, tied to the submitted design revision and phase boundary.
- Design findings naming missing or inconsistent research, plan, architecture, endpoint, UI, stack-lock, or implementation-spec evidence.
- Findings for premature/speculative scope, missing migration proof, absent test strategy, or undocumented trust boundaries when applicable.
- Required remediation instructions for `design/commander`, including which specialist packet must change before build can consume the design.

## Boundary Contract

This gate owns two boundaries. `../../gates.yaml` is the source of both rows; the
table mirrors that file and is never restated from memory, because a remembered
evidence list is how a gate starts accepting keys the spec does not require.
Confirm the declared boundary first.

| Boundary | Guards | Submitter | Required evidence |
| --- | --- | --- | --- |
| `design-to-build` | DESIGN to BUILD | commander | `decisions` `architecture` `interfaces` `plan` `acceptance` `security_seed` `stack_lock` `taste_snapshot` `ui_evidence` |
| `redesign-review` | REDESIGN (design-shaped) to GATE to DESIGN with the chosen variant, or COMPLETE | redesign | `design_inventory` `taste_grilling` `taste_snapshot` `design_directions` `variant_set` `parity_evidence` `rendered_verification` `accessibility_evidence` `recommendation` `residual_risk` |

`references/boundary-evidence.md` carries what each key must be — its record
type, its artifact-backing, and the exact sanctioned waiver text. The decisions
that belong at the gate itself are these:

**At `design-to-build`**, four of the nine keys are artifact-backed and must name
a path in `artifact_hashes`: `decisions`, `architecture`, `plan`, and
`taste_snapshot`. Three accept a waiver — `stack_lock` (no new runtime or
framework), `ui_evidence` (no user-facing surface), `taste_snapshot` (no saved
Taste profile available) — each only as a typed applicability record naming
reason, scope, and decided_by. The other six accept no fallback.

**At `redesign-review`**, seven of the ten are artifact-backed:
`design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`,
`variant_set`, `parity_evidence`, and `rendered_verification`. Only
`taste_snapshot` is waivable, because `../../gates.yaml` lists
`rendered_verification` under this boundary's `no_fallback`: there it accepts
neither the sanctioned fallback string nor an applicability record, even though a
global fallback exists for it elsewhere. A redesign always has a visible surface,
so "no visible surface changed" can never be true at this boundary.

### Owner routing

Ownership decides where a `REVISE` lands. Across both boundaries a failing key
routes to its owner, not to the submitter: a missing `security_seed` is
`security-builder`'s work even though `commander` submitted the package, and a
failed `rendered_verification` is `design-qa`'s even though `redesign` submitted
it. Sending either to the submitter parks the defect with an owner who cannot fix
it. Both tables below mirror `../../gates.yaml` `evidence_owners`.

`design-to-build`:

| Evidence key | Owner |
| --- | --- |
| `decisions` | admiral |
| `architecture` | architect |
| `interfaces` | architect |
| `plan` | planner |
| `acceptance` | planner |
| `security_seed` | security-builder |
| `stack_lock` | commander |
| `taste_snapshot` | taste |
| `ui_evidence` | architect |

`redesign-review`:

| Evidence key | Owner |
| --- | --- |
| `design_inventory` | design-mapper |
| `taste_grilling` | taste |
| `taste_snapshot` | taste |
| `design_directions` | architect |
| `variant_set` | prototyper |
| `parity_evidence` | design-mapper |
| `rendered_verification` | design-qa |
| `accessibility_evidence` | frontier |
| `recommendation` | redesign |
| `residual_risk` | redesign |

## Deterministic Pre-Check (two validators)

Run both **before** applying judgment. Neither issues a verdict, and neither
substitutes for the other: a package can pass the shape check and still fail the
evidence contract.

**1. The package-shape validator** checks which files the package directory
holds. At `design-to-build`:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

At `redesign-review`, run `scripts/check_redesign.py <redesign-phase-dir>`
instead — it declares the redesign artifact manifest: inventory, taste grilling
log, directions, one `variant.md` per variant, the assembled redesign package,
and the parity probe output.

Both wrap the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which
also mechanizes single-revision lineage, skip-record completeness, the
blocked-phrase scan, idempotency drift against `--prior`, and harness-doctrine §5
structure. Both return `PASS` / `FAIL` / `UNCHECKED` findings plus a
`gate_status`, never a verdict, and never a judgment about design coherence. Both
fail loud: a blocking failure exits non-zero, an internal error exits 2.

Two `design-to-build` artifacts are **conditional** — API contracts and the
frontend/UI handoff. The script cannot know whether endpoints or a user-facing
surface are in scope, so it reports their absence as `UNCHECKED`, to be resolved
against the actual scope and the `../architect/references/api-endpoint-design.md`
and `../../design-doctrine.md` contracts.

**2. The boundary validator** checks the evidence contract against
`../../gates.yaml`:

```bash
python ../../harness/gatekeeper/check.py --boundary <design-to-build|redesign-review> \
  --package <phase>/manifest.json [--prior <prior-verdict-file>] \
  --verdict-out <phase>/verdict_<boundary>.json
```

At `redesign-review` it mechanizes the four-variant `variant_set` record, the
single aggregated parity probe record — `parity_evidence` must be one mapping
with hashed artifacts and a passing status, and a list of per-variant records
fails — and the no-fallback rule for `rendered_verification`. Judgment keeps the
differentiation of the four directions (`../../design-doctrine.md` §9) and
whether the parity record actually binds to the inventory: `inputs` is optional
on a `probe`, so the validator does not require it. See
`../../harness/gatekeeper/README.md`.

### The two key spaces collide by name

The shape keys are declared by the two scripts; the evidence keys are declared by
`../../gates.yaml`. Nine names appear in both spaces meaning different things,
and reading a `PASS` on the left as satisfaction of the right is how a package
advances with a file present and its evidence key empty.

| Name | As a shape key (script) | As an evidence key (`../../gates.yaml`) |
| --- | --- | --- |
| `plan` | `check.py`: a `*plan*.md` file exists in the package directory | required at `design-to-build`, artifact-backed — a path in `artifact_hashes` |
| `architecture` | `check.py`: an `*architect*.md` or `*adr*.md` file exists | required at `design-to-build`, artifact-backed |
| `taste_snapshot` | `check.py`: a `*taste*snapshot*` file carrying digest/source markers | required at both boundaries, artifact-backed, waivable |
| `stack_locks` / `stack_lock` | `check.py` `stack_locks`: any `*stack*.md`, `*lock*.md`, or `*tech*.md` file | spec `stack_lock`: a typed record `{slug, versions, overlay_sha256}` validated against `../../tech-stacks/registry.yaml` |
| `design_inventory` | `check_redesign.py`: a `*design-inventory*` file exists | required at `redesign-review`, artifact-backed |
| `taste_grilling` | `check_redesign.py`: a grilling log file exists | required at `redesign-review`, artifact-backed |
| `design_directions` | `check_redesign.py`: `*direction*.md` files exist | required at `redesign-review`, artifact-backed |
| `parity_evidence` | `check_redesign.py`: a `*parity*.json` file exists | a `probe` record per variant, bound by `inputs` to the inventory and prototype files |
| `rendered_verification` | `check_redesign.py`: conditional — a `*render*` or `*capture*` file, absence reported `UNCHECKED` | a `render` record with hashed captures, breakpoints, themes, and bound `inputs`; `no_fallback` at this boundary |

Six shape keys have no evidence counterpart at all — `research`, `impl_spec`,
`api_contracts`, `ui_handoff`, `variant_specs`, `redesign_package` — and nine
evidence keys have no shape counterpart: `decisions`, `interfaces`, `acceptance`,
`security_seed`, `ui_evidence`, `variant_set`, `accessibility_evidence`,
`recommendation`, `residual_risk`. Neither absence is a defect in the other
validator; it is why both run.

### The `rendered_verification` requirement discrepancy

`scripts/check_redesign.py` declares `rendered_verification` with
`requirement="conditional"`, so its absence from the redesign phase directory is
reported `UNCHECKED` rather than `FAIL`. `../../gates.yaml` lists the same key
under `redesign-review`'s `no_fallback`, where it is neither waivable nor
optional. The two are answering different questions, and the discrepancy is
recorded here rather than repaired in the script:

- The script asks whether a capture file is present, and cannot know which filenames a given redesign produced; marking it `required` would fail honest packages on a naming mismatch.
- The spec asks whether the evidence key carries a hashed `render` record, which the boundary validator can answer exactly.
- Therefore: treat the script's `UNCHECKED` on this key as **unresolved, never as a waiver**. The boundary validator is the authority, and it fails the key outright.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

Clause 6 binds directly, because this skill owns the `design-to-build` and
`redesign-review` gates. Every return carries all six fields:

- **Outcome** — the boundary judged and what the package may now do
- **Evidence** — both validator results plus the hashed artifacts actually inspected
- **Open risks** — unresolved design questions, and `residual_risk` at `redesign-review`
- **Next action** — the owner-grouped `REVISE` packet, or the handoff to build with the chosen variant
- **Revision** — the submitted package revision
- **Verdict** — `APPROVED` / `REVISE` / `ESCALATE`

A verdict returned without its evidence anchors is incomplete and is not a gate
result.

Clause 4 has a concrete local form here: `<package-dir>` is untrusted phase
context. Both scripts resolve it, require an existing directory inside the
working tree, and exit 2 without running the gate otherwise; confirm the same
before invoking and return `ESCALATE` naming the rejected path.

## Workflow

1. Classify the boundary from the submitted manifest's `boundary` and `owner` — `design-to-build` (submitter `commander`) or `redesign-review` (submitter `redesign`) — and read that row's required-evidence list from `../../gates.yaml` rather than from memory. The two sets share only `taste_snapshot`.
2. Run the package-shape validator for that boundary: `scripts/check.py` at `design-to-build`, `scripts/check_redesign.py` at `redesign-review`. Treat its `UNCHECKED` findings as unresolved questions, not as passes.
3. Run the boundary validator for that boundary. At `design-to-build`, confirm `decisions`, `architecture`, `interfaces`, `plan`, `acceptance`, `security_seed`, `stack_lock`, `taste_snapshot`, and `ui_evidence` are present and non-falsy, that `decisions`, `architecture`, `plan`, and `taste_snapshot` resolve to hashed artifacts, and that `stack_lock` validates against `../../tech-stacks/registry.yaml`. At `redesign-review`, confirm `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`, `variant_set`, `parity_evidence`, `rendered_verification`, `accessibility_evidence`, `recommendation`, and `residual_risk`, with only the last three unbacked. Accept a waiver only as a typed applicability record carrying a sanctioned reason, and never for `rendered_verification` at `redesign-review`.
4. Judge what neither validator can. At `design-to-build`: whether stakeholder goals, system structure, frontend and backend decisions, deployment assumptions, YAGNI deferrals, and unresolved questions contradict each other. At `redesign-review`: whether the four directions are genuinely differentiated (`../../design-doctrine.md` §9), whether the comparison is honest, and whether the recommendation follows from it.
5. Check that migration/deprecation, proof-first testing, frontend state/API handoff, and threat-model surfaces are present when the design scope requires them.
6. Decide the narrowest justified verdict and return only the mandatory changes the design owner must make, grouped by the owner each failing key belongs to.
7. Preserve verdict history across revisions and reject silent scope broadening disguised as normal design evolution, undocumented architecture drift, or an unearned pipeline exit.

## Required Contracts

- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **API endpoint contract schema**: When API, webhook, event-ingest, or internal service endpoints are in scope, reject packages that do not satisfy `../architect/references/api-endpoint-design.md` with endpoint inventory, per-endpoint schemas, auth/authorization, error envelope, idempotency, observability, versioning, frontend handoff, and contract tests.
- **Frontend/UI handoff schema**: When a user-facing surface is in scope, reject packages that do not satisfy `../../design-doctrine.md` with both the shadcn Component Template and UI/UX Handoff sections, including route inventory, state matrix, API/data dependency map, validation behavior, and responsive evidence.
- **Taste snapshot**: Require its canonical digest, project and global source revisions, resolved and shadowed entries, unresolved conflicts, applicability decision, and effective-preference traceability rows. Confirm both source revisions are still current immediately before approval; reject stale snapshots or unresolved conflicts that affect a design decision.
- **Harness-doctrine citation**: When the package adds or changes a cross-cutting runtime intervention, check it against `../../harness-doctrine.md` §5 and cite the violated section by number in the verdict.
- **YAGNI and proof contract**: Reject packages that force speculative future commitments without current need, or that change behavior without a build-ready proof plan covering reproduction/contract tests, migration checks, and rollback evidence as applicable.
- **Batched REVISE** (`../../gates.yaml` `revise_policy`): A `REVISE` carries every mechanical failure and every judgment finding from the pass, grouped by owner exactly as the boundary validator `../../harness/gatekeeper/check.py` reports them in `revise_packet.by_owner`; never return the first defect alone. On a resubmission run with `--prior`, re-judge only `changed_evidence` and carry the prior judgment on `unchanged_evidence`; the mechanical pass always covers the whole package. A package that fails mechanically was never eligible for submission (the submitter self-checks) and is returned without judgment.

## Verdict Model

- **APPROVED**: The package is ready to advance with its current evidence.
- **REVISE**: The package can progress after specific mandatory changes.
- **ESCALATE**: The package cannot advance without external judgment or a broader scope decision.

## Evidence Standard

- Tie every major and critical finding to a concrete file, artifact, or observable behavior.
- Reject claims of completion that are not backed by a visible deliverable.
- Preserve contradictory evidence instead of normalizing it away.

## Skip Rule

Do not skip gate evaluation; only reuse a prior verdict when the exact package revision is unchanged.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The architecture describes components, flows, or interfaces that are absent from the plan or implementation spec | Return `REVISE` and require a single coherent system view before build can rely on it. |
| The package claims API readiness but endpoints lack request/response schemas, auth/authorization, error envelope, idempotency, or contract tests | Return `REVISE` and require the API endpoint contract template before the design package can exit. |
| The package claims frontend readiness but lacks route inventory, screen-state coverage, API/data dependency mapping, form validation behavior, or breakpoint evidence | Return `REVISE` and require the UI/UX Handoff section before the design package can exit. |
| Stack locks or infrastructure assumptions conflict with regulatory, operational, or platform constraints already captured in the packet | Block the design exit until the contradiction is resolved or explicitly escalated to the user. |
| The packet names critical open questions but does not assign ownership or a downstream decision point | Mark the package incomplete and require explicit unresolved-decision handling before approval. |
| The design claims readiness for build but lacks the actual phase-exit approval record for the current revision | Reject the handoff and require the matching approval lineage instead of trusting narrative readiness claims. |
| Taste source revisions changed before the gate, or an effective entry used by the active design was revoked | Return `REVISE`, require Admiral/Taste re-resolution, and surface revocation drift for a user retain/replay decision. |
| The package removes, replaces, or deprecates behavior without consumer/usage evidence, replacement readiness, migration steps, and removal criteria | Return `REVISE` and require the planner/engineer packets to make the migration path build-ready. |
| The implementation spec changes behavior but does not identify the first failing test, contract test, or runtime verification expected from the build phase | Return `REVISE` and require a proof-first validation plan before build begins. |
| `variant_set` holds fewer than four variants, repeats a variant id, or leaves a variant's `spec`, `tokens`, `components`, or `app` unhashed | Return `REVISE` to `prototyper`. `../../gates.yaml` `evidence_type_params` fixes the required count at four; three variants is a comparison with a predetermined winner, and an unhashed variant cannot be the one that was compared. |
| `parity_evidence` is a probe record whose `inputs` are absent or do not bind by sha256 to the inventory and prototype files | Return `REVISE` to `design-mapper`. An unbound parity probe proves that something passed, not that the redesign matches the inventory it claims parity with. |
| `rendered_verification` at `redesign-review` carries the sanctioned fallback string or an applicability record, or the shape check's `UNCHECKED` on it is read as a waiver | Return `REVISE` to `design-qa` and require hashed captures across the required breakpoints and themes, bound by `inputs` to the rendered variant. The boundary lists the key under `no_fallback`, which beats the global fallback, and a conditional `UNCHECKED` from `check_redesign.py` is an unresolved question rather than permission. |

## Save Protocol

A gatekeeper writes exactly one path class — `gate-verdict`
(`../../save-ownership.yaml`, pattern `skillset-saves/runs/*/*/verdict_*.json`) —
and within that class one durable verdict record per boundary it gates. This
skill gates two boundaries, so a run that exercises both leaves two records of the
same class; a single boundary never produces two:

| Boundary | Verdict record |
| --- | --- |
| `design-to-build` | `skillset-saves/runs/{run-id}/design/verdict_design-to-build.json` |
| `redesign-review` | `skillset-saves/runs/{run-id}/redesign/verdict_redesign-review.json` |

Each record is produced by the boundary validator against `../../gates.yaml`:

```bash
python ../../harness/gatekeeper/check.py --boundary design-to-build \
  --package skillset-saves/runs/{run-id}/design/manifest.json \
  --verdict-out skillset-saves/runs/{run-id}/design/verdict_design-to-build.json

python ../../harness/gatekeeper/check.py --boundary redesign-review \
  --package skillset-saves/runs/{run-id}/redesign/manifest.json \
  --verdict-out skillset-saves/runs/{run-id}/redesign/verdict_redesign-review.json
```

It never modifies the submission, its evidence, or the run record. The boundary's
submitter — `design/commander` at `design-to-build`, `design/redesign` at
`redesign-review` — carries the semantic verdict into its next checkpoint.
`gatekeeper-admiral` later re-validates the same boundary with `--prior` pointed
at the record above and writes its own beside it as
`verdict_<boundary>.cross-stage.json`, which it never overwrites. When
persistence is inactive, return the verdict inline and preserve the run and
revision.

## References

- `scripts/check.py` for the `design-to-build` package-shape manifest, and `scripts/check_redesign.py` for the `redesign-review` one.
- `references/boundary-evidence.md` for what each evidence key must be: record type, artifact-backing, and the exact sanctioned waiver text.
- `../../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed validation sequence and verdict rules.
- `references/examples.md` for worked submissions at both boundaries.
- `../architect/references/api-endpoint-design.md` for the required API endpoint design contract.
- `../../design-doctrine.md` for the shadcn Component Template, the UI/UX Handoff requirements, and §9 direction differentiation.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `scripts/check_redesign.py`, `references/workflow.md`, `references/boundary-evidence.md`, and `references/examples.md` together. Both scripts depend on the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which they locate by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
