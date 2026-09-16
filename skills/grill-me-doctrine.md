# Grill-Me Intake Doctrine

The single shared decision protocol for intake and plan stress-testing. Any skill
that takes a fresh request, confirms scope, or produces a first plan or design
runs this protocol before delegating work or committing to a deliverable. A plan
accepted without it is not gate-eligible.

This file is canonical for the intake questioning protocol, the decision prompt
contract, how the protocol scales with stakes, the required content of the
grilling log, and the taste grilling the redesign pipeline runs. It is not
canonical for the meaning of the preference categories it walks through
([taste-doctrine.md](taste-doctrine.md) §3), for the evidence keys the logs back
([gates.yaml](gates.yaml)), or for where an artifact may be written
([save-ownership.yaml](save-ownership.yaml)).

Bound skills: `admiral`, `commander`, `skill-maker`, `researcher`, `planner`,
`architect`, `engineer`, `redesign`, and `taste` (for the taste grilling below).

Resolve only decisions that change the next deliverable, a locked contract, a
security boundary, migration path, rollback commitment, or user-visible
behavior.

## Contents

- [Enforcement status](#enforcement-status)
- [Rules](#rules)
- [Decision prompt contract](#decision-prompt-contract)
- [Scaling](#scaling)
- [Output](#output)
- [Taste grilling](#taste-grilling)
- [Failure paths](#failure-paths)

## Enforcement status

This doctrine is a protocol for a conversation, so nearly all of it is
judgement. Exactly one thing is mechanical: that a hashed artifact backs the
`decisions` key at `design-to-build`, and the `taste_grilling` key at
`redesign-review`. That check knows nothing about what the artifact contains.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| `decisions` is present at `design-to-build` and references a correctly hashed artifact in the package | machine-checked | `skills/harness/gatekeeper/check.py`, `decisions` listed in both `required_evidence` and `artifact_evidence` for that boundary in [gates.yaml](gates.yaml) |
| `taste_grilling` is present at `redesign-review` and references a correctly hashed artifact | machine-checked | `check.py`, the same two lists on that boundary |
| The submitted artifact is a grilling log, and carries the four sections [Output](#output) requires | **judgement** | nothing — see below |
| The grilling actually happened before the deliverable was produced | judgement | nothing; the log is written by the same run that would have skipped it |
| Rules 1 to 7, and the whole decision prompt contract | judgement | nothing |
| One decision per prompt, recommendation first, two or three exclusive options | judgement | nothing |
| That a deferral carries a real owner and a real reopen trigger | judgement | nothing at this boundary; a `findings` record enforces owner-and-reopen-trigger for deferred Majors, which is a different key |
| The taste grilling walked all eleven categories in the declared order | judgement | nothing |
| That a grilling answer became a Taste entry only after confirmation | judgement here; machine-checked at `taste-review` | the typed `confirmation` record required at `taste-review` ([taste-doctrine.md](taste-doctrine.md) §6) |
| This document itself | **judgement** | nothing — no comparator opens this file. The two mechanical rows above are properties of [gates.yaml](gates.yaml) and `check.py`, which know only that a hashed artifact backs a key. `team-manifest.yaml` `intake_doctrine` names this doctrine, and nothing resolves that name to a file (its own `authority.unchecked_keys` records the same gap), so this document could be renamed and every suite would still pass. |

**Why the four-section requirement is not mechanical, and what would make it
so.** `check.py` verifies that the `decisions` key names a path, that the path is
in the package, and that its sha256 matches the registered hash. Any hashed file
satisfies that. Separately, `skills/harness/gatekeeper/_gatecheck.py` supports
exactly the check that is missing: an `ArtifactSpec` matches a file by filename
glob and, optionally, by a `content_marker` regex that must appear inside it,
and a required spec whose marker never matches fails as a Major defect. The
design gatekeeper's `MANIFEST` in
`skills/design/gatekeeper-design/scripts/check.py` already uses that mechanism
for seven artifacts — `taste_snapshot`, for instance, requires one of
`canonical digest`, `source revisions`, `resolved entries`, or `applicability`
to appear in the file. It carries no spec for the grilling log. Adding one, with
a `*grilling*.md` pattern and a `content_marker` over the four section names
below, is what would convert this clause from judgement to machine-checked.
Until that exists, a reviewer reading the log is the only check, and the claim
that a package whose decisions are not backed by this artifact "fails the gate
mechanically" is true only of the artifact's existence and hash, never of its
content.

## Rules

1. Explore code, configuration, history, and prior artifacts before asking
   anything discoverable. Reserve the user's attention for intent, priorities,
   constraints, and tradeoff preferences.
2. Ask one load-bearing question at a time and recommend an answer with evidence.
   A question without a recommendation is incomplete. This governs how the
   question is asked, not how the user may answer.
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

Every rule here is judgement. None is machine-checked, and the log in
[Output](#output) is the only durable trace that any of them was applied.

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
([gates.yaml](gates.yaml)), owned there by `admiral`. A package whose `decisions`
key names no artifact, names a path that is not in the package, or names one
whose hash does not match fails the gate mechanically. A package that submits a
different hashed document under that key passes the machine and is caught only
by the reviewer, which is why the four sections below are a judgement
requirement rather than a checked one.

The log carries:

- Resolved decisions with source (`user`, `codebase`, `prior-artifact`, or
  `delegated-default`) and the chosen option.
- Deferred decisions with why deferral is safe, the owner, and the phase that
  must reopen them.
- Rejected options for material tradeoffs, with one-line rationale.
- Non-goals and YAGNI deferrals with the trigger that reopens each.

All four are required. A log missing any of them is an incomplete log, and the
reviewer at the boundary rejects it on that basis even though the mechanical
pass reported no defect.

## Taste grilling

The redesign pipeline runs a taste grilling: the same protocol, applied to
presentation and interaction preferences, owned by `taste` because every
confirmed answer becomes a preference entry under [taste-doctrine.md](taste-doctrine.md).

- Work through the eleven Taste categories (taste-doctrine §3) one category
  per prompt, in this order: visual-style, layout, density, typography,
  color-behavior, component-behavior, interaction-patterns, motion,
  content-tone, technology-ergonomics, anti-preference.
- Anchor each question to the design inventory: state what the current
  surface does today (the token, the pattern, the capture) and offer two or
  three mutually exclusive options with the recommended one first and a
  one-line rationale drawn from the inventory's inconsistencies or the
  accessibility baseline.
- Record every answer as a candidate entry: `category`, `normalized_rule`,
  `strength` (`hard`, `strong`, `soft`), `source` (`explicit` for a direct
  answer, `confirmed-inference` for an accepted recommendation), the
  applicability selectors, and any anti-preference the answer implies.
- Never derive a candidate from protected or personal characteristics, and
  never let a Taste answer weaken an accessibility, security, or gate
  requirement; surface the collision and keep the requirement.
- Ask the scope question last: project only, or also global. Promotion to
  global scope needs its own explicit confirmation.

**The order is a permutation, not a separate list.** The eleven identifiers
above are exactly the eleven in [taste-doctrine.md](taste-doctrine.md) §3 — the
same set, no additions, no omissions — reordered so the grilling moves from the
broadest decision to the narrowest and ends on denials. The registry there is
canonical for the identifiers and their meanings; this section is canonical only
for the order they are asked in. Adding, removing, or renaming a category in §3
therefore requires the same change here, and nothing will fail if that is
forgotten: no comparator ties the two lists together, so the tie is maintained
by review. The same obligation runs to [design-doctrine.md](design-doctrine.md)
§9, which requires four redesign directions to differ in at least three of these
same categories.

Write the result as the taste grilling log at
`skillset-saves/runs/{run-id}/redesign/reports/taste-grilling.md` (the
`taste-grilling-log` artifact behind the `taste_grilling` evidence key at
`redesign-review`, owned there by `taste`): one decision per category with the
current state, the options, the recommendation, the answer, and the resulting
candidate entries. The same limit applies as for the grilling log above — the
gate checks that a hashed artifact backs the key, not that it contains eleven
categories.

`taste` then confirms and persists the candidates through its own pipeline and
returns the effective-profile snapshot that `architect` and `prototyper`
consume read-only. Confirmation is where the mechanical floor returns: the typed
`confirmation` record required at `taste-review` names the actor, the timestamp,
the confirmed scope, and the exact candidate-id set, and `check.py` verifies it.
A grilling answer that never reached that record never became Taste.

## Failure paths

- **The host exposes no structured input primitive.** Ask the same decision as a
  concise plain-text question, one decision at a time, recommendation first. The
  contract is about the decision, not the widget; the absence of a prompt
  primitive is never a reason to skip the question.
- **The user does not answer a load-bearing decision.** Do not guess and do not
  proceed. Either record a deliberate deferral with a named owner and a reopen
  trigger, or narrow the package until the decision is no longer load-bearing.
  Those are the only two exits, and both are recorded in the log.
- **The user answers several branches at once, or out of order.** Map each
  answer to its decision node, record the resolved decisions, and resume at the
  next unresolved branch. Never re-ask a settled decision and never reject input
  for arriving in an unexpected order.
- **Discovered evidence conflicts with itself.** Do not silently pick a winner.
  Present the conflicting sources and ask which one governs, then record the
  answer with source `user` rather than `codebase`.
- **The run is Tier 0.** No grilling log is produced, because Tier 0 opens no
  package and closes no gate ([routing-doctrine.md](routing-doctrine.md)). If
  the work grows past Tier 0, the grilling runs before the first delegation of
  the reclassified run, not retroactively.
- **Persistence is inactive, so the log cannot be written.** The protocol still
  runs and its result is surfaced inline. The gate cannot close without the
  hashed artifact, so a run that needs `design-to-build` reports the blocked
  persistence rather than submitting without the key.
- **A taste grilling answer collides with an accessibility, security, or gate
  requirement.** The requirement stands and the candidate is not recorded as a
  preference. Surface the collision in the log so the reviewer sees what was
  asked and why it was refused.
- **The grilling log and this doctrine disagree about what a section requires.**
  This file governs the log's content. Where a downstream skill has restated the
  four sections differently, the restatement is drift and is corrected here
  first, then in the skill.
