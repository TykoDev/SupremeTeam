# Execution Contract

This file is the canonical clause source for the short execution preamble every
orchestrator and gatekeeper applies. Phase-specific contracts may add
constraints, but they must not weaken these shared clauses.

## Canonical clauses

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Tier selection

Tier is a property of the run, not a fixed attribute of a skill. The same skill
runs at Tier 0 for a typo fix and at Tier 3 for an authentication change. Blast
radius decides:

| Tier | Blast radius | Ceremony |
| --- | --- | --- |
| 0 | Local, understood, reversible; acceptance is obvious | Direct change, focused verification, brief completion note |
| 1 | Bounded and read-only | Intake, evidence, no state change |
| 2 | Multi-step edits, delegation, external coordination | Full pipeline route, saved run, gate package |
| 3 | Destructive, security-sensitive, production, irreversible | Tier 2 plus explicit owner intent and a fresh human go decision |

## Maintenance rule

When a shared clause changes, update this file first, then update the local
statement of the clause in the affected skills, then rerun
`python skills/scripts/validate_manifests.py` and the validation suites. The six
numbered clauses are compared exactly; a paraphrase in a skill is drift.
