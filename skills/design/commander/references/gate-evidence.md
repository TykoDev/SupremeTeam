# Gate Evidence Reference — `design-to-build`

Commander is the `design-to-build` submitter (`../../../gates.yaml`,
`boundaries`), so it assembles all nine required keys into `design/manifest.json`
and authors exactly one of them — `stack_lock`. Every other key is authored by
its owner and carried into the manifest unchanged; a missing one routes to that
owner through the REVISE packet and is never filled in locally.

Read this file before assembling the manifest or answering a REVISE. `../SKILL.md`
states only the three decisions that change what Commander does; the columns
below state what each key must contain and what may stand in for it.

## Contents

1. How to read the columns
2. The nine keys
3. Fallbacks that exist, and the ones that do not
4. Where each fallback is decided

## How To Read The Columns

- **Owner** — the skill `../../../gates.yaml` `evidence_owners` assigns the key to. Commander routes a defect here, it does not author the repair.
- **Artifact-backed** — whether the key must reference a path present in the manifest's `artifact_hashes` map. `artifact_evidence` at this boundary lists four keys only: `decisions`, `architecture`, `plan`, `taste_snapshot`.
- **Typed record** — the shape `evidence_types` requires. An untyped key is satisfied mechanically by any non-falsy statement, so its quality is a judgment finding rather than a mechanical one.
- **Fallback** — the exact sanctioned value from `fallback_values`, or `none`. Only a key listed under `fallback_values` is waivable; at manifest schema 2 the waiver is an applicability record (`applicable: false`, `reason`, `scope`, `decided_by`), never a bare string.

## The Nine Keys

| Key | Owner | Must contain | Artifact-backed | Typed record | Fallback |
| --- | --- | --- | --- | --- | --- |
| `decisions` | `admiral` | The intake grilling log, referenced manifest-relative as `../intake/report_grilling.md` from the design phase directory: every load-bearing decision resolved, every branch deferred with its reopen trigger | Yes | None | None |
| `architecture` | `design/architect` | The hashed architecture report: component boundaries, data flow, and the decisions the plan is sequenced against | Yes | None | None |
| `interfaces` | `design/architect` | The API endpoint inventory and contracts for every surface the build must implement | No | None | None |
| `plan` | `design/planner` | The hashed delivery plan, sequenced against the approved architecture rather than beside it | Yes | None | None |
| `acceptance` | `design/planner` | The criteria the build will be measured against at `build-to-review` | No | None | None |
| `security_seed` | `build/security-builder` | The trust boundaries the design introduces or moves, and the control the build owes at each one | No | None | **None.** `fallback_values` carries no entry for this key, so it is not waivable here and no applicability record substitutes for it. With no trust boundary in scope, the value is the recorded determination — who decided there is no boundary movement, and on what basis — which satisfies the mechanical check as a plain statement |
| `stack_lock` | `commander` | The `tech-stacks/registry.yaml` slug, the locked versions, and the overlay sha256, validated so the slug exists, the overlay digest matches both registry and file, and the versions intersect | No | `stack_lock` | `no new runtime or framework - existing stack unchanged` |
| `taste_snapshot` | `taste` | The immutable effective-profile snapshot: canonical digest, project and global source revisions, resolved and shadowed entries, unresolved conflicts, applicability decision | Yes | None | `no saved Taste profile available` |
| `ui_evidence` | `design/architect` | The component template and UI/UX handoff `../../../design-doctrine.md` §5 requires: generated tokens, components, preview, and `design-system.md` | No | None | `no user-facing surface - design system not engaged` |

## Fallbacks That Exist, And The Ones That Do Not

Three keys at this boundary are waivable, and each waiver is a claim about the
project rather than about the run's convenience:

- `stack_lock` — waivable only when the design introduces no runtime, framework, or dependency. Detect the slug deterministically with `python skills/scripts/check_runtime.py --detect-project` before claiming this; a registry that has no slug for the detected runtime is not the same as no new runtime, and is handled in `../SKILL.md` Failure Modes.
- `taste_snapshot` — waivable only when neither Taste store holds a profile. A profile that exists but was not requested is a missing key, not an absent one.
- `ui_evidence` — waivable only when the design produces no user-facing surface. A backend-only service uses it; a design whose UI work was skipped for time does not.

Six keys accept nothing but their evidence: `decisions`, `architecture`,
`interfaces`, `plan`, `acceptance`, and `security_seed`. A gap in any of them is
a REVISE routed to the owner named above.

## Where Each Fallback Is Decided

An applicability record names its `decided_by`, so each waiver has an accountable
author rather than defaulting to the submitter:

| Fallback | Decided by | Recorded during |
| --- | --- | --- |
| `stack_lock` no-new-runtime | commander | the stack-lock stage, after `check_runtime.py --detect-project` |
| `taste_snapshot` no-profile | commander, on the resolution Admiral/Taste returns | intake, before the first specialist delegation |
| `ui_evidence` no-surface | architect, confirmed by commander against the scope statement | the interface-and-design-system stage decision |
