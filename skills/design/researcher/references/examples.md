# Example Invocations

Three delegations and the actual brief text returned. The five-field row, the
confidence tiers, and the document template are in `workflow.md`.

## Contents

1. Example 1 — "research this problem space"
2. Example 2 — "analyze stakeholder needs"
3. Example 3 — "gather requirement evidence" for a greenfield domain

## Example 1 — "research this problem space"

A field-service scheduling product. Returned: actors, then the sourced rows.
Verbatim from the brief:

```markdown
## Actors and jobs

| Actor | Job to be done | Success looks like | Frequency / volume |
| ----- | -------------- | ------------------ | ------------------ |
| Dispatcher | Fill tomorrow's schedule without stranding a technician | Every job has an assignee by 16:00 | daily, ~120 jobs |
| Field technician | Know the next job and record what happened | Job closed with evidence before leaving site | 6–9 jobs/day/tech |
| Operations manager | See which jobs are at risk today | Slipping jobs surfaced before the customer calls | continuous |
| Finance reviewer | Confirm billable work actually happened | Every invoice line traces to captured evidence | monthly |

## Requirements

| # | Requirement | Source | Confidence | Affects | Open assumption |
| - | ----------- | ------ | ---------- | ------- | --------------- |
| R1 | A technician can record job evidence with no connectivity and sync later | 41 of 220 support tickets cite "lost photos" (`support/export-2026-08.csv:tickets[status=closed]`) | observed | Data-flow boundary: local store plus sync, not a live write path | Whether sync conflicts can be last-write-wins, or need per-field merge |
| R2 | Schedule changes after 16:00 notify the affected technician | Named: operations manager, intake interview 2026-09-02 | reported | Notification interface and its delivery guarantee | Whether SMS is required or push suffices; no device inventory available |
| R3 | An invoice line cannot exist without captured evidence | Finance policy doc §4.2 (`docs/finance/billing-policy.md:88`) | observed | Invariant: evidence write inside the job-close transaction | None |
| R4 | Dispatchers reassign jobs faster than the current 4-click path | Inferred from ticket volume plus the current UI's flow | inferred | UI/UX handoff: reassignment interaction | No timing data exists; would need a session recording to reach `observed` |

## Non-functional targets

| Target | Number | Source | Confidence | Why this number |
| ------ | ------ | ------ | ---------- | --------------- |
| Offline evidence retention | 72 hours | Ops manager, confirmed against the longest observed outage in `ops/incidents-2026.md` | reported | Covers a weekend outage without data loss |
| Schedule load | 500 jobs/day peak | `scheduler_jobs` table, max daily count over 18 months | observed | Measured peak plus the stated 2x growth plan |

## Open questions

| Question | Blocks | Owner | Latest safe decision point |
| -------- | ------ | ----- | -------------------------- |
| Sync conflict policy (last-write-wins vs per-field merge) | R1's data-flow boundary | product owner | before the architecture fixes the offline store |
| SMS vs push for R2 | notification interface and its vendor dependency | ops manager | before the interface contract is written |
```

**Returned to** `design/commander`. `design/architect` consumes it next — the
stage `../../../pipelines.yaml` places after research; `design/planner` consumes
the architecture that follows, not this brief directly.

## Example 2 — "analyze stakeholder needs"

Two stakeholders want incompatible flows. The conflict is preserved, not resolved.

```markdown
## Conflicts preserved

| Conflict | Position A | Position B | Who decides |
| -------- | ---------- | ---------- | ----------- |
| Account setup path | Sales: one-click setup, no approval step. Source: named, sales lead, intake 2026-09-03. Confidence: reported | Operations: every new account passes a reviewed approval. Source: `docs/ops/onboarding-runbook.md:22` plus an audit finding from 2026-Q1. Confidence: observed | Product owner, before the architecture fixes the onboarding flow |

**Research conclusion**: the positions are not a preference clash. Position B is
backed by an audit finding with a compliance consequence; position A is backed by a
conversion concern with no measurement attached. Both can hold if the fast path
exists and the approval checkpoint is explicit rather than removed — but that is a
design proposal, and the decision belongs to the product owner before
`design/architect` locks the flow.

**Not done here**: choosing. Collapsing these into one requirement would hand the
architect a boundary neither stakeholder agreed to.
```

## Example 3 — "gather requirement evidence" for a greenfield domain

A regulated market the team has never built in: no existing system, no usage data,
no comparable internal flow. The brief says so.

```markdown
## Limitations

- **No prior art in this project.** No existing system, dataset, ticket history, or
  comparable flow. Every requirement below is `assumed` unless its source names an
  external document.
- **No usage data exists.** Volume and frequency figures are planning estimates
  from the product owner, not measurements.

## Requirements

| # | Requirement | Source | Confidence | Affects | Open assumption |
| - | ----------- | ------ | ---------- | ------- | --------------- |
| R1 | Delegated approval must not expose full billing access | Regulation text §7 (`docs/regulatory/dir-2024-118.md:412`) | observed | Authorization model and the trust boundary around billing | Whether "full access" includes read-only totals; the text is ambiguous |
| R2 | Approval decisions are retained for seven years | Regulation text §9 (same file, line 508) | observed | Data retention and the audit store's lifecycle | None |
| R3 | Reviewers expect a queue rather than per-item notification | First principles plus two external case studies | assumed | UI/UX handoff: reviewer route and its primary action | Raise to `reported` with one interview with a practising reviewer — the cheapest experiment available |

**Told to `design/architect`**: R3 is the only row shaping the reviewer interface,
and it is `assumed`. Keep that surface reversible — a queue and a notification path
should not be a locked boundary decision at this stage. R1 and R2 are `observed`
from the regulation and can carry irreversible structure.
```

The brief is short, and that is the finding. Padding it with analogies from
adjacent domains would have produced a document that reads like evidence and is
not.
