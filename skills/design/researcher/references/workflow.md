# Workflow Reference

## Contents

1. Research sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Research Sequence

1. Define the actors, goals, and decision points the research must clarify.
2. Collect evidence from the strongest available sources and separate direct evidence from analogy or assumption.
3. Translate the findings into requirements, constraints, risks, and open questions that later design phases can consume directly.
4. Package the result so the next design owner knows what is proven, what is likely, and what still needs discovery.

## Decision Rules

- Prefer evidence that changes a design decision, not trivia that only expands the document.
- Keep technology lock-in out of the research packet unless an earlier approval already fixed it.
- Preserve disagreement across sources instead of averaging it into fake certainty.
- Escalate when the missing evidence is material to the next design boundary.

## Acceptance Checklist

- Actors, goals, and constraints are explicit.
- Confirmed facts and assumptions are separated.
- Requirements and risks are usable by later design phases.
- Open questions have clear ownership or next steps.
- The packet is ready for design-gate review.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `design/commander` consumes the research packet and routes it into later design phases.
- `design/gatekeeper-design` validates whether the research output is strong enough for the next boundary.
