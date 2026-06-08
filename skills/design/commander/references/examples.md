# Example Invocations

## Example 1

**User request:** design this system

**Output:**
- Phase path: researcher -> planner -> architect -> engineer.
- Gate note: architect must produce the frontend/UI visual design system (shadcn/ui component template, tokens, preview, spec, design-review scorecard) because the request includes an operator-facing web console.
- Delivery: consolidated design package with phase approvals, stack-lock continuity, and one unresolved decision about tenancy boundaries.

## Example 2

**User request:** create the design package

**Output:**
- Resume state: existing requirements and planning artifacts are approved, so commander starts at architecture and carries the prior approvals forward.
- Drift rule: if architecture changes the event model, planner must reopen because milestone ordering depends on that contract.
- Next move: send the completed package through `design/gatekeeper-design` before handing it to admiral.

## Example 3

**User request:** start the design pipeline

**Output:**
- Constraint: backend-only service, so architect's frontend/UI visual design system is explicitly skipped with justification recorded in the package.
- Package shape: requirements, plan, architecture, implementation specification, and gate approvals are all included.
- Escalation note: the pipeline pauses only if a scope choice or missing prerequisite prevents the next phase from starting.
