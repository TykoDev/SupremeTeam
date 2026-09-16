# Workflow Reference

Read this when producing a `requirements-brief`: it carries the research sequence,
the confidence tiers, the document template the rows live in, the evidence rules,
and the acceptance checklist.

## Contents

1. Research sequence
2. Confidence tiers
3. Requirements-brief template
4. Evidence rules
5. Decision rules
6. Acceptance checklist
7. Collaboration notes

## Research Sequence

1. Define the actors, the jobs they are trying to finish, and the decisions the
   architecture stage cannot make until this brief lands. Research that changes no
   downstream decision is not in scope.
2. Mine what already exists before asking anyone: repository, configuration,
   tickets, prior artifacts, support history, existing schemas. Every answer found
   here arrives with a path, which is the strongest provenance available.
3. Collect the rest from stakeholders and domain sources, recording the tier as the
   evidence is collected rather than grading it afterwards from memory.
4. Write one row per material requirement or constraint with all five fields.
5. Group the rows into requirements, constraints, non-goals, risks, and open
   questions, and state which downstream decision each group constrains.
6. Package so the next design owner can tell, per row, what is proven, what is
   likely, and what still needs discovery.

## Confidence Tiers

One tier per row, assigned from what was actually observed. The tier is not a
measure of how reasonable the claim sounds.

| Tier | Assign when | Architecture may |
| --- | --- | --- |
| `observed` | Read directly from a system, dataset, log, schema, or artifact in this project, with a path or query | Treat it as fixed; design against it without hedging |
| `reported` | Stated by a named stakeholder or a project document, not independently verified | Design against it, and name it as a dependency in the boundary rationale |
| `inferred` | Derived from adjacent evidence in this project by a stated chain of reasoning | Design against it only with a reversible choice, and record the reopen trigger |
| `assumed` | No project evidence; taken from a comparable domain or from first principles | Not lock an irreversible boundary on it; carry it as an open assumption |

Anything above `observed` names what would raise it a tier and who could supply
that. A brief whose rows are all `assumed` is valid when the domain is genuinely
greenfield, and it says so in its limitations rather than reading as evidence.

## Requirements-Brief Template

```markdown
# Requirements Brief — {scope}

**Revision**: {n}   **Sources mined**: {paths, systems, documents}
**Prepared for**: `design/architect` (next stage per pipelines.yaml)

## Actors and jobs

| Actor | Job to be done | Success looks like | Frequency / volume |
| ----- | -------------- | ------------------ | ------------------ |

## Requirements

| # | Requirement | Source | Confidence | Affects | Open assumption |
| - | ----------- | ------ | ---------- | ------- | --------------- |

## Constraints

| # | Constraint | Kind | Source | Confidence | Affects |
| - | ---------- | ---- | ------ | ---------- | ------- |

{kind: regulatory, contractual, operational, technical, or organisational}

## Non-functional targets

| Target | Number | Source | Confidence | Why this number |
| ------ | ------ | ------ | ---------- | --------------- |

## Non-goals

- {what this scope deliberately excludes, and the trigger that would reopen it}

## Prior art and comparable flows

| Source | What it shows | Why it transfers (or does not) |
| ------ | ------------- | ------------------------------ |

## Conflicts preserved

| Conflict | Position A (source, confidence) | Position B (source, confidence) | Who decides |
| -------- | ------------------------------- | ------------------------------- | ----------- |

## Open questions

| Question | Blocks | Owner | Latest safe decision point |
| -------- | ------ | ----- | -------------------------- |

## Limitations

- {unreachable sources, unusable artifacts, and every row left `assumed` because of them}
```

A non-functional target without a number is not a target; it is an aspiration, and
the architecture stage cannot design against it. Either get the number or record
the row as an open question naming who sets it.

## Evidence Rules

- A path beats a paraphrase. Quote the line or name the file; a summary of
  something unread is `assumed`, not `reported`.
- One row, one claim. A requirement joined by "and" hides two decisions with
  different confidence and different owners.
- Requirements state what must be true, not what to build. "Approvals are
  auditable" is a requirement; "add an audit table" is a design decision that
  belongs to `design/architect`.
- Preserve disagreement. Two sources that conflict become a Conflicts row with
  both confidences, never an average and never a silent pick.
- Anecdote is `reported` at best. Three users saying the same thing is three
  reports, not a measurement.
- Absence of evidence is recorded as absence, not as a negative finding.

## Decision Rules

- Prefer evidence that changes a design decision over trivia that only lengthens
  the document.
- Keep technology lock-in out of the brief unless an earlier approval already fixed
  it; naming a stack here pre-empts `design/architect`'s rationale table.
- Escalate when missing evidence is material to the next design boundary, rather
  than shipping a row that looks complete.
- Stop when every open question has an owner and a latest safe decision point.
  Research with no decision attached is not finished, it is unbounded.

## Acceptance Checklist

- Actors, their jobs, and the success measures are explicit.
- Every requirement and constraint row carries all five fields.
- Every confidence tier above `observed` names what would raise it and who could.
- Every non-functional target has a number, or an open question naming who sets it.
- Conflicts are preserved with both positions and a named decider.
- Non-goals are recorded with their reopen triggers.
- Limitations list every unreachable source and the rows it left `assumed`.
- Every open question has an owner and a latest safe decision point.
- The brief is consumable by `design/architect` without reinterpretation.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

The skills this workflow hands to and receives from are named in `../SKILL.md` § Collaboration Surface. What this workflow adds:

- `design/planner` inherits this evidence through the architecture, not directly.
