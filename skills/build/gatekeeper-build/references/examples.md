# Worked Build-Gate Submissions

Every example below is a **routed submission**, not a cold request.
`build/build-management` reached this gate with an active handoff — a
`### Save Context` block naming run, phase, submission id, revision, and owner —
because `../SKILL.md` Entry Routing forbids running standalone: with no
submission there is no packet, no evidence bundle, and no approved design lineage
to judge. A prompt that arrives as a bare "validate the build deliverable" with
none of that is answered by routing to `admiral`, not by returning a verdict.

Five submissions at the one boundary this gate owns.

## Contents

1. `REVISE` — a missing `runtime` and a claim where a log belongs
2. `REVISE` — an unsanctioned `security_evidence` string and an empty design revision
3. `APPROVED` — a resubmission with one sanctioned waiver
4. `ESCALATE` — a build fix that widens design scope
5. `ESCALATE` — `<package-dir>` rejected before the gate ran

## Example 1 — `REVISE` on a missing `runtime` and a claim where a log belongs

**Submission:** `build/build-management` submits the build package. Save Context:
run `r-4102`, phase `build`, submission `r-4102-b1`, revision 1, owner
`build-management`, return boundary `build-to-review`. The manifest declares
`schema_version: 2`, as every submission in this file does; the failure strings
quoted below are the schema-2 set.

**Validators:**
- `../scripts/check.py skillset-saves/runs/r-4102/build`: `NEEDS_JUDGMENT`. Implementation, test, security, and completeness deliverables all present; `build_verdict` reported `UNCHECKED` (no prior verdict exists at revision 1).
- Boundary validator `--boundary build-to-review`: exit 1, `failures` reading `["evidence not artifact-backed: tests", "missing evidence: runtime", "tests must be a typed probe record at schema 2"]`. `runtime` is absent; `tests` carries the string "unit + integration green, 412 passed, 0 failed", which names no path in `artifact_hashes`.

**Output:**
- Verdict: `REVISE`.
- Boundary: `build-to-review`, submitted by `build-management`, revision 1.
- Evidence, batched and grouped by `../../../gates.yaml` `evidence_owners`:
  - `health-check` — `runtime` is missing. The package's completeness certification says the service "builds and deploys cleanly", which is a statement about compilation; the key asks for the startup / entry-point smoke log as a hashed `probe` artifact under `build/evidence/`.
  - `test-builder` — `tests` is a claim, not a log. The shape check passed on this key because a `*test*.md` deliverable exists in the directory; the evidence key asks for the test-runner log itself, which is why both validators run. The count cannot be re-read by review.
- Note on the two spaces: the shape key `tests` matched a written report, the evidence key `tests` wants an executed log. A `PASS` on the left is not satisfaction of the right.
- Next action: the two owners fix in parallel; `build-management` resubmits once at revision 2.
- Revision: 1.

## Example 2 — `REVISE` on an unsanctioned waiver and an empty design revision

**Submission:** `build/build-management` resubmits at revision 2. Save Context:
run `r-4102`, submission `r-4102-b2`, owner `build-management`;
`--prior build/verdict_build-to-review.json`.

**Validators:**
- `../scripts/check.py`: `STRUCTURE_OK`.
- Boundary validator: exit 1, `failures` reading `["missing evidence: approved_design_revision", "security_evidence must be a findings record with an items list at schema 2"]`. `security_evidence` carries "nothing security-relevant in this change"; `approved_design_revision` is the empty string. `changed_evidence` names `tests`, `runtime`, `security_evidence`, and `approved_design_revision`.

**Output:**
- Verdict: `REVISE`.
- Boundary: `build-to-review`, submitted by `build-management`, revision 2.
- Evidence, grouped by owner:
  - `security-builder` — `security_evidence` is a bare explanatory string where a record belongs, and the validator says so in those terms: *security_evidence must be a findings record with an items list at schema 2*. The only admissible waiver is the typed applicability record naming reason, scope, and decided_by, carrying exactly "no trust-boundary change - security-builder not engaged" — and swapping in that wording as a bare string does not clear the failure, it changes it to *bare fallback string not accepted at schema 2*. If the statement is true here, the record says so in the shape the spec accepts; if it is not, the `findings` record is owed. (Had this package been submitted at schema 1, neither string would have failed at all and this finding would be judgment alone.)
  - `build-management` — `approved_design_revision` is empty. An empty value is falsy, so the validator counts it in `missing` before any waiver logic runs and the failure reads *missing evidence: approved_design_revision*. (*evidence not waivable* is a different failure: it fires only when the value is a `{applicable: false, ...}` record on a key the boundary does not allow waiving.) Without the key the build advances under a design nobody approved, which is the one thing it exists to prevent.
- Carried forward: `tests` and `runtime` now resolve to hashed probe logs at `result.status: pass`, clearing both revision-1 findings. `implementation` and `traceability` are in `unchanged_evidence` and keep their prior judgment.
- Next action: two owners, fixed in parallel; resubmit at revision 3.
- Revision: 2.

## Example 3 — `APPROVED` with one sanctioned waiver

**Submission:** `build/build-management` resubmits at revision 3. Save Context:
run `r-4102`, submission `r-4102-b3`, owner `build-management`; `--prior` from
revision 2.

**Validators:**
- `../scripts/check.py`: `STRUCTURE_OK`, blocked-phrase scan clean.
- Boundary validator: exit 0.

**Output:**
- Verdict: `APPROVED`.
- Boundary: `build-to-review`, submitted by `build-management`, revision 3.
- Evidence: `tests` names `build/evidence/pytest-r3.log` and `runtime` names `build/evidence/startup-r3.log`, both hashed in `artifact_hashes` at `result.status: pass`. `approved_design_revision` names design revision 3, which `design/verdict_design-to-build.json` approved. `security_evidence` carries the sanctioned applicability record for "no trust-boundary change - security-builder not engaged", scoped to the two changed modules and decided by `security-builder`, and the diff touches no auth, network, or serialization path — so the reason is honest, not merely well-formed.
- Judgment: `traceability` maps all seven changed modules to approved design items, including the migration script that revision 1 omitted. No generated or vendored content appears in the diff.
- Open risks: one deferred Major owned by `test-builder` with a reopen trigger on any change to the retry path, which the finding policy admits.
- Next action: review may consume the package at revision 3.
- Revision: 3. Later edits that change the build revision invalidate this verdict.

## Example 4 — `ESCALATE` on a build fix that widens design scope

**Submission:** `build/build-management` submits a package fixing a migration
failure. Save Context: run `r-4210`, phase `build`, submission `r-4210-b2`,
revision 2, owner `build-management`.

**Validators:** both pass mechanically — all six keys resolve, `tests` and
`runtime` hashed.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `build-to-review`, submitted by `build-management`, revision 2.
- Conflict: the migration fix replaces the persistence model, and `traceability` maps that change to an approved design item that describes a schema migration, not a model replacement. `approved_design_revision` names a design revision that never contemplated it.
- Evidence: the contradiction is preserved rather than normalized — the evidence set is internally clean, and that is precisely the problem: a mechanically perfect package can still carry a design change it was not authorised to make.
- Next action: obtain a design-level approval for the new persistence model, or rewind the build packet to the prior contract. Neither is a change `build-management` can make to the packet, which is why this is not a `REVISE`.
- Revision: 2.

## Example 5 — `ESCALATE` on a rejected `<package-dir>`

**Submission:** `build/build-management` submits with `package-dir` given as
`../../shared/releases/candidate-v2`, which traverses above the designated build
working area. Save Context: run `r-4210`, phase `build`, submission `r-4210-b3`,
revision 3.

**Validators:** neither ran. The path contains traversal sequences and does not
resolve inside the expected build/package working area, so the script was not
invoked; `../scripts/check.py` would itself exit 2 on the same path, before the
engine reads anything.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `build-to-review`, submitted by `build-management`, revision 3. Not judged.
- Evidence: none. Nothing about the package was checked, so no statement about its readiness is available — an unrun pre-check is not a clean one, and a gate that fails open is worse than no gate.
- Next action: `build-management` supplies a package directory path inside the designated working area, and resubmits unchanged.
- Revision: 3.
