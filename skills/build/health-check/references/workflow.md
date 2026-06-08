# Workflow Reference

## Contents

1. Runtime-health verification sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Runtime-Health Verification Sequence

1. Confirm the environment, revision, and runtime contract that the health pass is meant to prove.
2. Gather startup logs, readiness probes, smoke-flow evidence, and dependency checks for the real target surface.
3. Evaluate whether the environment is healthy, degraded, or unverified across the critical runtime boundaries.
4. Package the result so build-management and gatekeeper-build can see exactly what is ready and what still blocks confidence.

## Decision Rules

- Prefer health evidence from real user-critical paths over shallow green infrastructure signals alone.
- Keep transient warm-up behavior separate from repeatable degradation.
- Treat unexercised dependencies and feature paths as unverified, not implicitly healthy.
- Escalate when the environment can run but still fails the approved readiness contract.

## Acceptance Checklist

- Environment and revision under test are explicit.
- Startup, readiness, and critical dependency checks are named.
- The report distinguishes healthy, degraded, and unverified boundaries.
- Evidence supports the runtime claim being made.
- Next remediation or release action is clear.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `build/build-management` — delegating orchestrator; receives the health report and owns remediation routing and resubmission.
- `build/gatekeeper-build` — downstream gate; consumes health verification evidence when deciding whether the build package can advance.
