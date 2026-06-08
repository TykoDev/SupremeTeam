# Example Invocations

## Example 1

**User request:** design the architecture

**Output:**
- Boundary model: public API, workflow engine, notification worker, audit store, and identity service integration.
- Critical tradeoff: asynchronous workflow events reduce coupling but require idempotent replay handling.
- Next move: hand the package to `engineer` with the event contract and ownership map locked.

## Example 2

**User request:** define system boundaries

**Output:**
- Ownership: billing owns invoice generation, core app owns subscription state, and analytics consumes events only.
- Risk note: the current proposal lets both billing and app services mutate subscription state, which is rejected as a split-brain boundary.
- Recommendation: move authoritative state to one service and expose the rest as read or event-driven consumers.

## Example 3

**User request:** write the architecture package

**Output:**
- Deliverables: component map, data-flow summary, external dependency list, and interface contract draft.
- Open decision: choose between per-tenant queues and shared queues before sizing the async worker fleet.
- Boundary note: the package is ready for downstream design work except for that single scaling decision.
