# Workflow Reference

## Contents

1. Continuity sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Continuity Sequence

1. Determine whether the request is a checkpoint, a learning write, a resume, or a lookup against prior learnings.
2. Save only the durable state needed for safe continuation: current boundary, active artifacts, blockers, and the next intended action.
3. Normalize learnings into short searchable entries with evidence and confidence so later sessions can query them quickly.
4. On resume, reload only the verified artifacts and notes relevant to the immediate next step, then surface any drift or missing state.

## Decision Rules

- Prefer short, evidence-backed continuity notes over verbose narrative.
- Treat missing artifact lineage as a resume blocker, not a guessable inconvenience.
- Keep learnings reusable by other skills rather than tied to one transient conversation turn.
- Never persist sensitive ephemeral tokens or secrets as durable state.

## Acceptance Checklist

- Checkpoint names the active stage, blockers, and next action.
- Learnings include evidence or confidence context.
- Resume output distinguishes verified state from missing or stale state.
- Saved material is durable, searchable, and safe to retain.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `admiral` is the primary invoker — calls session-memory at context tier 3+ escalations, before every gatekeeper-admiral submission, at session end, and on error recovery.
- `design/commander`, `build/build-management`, and `review/code-chief` consume continuity records when long-running work spans sessions.
- Any specialist may request a checkpoint via its orchestrator when context pressure rises.
