# Example Invocations

Each example shows what Admiral decides, not what the downstream pipeline
produces. Examples 1 through 3 cover the three intake outcomes a request can
have — fast path, new run, resume — and examples 4 through 8 cover one pipeline
route each.

## Contents

1. Tier 0 fast path (no run created)
2. Full pipeline
3. Resume at build
4. Redesign route
5. Security-audit route
6. Product-QA route
7. Skill creation
8. Team creation
9. Drift constraint carried across boundaries

## Example 1 — Tier 0 fast path

**User request:** the footer copyright year is hardcoded to 2024, fix it

**Output:**
- Classification: Tier 0 under `../../routing-doctrine.md#tier-0-fast-path` — one file, understood, reversible, obvious acceptance, and no authentication, secrets, trust boundary, deployment, or production state in scope.
- What is skipped: intake interview, readiness probe, `save_run.py create`, session pin, phase manifest, delegation, and gatekeeper verdict. No run exists, so no Save Context block is emitted and nothing is written under `skillset-saves/`.
- What still happens: the change, a focused verification (the page renders the current year), and a brief completion note recording the tier and its rationale.
- Escalation rule: if the hardcoded year turns out to be read from a build-time config that also feeds licence headers, Tier 0 eligibility is gone — stop, reclassify to Tier 2, and carry the diff and the checks already run into normal intake rather than finishing under the fast path.

## Example 2 — Full pipeline

**User request:** run the full pipeline for a two-sided marketplace MVP

**Output:**
- Mode: full pipeline; route `design/commander` → `build/build-management` → `review/code-chief`, closing at `design-to-build`, `build-to-review`, and `review-to-delivery`.
- Intake: user roles, payment risk, and launch deadline are resolved through the grilling interview and written to `intake/report_grilling.md`, which is the hashed artifact behind the `decisions` gate key — a design package whose decisions are not backed by it fails `design-to-build` mechanically.
- First engagement: `session-memory` checkpoints the normalized intake before the first delegation, so `skills_engaged` already lists two skills before design starts.
- Next action: delegate design, then route the returned package through `gatekeeper-admiral` before any build work starts.

## Example 3 — Resume at build

**User request:** resume from the approved design package and get me through review

**Output:**
- Mode: resume. The save startup check classifies `skillset-saves/`; `_latest.md` is stale, so `runs/` is scanned, the directory is classified `orphaned` rather than `missing`, and the pointer is rebuilt by the sanctioned writer — `save_run.py recover --run-id <run> --owner admiral --reason "stale-latest-pointer"`, the lock having gone stale — with `LATEST_POINTER_REBUILT` appended to the agent trail to record it, instead of a second run being forked.
- Validation: the design package must still carry matching approval lineage and an unchanged revision. `check_readiness.py` runs with `--require-active-run` because this is a resume.
- Boundary rule: skip design only if the package revision is unchanged; otherwise rewind and re-gate from the earliest incomplete approved boundary, never from the newest artifact on disk.

## Example 4 — Redesign route

**User request:** our admin UI looks dated, give me some alternative directions before we commit

**Output:**
- Mode: partial pipeline on the redesign route. The request never says "redesign the UI", but an existing user-facing surface plus a request for alternatives is the redesign entry condition.
- Route: `design/redesign`, closing at `redesign-review`. Four static mocks are compared, the user picks one, and only then is a living prototype built for that direction. The chosen variant then enters `design/commander` as the `design-system` input and is locked at `design-to-build`; Admiral does not hand the prototype to build directly.
- Gate note: `mock_rendering` has no fallback at `redesign-review`, so a browserless host returns the `render` record with `result.status: inferred` labelled `INFERRED - no browser available` plus its limitation, and the verdict records the limitation rather than treating it as a clean pass.

## Example 5 — Security-audit route

**User request:** we handle card data now, I want this threat-modelled and hardened

**Output:**
- Mode: partial pipeline on the security route, closing at `security-review` under `review/cso`.
- Routing reason: threat modelling, accepted-risk decisions, and release security posture are governance judgments. `../../pipelines.yaml` gives the `review` pipeline no cso stage, so `review/code-chief` cannot absorb this even if a review is also requested.
- Tier: Tier 3 — security-sensitive scope, so the Tier 0 fast path is barred outright and the run carries explicit owner intent.

## Example 6 — Product-QA route

**User request:** test this like a real user would and tell me what breaks

**Output:**
- Mode: partial pipeline on the qa route, closing at `qa-review` under `qa`.
- Sweep ownership: a report-only run may execute the sweep through `qa-only`, but `qa` stays the only `qa-review` submitter and carries the `fixes_applied` applicability record `report-only run - no fixes applied`.
- Boundary note: defects QA finds are routed back to the owning phase as a REVISE packet; QA does not become a second build.

## Example 7 — Skill creation

**User request:** create a skill for automated invoice extraction with a strong eval loop

**Output:**
- Mode: create-skill, closing at `skill-maker-to-delivery`.
- Delegation: pass the skill intent, trigger phrases, packaging target, and success criteria to `skill-maker`. An arriving request missing any of the four stops at intake rather than becoming an underspecified brief.
- Verdict mapping: `SHIP` → `APPROVED`, `ITERATE` → `REVISE`, `BLOCKED` → `ESCALATE`.
- Delivery: the `.skill` package, the reviewer scorecard, and any remaining follow-up if it does not ship on the first pass.

## Example 8 — Team creation

**User request:** build me a team of skills for design review, bug triage, and release coordination

**Output:**
- Mode: create-team.
- Intake note: capture the specialist roster, coordination model, and expected handoff pattern before invoking skill-maker; `team_manifest` carries the `single skill - no team manifest produced` applicability record only when the result really is one skill.
- Delivery: the coordinated team package plus the recommendation for how Admiral should consume it in later runs.

## Example 9 — Drift constraint carried across boundaries

**User request:** ship this end to end, but stop if the build package drifts from the approved architecture

**Output:**
- Constraint: preserve architectural lineage across every handoff; record it in the Save Context `Risks` field so it survives each delegation.
- Gate behavior: if build output no longer matches the approved design package, route the package back for revision instead of allowing review to absorb the inconsistency. Two failed cycles exhaust `revise_policy.cycle_cap` and the run checkpoints to `phase_state: DISPUTED_AWAITING_USER`, which keeps the session pin while the user decides.
- Final package: approved artifacts, rewound boundaries, and any disputed items that still require user judgment, kept separate from the approved set.
