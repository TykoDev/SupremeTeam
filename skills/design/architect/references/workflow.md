# Workflow Reference

Read this when producing an `architecture`, `interface-contract`, or
`design-directions` artifact. It carries the boundary-decision method, the two
document templates, the procedure behind three of the Required Contracts, and the
acceptance checklist. The endpoint template lives in `api-endpoint-design.md` and
the frontend pipeline in `visual-design-system.md`; neither is repeated here.

## Contents

1. Architecture sequence
2. Boundary decision method
3. Architecture package template
4. Design-directions template (redesign pipeline)
5. Contract detail
6. Decision rules
7. Acceptance checklist
8. Collaboration notes

## Architecture Sequence

1. Read the `requirements-brief` before drawing anything: the requirements, their
   sources, the non-functional targets with their numbers, and the open
   assumptions. A target with no number cannot be designed against and goes back
   to `design/researcher`.
2. Enumerate the nouns the system owns — entities, streams, jobs, external
   systems — and assign each exactly one owning component. Ownership is the
   decision; the diagram is its record.
3. Draw the edges: which component calls which, synchronously or not, carrying
   what shape. Every edge becomes an interface contract or an event schema.
4. Name the invariants each boundary preserves and what happens when it fails:
   partial write, duplicate delivery, stale read, unavailable dependency.
5. Mark the trust boundaries the edges cross, and seed the threat model against
   them (§Contract detail).
6. For API surfaces, run `api-endpoint-design.md` in full before the package is
   declared build-ready.
7. For user-facing surfaces, run `visual-design-system.md` in full: detection,
   interview or existing-frontend analysis, tokens, component template, preview,
   `design-system.md`, then the eight-dimension adversarial review to ≥ 9 on every
   dimension with contrast verified.
8. Package the result against the template below and return it to
   `design/commander`.

## Boundary Decision Method

Apply these in order; the first that resolves the question wins, and the reason is
recorded in the package.

| Test | Question | If it resolves |
| --- | --- | --- |
| Single writer | Which component may change this state? | That component owns it; everything else reads or subscribes |
| Failure blast radius | If this component is down, what stops working? | A boundary that takes down an unrelated capability is drawn in the wrong place |
| Rate of change | What changes on different schedules? | Separate what changes weekly from what changes yearly |
| Transaction scope | What must commit together? | Never split an invariant across a network call |
| Data sensitivity | What crosses a trust boundary? | That crossing is an explicit interface with auth, validation, and an error taxonomy |
| Team ownership | Who is paged when it breaks? | One owner per component; two owners is an unresolved boundary |

Two components failing the single-writer test on the same state is split-brain:
freeze it, assign one authoritative owner, and expose the rest as read or
event-driven consumers. Do not resolve it with a lock, a sync job, or a
convention.

## Architecture Package Template

```markdown
# Architecture — {scope}

**Revision**: {n}   **Requirements brief**: {path}@{sha256}   **Stack**: {slug or "unlocked"}

## Components

| Component | Owns | Depends on | Failure behavior | Paged owner |
| --------- | ---- | ---------- | ---------------- | ----------- |

## Data flow

{the edges: source -> sink, synchronous or event, payload shape, ordering and
delivery guarantee}

## Invariants

| Invariant | Enforced by | Broken when | Detected by |
| --------- | ----------- | ----------- | ----------- |

## Interfaces

{endpoint inventory per api-endpoint-design.md, or the internal interface list:
name, caller, callee, request shape, response shape, error taxonomy}

## Trust boundaries

| Boundary | Untrusted input | Privileged action | Secret or asset | STRIDE notes |
| -------- | --------------- | ----------------- | --------------- | ------------ |

## Technology rationale

| Choice | Alternatives rejected | Why | Reversible? |
| ------ | --------------------- | --- | ----------- |

## Non-functional targets

| Target | Number | Supported by | Unproven? |
| ------ | ------ | ------------ | --------- |

## Decision Register

{resolved, deferred, rejected, and YAGNI-deferred options, each with source
(`user`, `codebase`, `prior-artifact`, `delegated-default`), owner, and reopen
trigger}

## Open decisions

| Decision | Owner | Blocks | Latest safe decision point |
| -------- | ----- | ------ | -------------------------- |
```

## Design-Directions Template (Redesign Pipeline)

`design-directions.md` carries exactly four directions. They must diverge in at
least three Taste categories (`../../../taste-doctrine.md` §3); palette-only
variation is one direction wearing four coats of paint, and the gate reads it as a
`REVISE`.

```markdown
# Design Directions — {surface}

**Inventory**: {path}@{sha256}   **Taste grilling log**: {path}@{sha256}
**Snapshot digest**: sha256:{…}

## Divergence matrix

| Category | Direction A | Direction B | Direction C | Direction D |
| -------- | ----------- | ----------- | ----------- | ----------- |
| visual-style | | | | |
| density | | | | |
| layout | | | | |
| motion | | | | |
| typography | | | | |

{at least three rows must differ across all four columns}

## Direction {A} — {name}

**Concept**: one paragraph a person could recognise the result from.
**Token strategy**: palette basis, type scale, spacing unit, radius, elevation,
motion budget — as values, not adjectives.
**Component approach**: which shadcn primitives carry the identity, which are left
plain, and what the direction names itself.
**Differentiators**: the three things only this direction does.
**Taste traceability**:

| Decision | Preference id | Strength | Snapshot digest |
| -------- | ------------- | -------- | --------------- |

**Inventory fit**: which recorded inconsistencies this direction resolves, and
which accessibility baseline findings it fixes.
```

## Contract Detail

### Grill-Me Intake

`../../../grill-me-doctrine.md` binds this skill. Resolve every load-bearing
branch one question at a time; use the host's planning-mode or structured-input
primitive for unresolved design and configuration choices, and a concise plain
question where none exists. Always recommend an answer with its evidence — a
question without a recommendation is incomplete. Explore the codebase, configs,
and prior artifacts instead of asking what is discoverable, and record every
resolved, deferred, rejected, and YAGNI-deferred option in the Decision Register
that ships with the architecture package. For user-facing surfaces the interview
also covers visual intent: brand and personality keywords, target users, layout
intent, density, and the dark-mode requirement.

### Decision provenance and Taste boundary

Trace every design-system decision to one of four sources: an effective Taste
entry in the supplied snapshot, an explicit current-run instruction, an existing
project convention, or a documented designer/architect judgment. For Taste-derived
decisions, record the snapshot digest and the preference id in the traceability
table; the other three provenance kinds use the same table with no invented Taste
id. Consume the snapshot read-only — never edit project or global Taste storage.
New feedback discovered during design becomes a Taste candidate record (source
context, proposed preference, rationale, affected artifacts) routed through
`design/commander` and `admiral` to the Taste pipeline for confirmation; it is not
an effective preference in the current run unless Taste confirms it and the
snapshot is re-resolved before the gate.

### Threat Model Seed

Triggered whenever the design touches authentication, authorization, sensitive
data, external inputs, model or tool output, file upload, webhooks, dependency
execution, or server-side fetches. Produce a lightweight STRIDE-oriented summary
per trust boundary: what crosses it untrusted, which privileged action sits behind
it, which secret or high-value asset it protects, and the spoofing, tampering,
repudiation, disclosure, denial, and elevation notes that apply. The point is that
`review/cso` and `review/mr-robot` inherit a stated attack surface instead of
reconstructing it from the component diagram.

## Decision Rules

- Choose boundaries that make ownership and failure modes visible; a boundary that
  hides a failure is a boundary drawn for the diagram, not the system.
- Treat hidden external contracts as structural risk, not later implementation
  detail — an unspecified third-party shape is an unbounded change surface.
- Prefer explicit tradeoffs over vague claims of flexibility. "Extensible" with no
  named extension point is an untested promise.
- Avoid speculative abstraction: no indirection the approved scope does not
  require, and every deferred generalisation gets a reopen trigger.
- A non-functional target the boundary design cannot support is marked unproven
  against the interface that would break first, not quietly restated.
- Escalate when an architecture choice implies an upstream business or platform
  decision; commit nothing irreversible that was not approved upstream.

## Acceptance Checklist

- Every component has one owner, a stated failure behavior, and a paged owner.
- Every edge in the data flow resolves to an interface contract or an event schema.
- Every invariant names what enforces it, what breaks it, and what detects the break.
- Endpoint inventory and per-endpoint templates are complete when any API, webhook,
  event-ingest, or internal service endpoint is in scope.
- Every non-functional target carries a number and a supporting mechanism, or is
  marked unproven.
- Trust boundaries are enumerated with their STRIDE notes when the Threat Model
  Seed is triggered.
- For a user-facing surface: the §5 component template and UI/UX handoff are filled
  concretely, contrast is verified to WCAG 2.2 AA, and every adversarial-review
  dimension scores ≥ 9.
- For a redesign: four directions, divergent in at least three Taste categories,
  each with traceability rows bound to the snapshot digest.
- The Decision Register is present, and every remaining decision has an owner and a
  latest safe decision point.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

The skills this workflow hands to and receives from are named in `../SKILL.md` § Collaboration Surface. What this workflow adds:

- `design/planner` sequences delivery against these boundaries; `design/engineer` slices against the same contracts.
- `design/prototyper` draws one static mock per direction from the directions produced here, and later builds the living prototype for the one direction the user selects.
