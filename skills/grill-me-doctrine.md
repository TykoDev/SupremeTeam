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

This doctrine is a protocol for a conversation, so most of it is judgement. Two
things are mechanical: that a hashed artifact backs the `decisions` key at
`design-to-build` (and the `taste_grilling` key at `redesign-review`), and that
the `decisions` artifact has the shape [Output](#output) fixes — four tables,
every cell filled, unique `D-<n>` ids, sanctioned sources. What the answers say,
and whether the interview happened, stays judgement.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| `decisions` is present at `design-to-build` and references a correctly hashed artifact in the package | machine-checked | `skills/harness/gatekeeper/check.py`, `decisions` listed in both `required_evidence` and `artifact_evidence` for that boundary in [gates.yaml](gates.yaml) |
| `taste_grilling` is present at `redesign-review` and references a correctly hashed artifact | machine-checked | `check.py`, the same two lists on that boundary |
| The submitted artifact is a grilling log, and carries the four sections [Output](#output) requires | **machine-checked** | `check.py`, `decisions` typed `decision_log` in [gates.yaml](gates.yaml): each section, its table columns, every cell, unique `D-<n>` ids, a sanctioned `Source`, at least one resolved decision. `check.py --intake-log` runs the same check on its own, and the `gate_watch` hook runs it whenever the log is written |
| The grilling actually happened before the deliverable was produced | judgement | nothing; the log is written by the same run that would have skipped it |
| Rules 1 to 7, and the whole decision prompt contract | judgement | nothing |
| One decision per prompt, recommendation first, two or three exclusive options | judgement | nothing |
| Every log entry carries a stable `D-<n>` id | **machine-checked** | the `decision_log` check refuses a row whose ID is not `D-<n>` or repeats; `check.py --judgment` fails a gate finding whose `D-<n>` the log does not contain |
| That a deferral carries an owner and a reopen trigger | **machine-checked for presence**; judgement for whether they are real | the `decision_log` check refuses an empty Owner, Reopen phase or Reopen trigger cell (a dash, `n/a`, `none`, `tbd` or `?` counts as empty) |
| The taste grilling walked all eleven categories in the declared order | judgement | nothing |
| That a grilling answer became a Taste entry only after confirmation | judgement here; machine-checked at `taste-review` | the typed `confirmation` record required at `taste-review` ([taste-doctrine.md](taste-doctrine.md) §6) |
| This document itself | **partial structural coverage; semantic judgement** | Catalog prose scans inspect doctrine text, not the quality or timing of an interview. The mechanical rows above are properties of [gates.yaml](gates.yaml) and `check.py`, which read the log's structure and never its meaning. `team-manifest.yaml` `intake_doctrine` names this doctrine, and nothing resolves that name to a file (its own `authority.unchecked_keys` records the same gap), so pointer resolution is not guaranteed by that declaration. |

**What the mechanical check reads.** `check.py` parses the `decisions` artifact as
Markdown: each of the four headings below (any level, case and spacing folded),
the first table under it, its header row, and its data rows. Fenced code is
blanked first, so a template quoted in a fence is never read as the log. Extra
columns and prose around the tables are allowed. The parse is deterministic and
knows nothing about whether an answer is wise, so a log that passes it can still
be a poor interview — that part is the reviewer's.

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

Delegated pipeline specialists consume Admiral's confirmed intake; they do not
repeat the user interview from a sub-agent. Admiral owns `intake-grilling` and
the user channel. Commander or a specialist discovering a new load-bearing
choice returns one bounded question and recommendation to Admiral, then holds
its deliverable until the updated Decision Register arrives. Applying this
doctrine to an inherited decision is not permission to bypass that owner.

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
- A bounded change to an existing codebase — a fix or a small feature that the
  interview confirms changes no architecture, interface contract, data model, or
  trust boundary — records that determination in the Decision Register, and every
  downstream artifact is sized to it: a one-page architecture note, a plan of one
  slice, conditional stages skipped with their applicability records, the Taste
  snapshot reused when the profile is unchanged. The gates and their evidence keys
  do not change; the length of what satisfies them does.
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
whose hash does not match fails the gate mechanically, and so does one whose log
lacks the fixed tables below ([gates.yaml](gates.yaml) `decision_log`).

The log carries, every entry under a stable id `D-<n>` that is unique in the log
and never reused for a different decision across revisions:

- Resolved decisions with source (`user`, `codebase`, `prior-artifact`, or
  `delegated-default`) and the chosen option.
- Deferred decisions with why deferral is safe, the owner, and the phase that
  must reopen them.
- Rejected options for material tradeoffs, with one-line rationale.
- Non-goals and YAGNI deferrals with the trigger that reopens each.

All four are required, each as a `##` section holding one table with at least
these columns (a section with no entries keeps its header row and has no data
rows; Resolved decisions needs at least one row):

```markdown
## Resolved decisions

| ID | Decision | Chosen | Source |
| --- | --- | --- | --- |
| D-1 | API style | REST | user |

## Deferred decisions

| ID | Decision | Why deferral is safe | Owner | Reopen phase |
| --- | --- | --- | --- | --- |
| D-2 | Pagination | one page fits every tenant today | API lead | build |

## Rejected options

| ID | Option | Rationale |
| --- | --- | --- |
| D-3 | GraphQL | no client needs it |

## Non-goals and YAGNI deferrals

| ID | Non-goal | Reopen trigger | Owner |
| --- | --- | --- | --- |
| D-4 | Bulk export | a tenant asks for it | product owner |
```

`Source` is one of `user`, `codebase`, `prior-artifact`, `delegated-default`. Every
listed cell is filled; `-`, `n/a`, `none`, `tbd` and `?` count as empty. A log
that misses any of this fails `check.py` at `design-to-build`, and the `gate_watch`
hook reports it as soon as the log is written.

The ids are what make this log the source of truth a gate can be held to. A
gatekeeper finding grounded in an intake decision cites it as
`{kind: decision, ref: D-<n>, artifact: <this log>}`, and
`harness/gatekeeper/check.py --judgment` refuses the finding when the log the
package's `decisions` key names does not contain that id
([gates.yaml](gates.yaml) `judgment_policy`). A requirement the gate believes the
log should hold and does not is an `ESCALATE` to `admiral`, which owns this
interview, never a `REVISE` to the specialist who built on the log as written.

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
