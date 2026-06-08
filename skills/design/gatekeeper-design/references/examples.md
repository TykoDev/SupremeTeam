# Example Invocations

## Example 1

**User request:** validate the design deliverable

**Output:**
- Verdict: `REVISE`.
- Missing alignment: the architecture introduces an event bus, but the implementation spec and API contract still assume only direct request-response flows.
- Required fix: reconcile the architecture and downstream contracts before the packet can exit design.

## Example 2

**User request:** review design phase output

**Output:**
- Verdict: `APPROVED`.
- Evidence map: stakeholder goals, ADRs, API contract, frontend architecture, and stack locks all point to the same revision and phase exit.
- Handoff note: build may consume the packet as long as the approved revision remains unchanged.

## Example 3

**User request:** check design readiness

**Output:**
- Verdict: `ESCALATE`.
- Conflict: the packet alternates between HIPAA-bound storage rules and a third-party analytics choice that would violate those constraints.
- Required decision: resolve the product and compliance tradeoff before the design can advance.
