# Grill-Me Intake Doctrine

The single shared decision protocol for intake and plan stress-testing. Any skill
that takes a fresh request, confirms scope, or produces a first plan or design
runs this protocol before delegating work or committing to a deliverable. A plan
accepted without it is not gate-eligible.

Bound skills: `admiral`, `commander`, `skill-maker`, `researcher`, `planner`,
`architect`, and `engineer`.

Resolve only decisions that change the next deliverable, a locked contract, a
security boundary, migration path, rollback commitment, or user-visible
behavior.

## Rules

1. Explore code, configuration, history, and prior artifacts before asking
   anything discoverable. Reserve the user's attention for intent, priorities,
   constraints, and tradeoff preferences.
2. Ask one load-bearing question at a time and recommend an answer with evidence.
   A question without a recommendation is incomplete. This governs how you ask,
   not how the user may answer.
3. Resolve prerequisites before dependent decisions. Do not ask about rollout
   cadence before the release shape is known.
4. Record user decisions, discovered decisions, delegated defaults, rejected
   options, non-goals, and YAGNI deferrals with owners and reopen triggers.
5. Use reversible defaults for non-load-bearing branches instead of forcing a
   premature platform, abstraction, or future-scale commitment.
6. Apply adversarial pressure to high-risk or multi-stage plans: challenge
   assumptions, inspect failure paths, and require a falsifiable acceptance
   check.
7. End only when no material assumption remains unstated and the owner has
   confirmed the shared understanding or delegated the remaining calls.

## Decision prompt contract

When the host exposes a planning-mode or structured input primitive, use it for
unresolved design and configuration decisions. In Codex that is
`request_user_input`; in other hosts it is the closest native choice prompt.
Without one, ask the same decision as a concise plain-text question.

This contract is automatic. The user does not need to request planning mode. Any
fresh intake, plan, architecture, interface design, deployment setup, security
posture, data model, or configuration surface runs this loop before the
deliverable is generated or delegated.

- One decision per prompt, with two or three mutually exclusive options and the
  recommended one first.
- Auto-resolve discoverable configuration from files, manifests, or prior
  artifacts. When discovered evidence conflicts, ask which source wins.
- Ask judgment calls without delay: product behavior, API compatibility,
  authentication model, data retention, billing limits, deployment target,
  rollout risk, UI personality, density, accessibility tradeoffs.
- Offer delegation to the recommended default as a valid answer, and record it
  as a delegated default so gates can see the user accepted it.
- Block generation on unresolved load-bearing decisions. Either resolve it,
  record a deliberate deferral with owner and reopen trigger, or narrow the
  package so the decision is no longer load-bearing.

## Scaling

- Trivial, fully-specified requests still get one confirmation pass: restate the
  understanding, state the recommended approach, invite correction.
- Ambiguous or high-stakes requests get the full treatment until the end
  conditions above are genuinely met.
- Resumed runs re-confirm only the branches whose inputs changed.
- When a user answers several branches in one message, map each answer to its
  decision node, record the resolved decisions, and resume at the next
  unresolved branch. Never re-ask a settled decision, and never reject input for
  arriving out of order.

## Output

Write the result as the grilling log at
`skillset-saves/runs/{run-id}/intake/report_grilling.md`. It is the hashed
artifact behind the `decisions` evidence key at `design-to-build`
([gates.yaml](gates.yaml)); a package whose decisions are not backed by this
artifact fails the gate mechanically. The log carries:

- Resolved decisions with source (`user`, `codebase`, `prior-artifact`, or
  `delegated-default`) and the chosen option.
- Deferred decisions with why deferral is safe, the owner, and the phase that
  must reopen them.
- Rejected options for material tradeoffs, with one-line rationale.
- Non-goals and YAGNI deferrals with the trigger that reopens each.
