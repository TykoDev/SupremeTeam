# Workflow Reference

## Contents

1. Architecture sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Architecture Sequence

1. Confirm the scope, system goals, and non-functional expectations that the architecture must satisfy.
2. Draw the major components, ownership boundaries, interfaces, API endpoint contracts when applicable, and critical data flows before committing to implementation details.
3. Check the design against risky boundaries such as integration contracts, consistency models, scaling assumptions, and failure recovery.
4. Package the result so build-facing consumers know what is fixed, what is flexible, and which decisions still need approval.

## Decision Rules

- Choose boundaries that make ownership and failure modes visible.
- Treat hidden external contracts as structural risk, not later implementation detail.
- Prefer explicit tradeoffs over vague claims of flexibility.
- Escalate when architecture choices imply an upstream business or platform decision.

## Acceptance Checklist

- Components and ownership boundaries are explicit.
- Interface contracts, API endpoint contracts, and data flow are clear enough for downstream implementation planning.
- Endpoint inventory and per-endpoint templates are complete when any API, webhook, event-ingest, or internal service endpoint is in scope.
- Non-functional risks are tied to concrete boundaries.
- Remaining architectural decisions are narrow and explicit.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `design/commander` owns phase sequencing and consolidated package assembly.
- `design/gatekeeper-design` validates that the architecture is coherent enough for interface and implementation planning.
