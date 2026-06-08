# Example Invocations

## Example 1

**User request:** review code quality of the service-layer refactor

**Output:**
- Scope: service layer, repository adapter, and the new mapper used by three endpoints.
- Major finding: the refactor reduces duplication locally but introduces a second orchestration layer that now splits business rules across controllers and services.
- Remediation order: consolidate orchestration into one layer before pursuing any naming cleanup.

## Example 2

**User request:** check maintainability of the job runner

**Output:**
- Scope: job runner, queue configuration, and retry policy helpers.
- Finding set: configuration is now duplicated across three modules, which raises the cost of changing timeout or retry behavior safely.
- Delivery: maintainability packet with one structural issue, one debt note, and a bounded fix sequence.

## Example 3

**User request:** measure technical debt in the feature-flag subsystem

**Output:**
- Scope: flag evaluation, environment overrides, and rollout configuration.
- Structural concern: ownership is split between request middleware and a shared helper, so every new rollout path repeats the same branching logic.
- Handoff: ask `review/code-review` to confirm whether the same drift is already creating merge-readiness friction in the current diff.
