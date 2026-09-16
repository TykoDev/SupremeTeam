# Gate Evidence Reference — `build-to-review`

Build-management is the `build-to-review` submitter (`../../../gates.yaml`,
`boundaries`), so it assembles all six required keys into `build/manifest.json`
and authors two of them itself (`evidence_owners`). A key it owns is never
delegated to a specialist and never inferred from another key.

Read this file before assembling the manifest or answering a REVISE. `../SKILL.md`
states only the three decisions that change what build-management does; the
columns below state what each key must contain and what may stand in for it.

## Contents

1. The six keys
2. Why `runtime` is the one that breaks builds
3. Fallbacks that exist, and the ones that do not

## The Six Keys

| Key | Owner | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- | --- |
| `approved_design_revision` | build-management | The non-empty revision identifier of the approved design package this build implements, read from the `design-to-build` verdict rather than restated from memory. It is the upstream half of the `build-package` evidence `../../../ownership.yaml` requires: approved design revision, changed artifact set with hashes, and test and runtime evidence paths | No. `artifact_evidence` at this boundary lists only `tests` and `runtime` | `revision_ref`: a non-empty approved upstream revision identifier | None. `fallback_values` carries no entry for this key, so it is not waivable here and a build without an approved upstream revision cannot reach the gate |
| `implementation` | `build/bob-the-builder` | The changed artifact set with hashes and the diff summary for the submitted revision | No | None | None |
| `tests` | `build/test-builder` | The executed test-runner log as a hashed file under `build/evidence/`, with a result status. A bare count, or a claim that the suite passed, is not evidence | Yes | `probe` | None |
| `runtime` | `build/health-check` | The executed startup and entry-point smoke log as a hashed file under `build/evidence/`, with a result status | Yes | `probe` | None |
| `traceability` | build-management | The `build-traceability` artifact `../../../ownership.yaml` assigns to build-management: a design-decision-to-changed-artifact mapping with proven or unproven status stated per row, so a reviewer can walk every approved decision to the code that carries it | No | None. `evidence_types` assigns this key no shape, so a plain statement satisfies the mechanical check and every unproven row states why it is unproven | None. Every submission carries the mapping |
| `security_evidence` | `build/security-builder` | The graded finding set for the hardening pass, with a status and an owner on every deferred Major | No | `findings` | `no trust-boundary change - security-builder not engaged` |

## Why `runtime` Is The One That Breaks Builds

`../../../pipelines.yaml` attaches no condition to the `runtime-health` stage, so
`build/health-check` runs on every build, and `runtime` accepts no fallback. Two
substitutions are attempted and both fail the gate:

- **The test suite stands in for the smoke log.** It cannot: `tests` and `runtime` are separate keys with separate owners, and a suite that passes in a test harness proves nothing about the shipped entry point starting.
- **A library with no startable entry point omits the key.** It cannot either, and the sanctioned response is in `../SKILL.md` Failure Modes: the probe is run against the real consumption path the package declares, and its executed log is the `runtime` artifact.

## Fallbacks That Exist, And The Ones That Do Not

One key at this boundary is waivable: `security_evidence`, and only when no trust
boundary moved. At manifest schema 2 the waiver is an applicability record
naming reason, scope, and decided_by, never a bare string.

The other five accept nothing but their evidence. A gap in `implementation`,
`tests`, or `security_evidence` routes to the specialist named above through the
REVISE packet; a gap in `approved_design_revision` or `traceability` is
build-management's own to close, because it authored both.
