# Example Invocations

Each example shows the stage path Commander takes, the `design-to-build` evidence
the run produces, and the one decision that would otherwise be got wrong. Every
example assumes an active Admiral handoff; a cold invocation hands off to
`admiral` first.

## Contents

1. Full design with a user-facing surface
2. Resume at architecture
3. Backend-only service, no UI surface
4. No saved Taste profile
5. Second REVISE on the same keys

## Example 1 — Full design with a user-facing surface

**User request:** design this system (a multi-tenant operator console with a billing API)

**Output:**
- Stage path: `design/researcher` → `design/architect` (architecture) → `design/architect` (interfaces and design system, because a user-facing surface exists) → `build/security-builder` (`security-seed`, because tenancy moves a trust boundary) → `design/planner` → `design/engineer` → commander's own stack lock.
- Evidence assembled: `decisions` backed by the run's `intake/report_grilling.md`, hashed `architecture` and `plan`, `interfaces` as the endpoint inventory, `acceptance` from planner, `security_seed` naming the tenant isolation boundary and the controls the build owes, `ui_evidence` as the shadcn/ui component template plus `design-system.md`, the hashed `taste_snapshot`, and `stack_lock` from `check_runtime.py --detect-project`.
- Decision that matters: planning waits on the approved architecture rather than running beside it, because milestone ordering is derived from the component boundaries architect fixes.
- Before submitting: `python skills/harness/gatekeeper/check.py --boundary design-to-build --package design/manifest.json`, no `--verdict-out`; every mechanical failure is fixed first.
- Open item: one unresolved decision about tenancy boundaries, carried in the escalation packet with a recommended default rather than silently defaulted.

## Example 2 — Resume at architecture

**User request:** create the design package (resuming a run whose requirements brief is already approved)

**Output:**
- Resume state: the requirements brief carries a matching approval record at the current revision and is carried forward; architecture is the earliest incomplete boundary, so the run starts there.
- Drift rule: if architecture changes the event model, `design/planner` reopens because milestone ordering depends on that contract, and the implementation spec reopens after it. The prior research approval survives because nothing it asserted changed.
- Taste recheck: the snapshot's project and global source revisions are rechecked immediately before `design-to-build`. A changed revision invalidates `taste_snapshot`, requires re-resolution through Admiral/Taste, and replays the affected design-system decisions.
- Next move: submit the consolidated package through `design/gatekeeper-design` at `design-to-build`, then hand it to admiral for the `gatekeeper-admiral` pass.

## Example 3 — Backend-only service, no UI surface

**User request:** start the design pipeline for an internal event-ingest service

**Output:**
- Skipped stage: the interface-and-design-system stage produces no component template, so `ui_evidence` carries the sanctioned fallback `no user-facing surface - design system not engaged` as an applicability record naming reason, scope, and decider — not an omitted key and not a bare string.
- Not skipped: `security_seed`. The service terminates an external ingest connection, so `build/security-builder` states the boundary and its controls. Even with no boundary movement the key would still be required, because `../../../gates.yaml` `fallback_values` carries no entry for it.
- Stack lock: `check_runtime.py --detect-project` matches an existing registry slug, so `stack_lock` names the slug, the locked versions, and the overlay sha256 rather than the no-new-runtime fallback.
- Package shape: requirements, architecture, interfaces, plan, acceptance, implementation specification, `security_seed`, `stack_lock`, `taste_snapshot`, `ui_evidence` applicability record, and the approval record for every executed phase.

## Example 4 — No saved Taste profile

**User request:** plan and architect this project (a greenfield tool, no prior Taste work)

**Output:**
- Taste resolution: Admiral/Taste is asked to resolve and confirms neither store holds a profile. `taste_snapshot` carries the sanctioned fallback `no saved Taste profile available`, recorded with reason, scope, and decider.
- Boundary honoured: Commander does not read the preference stores to build a snapshot of its own. A digest Commander invented cannot be revalidated before the gate, so a failed or erroring resolution escalates to Admiral instead of being filled in locally.
- Presentation choices in this run: taken from explicit run instructions and documented architect judgment, recorded in the traceability table with their provenance kind and no invented Taste id.
- Feedback captured during design: emitted as Taste candidate records and routed through Admiral to the Taste pipeline; nothing is treated as an effective preference unless Taste confirms it and Commander re-resolves before the gate.

## Example 5 — Second REVISE on the same keys

**User request:** (continuation) the gate came back REVISE again on interfaces and acceptance

**Output:**
- Cycle state: this is the second `REVISE` on `design-to-build`, which exhausts `../../../gates.yaml` `revise_policy.cycle_cap` of 2.
- Action: stop resubmitting. Escalate to Admiral with both revise packets, both verdict records, and the unclosed keys named with their owners (`interfaces` → `design/architect`, `acceptance` → `design/planner`).
- Why the cap exists: two failed cycles on the same keys indicate disagreement about the requirement rather than a defect in the artifact, and a third submission would spend the gatekeeper's judgment on the same dispute.
- What Admiral receives: the dispute, the recommended default for each key, and the evidence preserved at both revisions rather than overwritten into one history.
