# Example Invocations

Each example shows the stage path build-management takes, the `build-to-review`
evidence the run produces, and the one decision that would otherwise be got
wrong. Every example assumes an active Admiral handoff; a cold invocation hands
off to `admiral` first.

## Contents

1. Service build with a trust boundary
2. Late fix after tests have passed
3. Library build with no startable entry point
4. Unknown failure mechanism mid-build
5. Vendored surface in the diff

## Example 1 — Service build with a trust boundary

**User request:** implement this design (a tenant onboarding workflow with API, worker, and admin console changes)

**Output:**
- Stage path: `build/bob-the-builder` (implementation) → `build/test-builder` (test surface) → `build/security-builder` (security checkpoint, because tenant isolation moves a trust boundary) → `build/health-check` (runtime health, unconditional) → `build/cross-check-build-confirm` (completeness) → `build/gatekeeper-build` (phase gate).
- Evidence assembled: `approved_design_revision` read from the `design-to-build` verdict, `implementation` as the changed artifact set with hashes, `tests` as the hashed runner log under `build/evidence/`, `runtime` as the hashed startup and entry-point smoke log, `security_evidence` as the graded findings record, and `traceability` walking every approved decision to the artifact that carries it.
- Decision that matters: `runtime` is collected even though the suite is green, because `tests` and `runtime` are separate keys with separate owners and neither substitutes for the other.
- Before submitting: `python skills/harness/gatekeeper/check.py --boundary build-to-review --package build/manifest.json`, no `--verdict-out`; every mechanical failure is fixed first.

## Example 2 — Late fix after tests have passed

**User request:** start the build pipeline (continuation: hardening found an unsafe dependency upgrade after the suite was green)

**Output:**
- Reopened phases: implementation reruns for the corrected dependency, then the test surface and runtime health rerun on the new revision. The security checkpoint re-records its findings against that revision.
- Why the rerun is not optional: the passing `tests` and `runtime` logs describe the pre-fix revision. Carrying them forward would submit a package whose evidence reviews code that no longer exists, which is the stale-evidence failure the gate is built to catch.
- Boundary note: the package does not advance to `build/gatekeeper-build` until every key names one revision. `approved_design_revision` is unchanged, because the design did not move.
- Escalation test applied: the dependency change did not alter the approved design or the release contract, so it stayed inside the build phase rather than rewinding to design.

## Example 3 — Library build with no startable entry point

**User request:** build this project (a published SDK package, nothing to boot)

**Output:**
- Problem: `build/health-check` has no server or CLI to start, and `runtime` accepts no fallback at `build-to-review`.
- Resolution: the smoke target becomes the real consumption path the package declares — install or import the built artifact from a clean environment, resolve its declared entry points, and exercise the documented public surface once. That executed log is hashed as `runtime`.
- What is not done: the test-runner log is not reused as `runtime`, and the key is not omitted. Either would fail the gate mechanically, and a claimed pass without an executed log would be fabricated evidence.
- Host limit: if even the clean-environment import cannot run here, nothing is submitted; the missing capability is escalated to Admiral by name.

## Example 4 — Unknown failure mechanism mid-build

**User request:** turn the specification into code (continuation: an intermittent worker crash appears during implementation)

**Output:**
- Routing: the mechanism is unknown, so the `investigation` stage goes to `investigate`, not `build/debugger`. A reproduced failure with a known mechanism would have gone the other way.
- What comes back: an investigation package gated at `investigation-review`, carrying an executed reproduction, an observed evidence chain, the surviving mechanism, and one bounded fix path with its owning phase.
- If the path is bounded and owned by build: implement it, then rerun the affected phases so `tests` and `runtime` describe the fixed revision.
- If no bounded path comes back: the build phase stops. The open mechanism and residual uncertainty are recorded in the package and the decision goes to Admiral; a fix applied without a mechanism produces exactly the unexplained evidence the gate rejects.

## Example 5 — Vendored surface in the diff

**User request:** execute the implementation plan (the change regenerates a client SDK and bumps a lockfile)

**Output:**
- Detection: the generated SDK directory and the lockfile match the mechanical non-first-party rule — a generated root, a generator banner, and a `*.lock` name — so they are classified before any completeness claim is made.
- Treatment: each path is listed with its upstream source and version, the owner who accepted it, and its scan note. None of it counts toward first-party coverage, and none of it is hand-edited; a needed change goes into the generator and is regenerated.
- Package contents: production diff summary, test log, runtime smoke log, security disposition, completeness confirmation, the non-first-party inventory, and the traceability mapping.
- Next move: submit the revision-aligned package to `build/gatekeeper-build` for review-readiness validation, then hand it to admiral for the `gatekeeper-admiral` pass.
