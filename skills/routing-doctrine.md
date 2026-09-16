# Entry Routing Doctrine

Binding rule for how a request enters the Supreme Team catalog. This file is
canonical for one question only: which skill a turn lands on, and whether that
skill may start work or must hand off first. It owns the precedence order, the
routing class of every skill in the catalog, the Tier 0 fast path's eligibility
rules, the active-handoff loop guard, and the session pin.

It is not canonical for what a pipeline does once entered
([pipelines.yaml](pipelines.yaml)), for gate boundaries or evidence
([gates.yaml](gates.yaml)), for the blast-radius tier scale clause 1 selects
from ([execution-contract.md](execution-contract.md)), or for who may write
which path ([save-ownership.yaml](save-ownership.yaml)).

`admiral` is the primary entry orchestrator: the single front door for the
delivery lifecycle, so one intake, one persisted run, and one cross-stage
gatekeeper govern the whole pipeline. The catalog is description-routed, so
without this rule a request like "design this system" or "investigate this bug"
would land on a sub-orchestrator and skip intake, persistence, and gating.

## Contents

- [Enforcement status](#enforcement-status)
- [Precedence](#precedence)
- [Routing classes](#routing-classes)
- [Tier 0 fast path](#tier-0-fast-path)
- [Front-door scope](#front-door-scope)
- [The active-handoff check (loop guard)](#the-active-handoff-check-loop-guard)
- [Session pin](#session-pin)
- [Deterministic reinforcement](#deterministic-reinforcement)
- [Failure paths](#failure-paths)

## Enforcement status

The structure this file declares — which class a skill is in, that the
classes cover the roster, that each skill's own text agrees with its class —
is machine-checked. The decisions it asks for at runtime — which precedence
rule a turn falls under, whether a task is Tier 0, whether a skill actually
ran its active-handoff check — are judgement, and a reader who assumes
otherwise will trust a routing decision no script ever validated. The table
states which is which.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| A routing reminder is injected on a fresh turn with no active run, and suppressed for an explicit slash command | machine-checked where the hook is registered | `skills/harness/hooks/user_prompt_submit.py` |
| Whether a saved run is active, coherent, and fresh (the input the pin precedence rule reads) | machine-checked | `skills/harness/hooks/_saves.py`, through `has_active_run` |
| A pinned run's lock is held, fresh, and single-owner | machine-checked | `skills/harness/hooks/save_run.py`, the only writer of the run record |
| Every skill named in the tables below exists | machine-checked | `skills/validation/test_trigger_routing.py`, through `RoutingClassTableTests.test_every_name_in_the_table_exists`, which resolves every backticked name in the routing-class table to a SKILL.md on disk |
| The routing-class table agrees with the roles in [team-manifest.yaml](team-manifest.yaml) | machine-checked | `skills/validation/test_trigger_routing.py`, through `RoutingClassTableTests` — see the note below |
| Every internal specialist states how it is entered, and no standalone tool claims it must hand off first | machine-checked | `skills/validation/test_trigger_routing.py`, through `EntryRoutingConsistencyTests` |
| Which precedence rule a given turn falls under | judgement | nothing |
| Tier 0 eligibility for a given task | judgement | nothing |
| Whether a skill ran its active-handoff check before working | judgement | nothing; each skill states the check in its own prose |
| Front-door scope: that a lifecycle request actually entered through `admiral` | judgement | nothing; the hook advises and never blocks |

**Closed gap.** `skills/validation/test_trigger_routing.py` reads the
routing-class table below and compares it against `pipeline_owners`,
`phase_leads`, `phase_gatekeepers`, `cross_stage_gatekeeper`, and `front_door`
in [team-manifest.yaml](team-manifest.yaml). A pipeline owner filed as an
internal specialist is exactly the error this table is meant to prevent, and the
last one was found and corrected by hand, which is why the comparator exists.
The table is written to be mechanically comparable — every entry is a skill
`name`, grouped by the manifest role or list key it is declared under — and
`RoutingClassTableTests` asserts three things about it: the rows partition the
roster with no skill in two rows and none missing, every name resolves to a
skill on disk, and each name is filed under a role it actually holds.

One thing it deliberately does not assert. A row may annotate a grouping list
rather than a routing role — `qa-only` is annotated `testing` — and a grouping
is not a partition: `testing` also holds `qa`, filed here under
`pipeline_owners`, and `benchmark`, filed under the standalone glob with no
annotation at all. [team-manifest.yaml](team-manifest.yaml) states under
`authority.grouping` that only the union of the groups is checked, so requiring
a grouping to be covered row by row would fail on a correct table. The five
routing roles are checked for coverage; the grouping lists are not.

## Precedence

Resolve each new user turn in this order:

1. Explicit slash command, or an explicit request for a standalone tool.
2. Active `admiral` session pin with a valid run lock.
3. Eligible minor task through the Tier 0 fast path below.
4. Fresh delivery-lifecycle request through `admiral`.
5. Ordinary conversation outside the delivery lifecycle.

There is no bypass keyword. Standalone tools stay out of routing scope, not
through an opt-out.

**Host registration.** Claude Code discovers skills at
`.claude/skills/<name>/SKILL.md`, one level deep, so where a skill sits decides
whether the user can name it. The catalog's layout follows its routing classes:
of its 52 skills, the 21 a user may reach directly sit at the catalog root, and
the 31 internal specialists stay nested one level below, where the loader does
not offer them. That is the intended reading of "reached only through the owning
sub-orchestrator" expressed in the filesystem rather than only in prose.

Nesting costs those specialists nothing, because delegation never used the skill
loader. `admiral` holds `Read`, `Grep` and `Glob` and no `Skill` tool: its
delegation surface names `build/build-management` and it reads that file. A
specialist is reachable because its path resolves, not because the host
registered it.

Relative pointers move with the skill. A skill at the catalog root is one
level from shared doctrine like gates.yaml; a nested one is two, and its
pointers carry the extra step.
[Install.md](../Install.md) warns that a flattened tree is a broken tree, and
that is exactly this: the danger is moving a skill without rebasing its
pointers, not the depth itself.

Measured with `validation/run_eval.py --registration`, which installs the tree
into a scratch project and diffs the host's reported skill list against a
control run with no catalog installed — the control matters because the host
ships skills of its own, and at least one name collides.

**Tie-break when two rules both apply.** Rule 1 and rule 2 can match the same
turn: an active pinned run exists *and* the user explicitly asks for a
standalone tool or types a slash command. The listed order holds — the explicit
request wins, because an explicit instruction is the strongest available signal
of intent and a standalone tool changes no run state. Three conditions bound
that win:

- The run stays pinned. The tool runs beside the run, not instead of it, and the
  pin is not released ([Session pin](#session-pin)).
- The tool may not write any path the pinned run owns, and may not mutate
  durable Taste. A request that would do either is not a standalone-tool request
  and resolves under rule 2.
- The tool's result is reported back into the run as an input, not as a
  substitute for the evidence the pending gate requires.

When the explicit request names a skill that is in scope rather than standalone,
rule 2 governs and the request is routed to the active run's owner. When the
request is ambiguous about which of the two it is, resolve it by asking rather
than by guessing; a wrong guess here either forks a run or silently swallows an
explicit instruction, and both are worse than one question.

## Routing classes

These classes say how a skill is reached, not how much a run can break. They are
unrelated to the numbered Tier 0-3 blast-radius scale in
[execution-contract.md](execution-contract.md): no routing class carries a
number, and no blast-radius tier names a skill.

Names below are the bare skill `name` values recorded in
[team-manifest.yaml](team-manifest.yaml), with the directory given where it
disambiguates. Every skill in the catalog falls in exactly one row.

| Routing class | Skills | Entry behavior |
| --- | --- | --- |
| Entry orchestrator | `admiral` (`front_door`) | The front door. Lifecycle work initiates here. |
| Pipeline owners (must defer) | `commander`, `build-management`, `code-chief` (`phase_leads`); `cso`, `investigate`, `redesign`, `skill-maker`, `taste` (`pipeline_owners`) | Components of the Admiral pipeline. Reached without an active handoff, they hand off to `admiral` first. |
| Dual-mode entry | `qa` and `ship` (`pipeline_owners`); `qa-only` (`testing`) | Invokable as tools **and** reachable inside a gated pipeline; how they were reached decides which is running. All three sit at the catalog root, so the host registers them by name. |
| Gatekeepers (must defer) | `gatekeeper-admiral` (`cross_stage_gatekeeper`); `gatekeeper-design`, `gatekeeper-build`, `gatekeeper-code` (`phase_gatekeepers`) | Reached only by a submitting owner presenting a package at the boundary they validate. Never a front door. |
| Session memory | `session-memory` | A component of the Admiral pipeline, engaged by `admiral` at its declared checkpoints; it hands off to `admiral` when reached cold. |
| Internal specialists | every skill under `design/`, `build/`, `review/` not named in a row above; `taste/taste-review`; `skill-maker/skill-creator` and `skill-maker/skill-reviewer` | Reached only through the owning sub-orchestrator. |
| Standalone tools | `careful`, `freeze`, `guard`, `unfreeze`, `browse`, `open-browser`, `setup-browser-cookies`, `pair-agent`, `benchmark`, and `setup-deploy`, `land-and-deploy`, `document-release` | Out of routing scope, and invokable directly: each sits at the catalog root, so the host registers it by name. |

Two rows deliberately overlap a directory glob, and the named row wins:
`review/cso` owns the security pipeline and belongs to the pipeline-owner row,
not to internal specialists; `ship` owns the release
pipeline and belongs to the dual-mode row, not to the standalone glob.

"Standalone" means directly reachable without going through `admiral`; it does
not mean outside the pipelines. The dual-mode skills are the case where both are
true at once, and the entry path decides which is happening:

- An explicit standalone request ("run QA on this page", "check deploy
  readiness") runs the tool directly, with no intake, no saved run, and no gate.
- A cold lifecycle request for product testing or a release enters through
  `admiral` (front-door scope below) so it gets intake, persistence, and the
  gate.

`qa` owns the `qa` pipeline and is the only submitter at `qa-review`;
`qa-only` runs the report-only sweep inside that pipeline when fixes are not
authorized, and carries no boundary of its own. `ship` owns the `release`
pipeline and submits at `deploy-readiness`. Those boundaries and their owners
live in [pipelines.yaml](pipelines.yaml) and [gates.yaml](gates.yaml), which are
canonical for them; this file only decides how the skill was reached.

## Tier 0 fast path

Classify scope before starting a pipeline. Tier 0 covers small, local,
understood, reversible tasks with clear acceptance criteria and focused checks:
typo or link corrections, narrow documentation updates, small style adjustments,
local renames, or simple bug fixes whose cause and impact are already known.
File count alone does not determine eligibility. Broad refactors, unknown
failures, new features, architecture decisions, dependency changes, and
cross-system coordination require the ordinary Tier 1/2/3 route.

Tier 0 must not change authentication, authorization, secrets, sensitive-data
handling, trust boundaries, security controls, deployment settings, production
state, or destructive behavior. Security audits, hardening, and vulnerability
remediation remain Tier 3 regardless of diff size. A wording fix in security
documentation qualifies only if it changes no security policy or operational
instruction.

Act directly in the current task: inspect relevant context, make the smallest
sufficient change, and verify the affected behavior or artifact. Use targeted
tests for behavior changes, link checks for documentation, or rendered
inspection for visual changes. Finish with the Tier 0 rationale, the changes,
the checks actually performed with their results, and any remaining limitation.
[execution-contract.md](execution-contract.md) fixes that completion note's
shape.

For eligible work this fast path takes precedence over general lifecycle routing
and phase ceremony. No intake interview, delegation, readiness probe, new saved
run, session pin, phase manifest, gatekeeper verdict, or full security audit is
required. This is not a new pipeline or gate boundary. Existing freezes, guards,
owner permissions, and local conventions still apply.

An active session pin takes precedence: changes to its artifacts stay with the
owning phase and cannot use Tier 0 to bypass a pending gate or required
evidence. If scope grows, uncertainty appears, verification fails for an unknown
reason, or a security-sensitive concern emerges, stop the fast path and
reclassify to Tier 1, 2, or 3 before further work. Carry the diff and observed
checks into normal Admiral intake or the existing run. Never use Tier 0 to waive
a failed check.

Eligibility is judgement, and no script grades it. When eligibility is genuinely
unclear, the task is not Tier 0: the fast path exists for work whose smallness
is obvious, so doubt is itself disqualifying.

## Front-door scope

Route design, build, review, investigation, checkpoint, resume, gate validation,
security engagements, product QA, skill and team creation, release, and
deployment work through `admiral`. A skill reached cold checks for a
`### Save Context` handoff or an active pinned run; without one, it routes
lifecycle work to `admiral` before acting.

Dedicated security engagements (audit, threat model, hardening, vulnerability
remediation) run the `security` pipeline under `cso`, gated at `security-review`.
Inside a delivery run, `security-builder` owns the recurring checkpoints
(`security_seed` at design, `security_evidence` at build) rather than forking a
parallel lifecycle.

Investigation of an unknown failure mechanism runs the `investigation` pipeline
under `investigate`, gated at `investigation-review`; its bounded fix path
returns to the owning phase rather than becoming a build of its own.

Product testing runs the `qa` pipeline under `qa`, gated at `qa-review`. A
report-only run stays under `qa`, which may execute the sweep through `qa-only`
while remaining the only `qa-review` submitter. Browser tooling is engaged
inside that pipeline, never as a parallel lifecycle.

Frontend and UI work stays inside the design and review pipelines: `architect`
owns the design system per [design-doctrine.md](design-doctrine.md), and
`design-qa` and `frontier` own its review evidence. There is no separate
frontend pipeline. [Taste](taste-doctrine.md) is a canonical semantic input for
user-authored or explicitly confirmed presentation and interaction preferences.
Consuming that input creates no route, pipeline, gate, or bypass of Admiral
precedence: a design or review phase reads the resolved profile and continues in
the pipeline it is already running. Mutating Taste is the separate case set out
below, and that case does run a pipeline and close at a gate.

A redesign of an existing user-facing surface (a new look, alternative design
directions, a design-system exploration) runs the `redesign` pipeline under
`design/redesign`, gated at `redesign-review`: `design-mapper` records the
current design as a stable-id inventory, `taste` runs a project taste
grilling, `architect` writes four directions, `prototyper` builds four living
single-page prototypes with component libraries at functional parity, and the
chosen variant enters the design pipeline as its design-system input. A
redesign never changes application source.

Mutation is the exception to the consumption rule above. Explicit preference
lifecycle requests run the `taste` pipeline under `taste` and close at
`taste-review`. Triggers include “remember that I prefer…”, “save this
style globally”, “only use this preference in this project”, “show my effective
taste”, “promote this project preference”, and “forget/revoke this preference”.
A direct standalone utility never mutates Taste unless the request explicitly
invokes preference management. Ordinary application design consumes the resolved
Taste handoff without opening a mutation pipeline. Scope-changing and destructive
actions require confirmation; promotion to global scope, global reset, bulk
import, and bulk revocation must never be inferred from casual feedback.

## The active-handoff check (loop guard)

Every in-scope skill performs this check before doing work. It is also the guard
that keeps Admiral's own delegations from bouncing back.

An active Admiral handoff is present when any of these is true:

- the delegation prompt contains a `### Save Context` block, or
- an active run lock with `session_pin: true` exists under `skillset-saves/`, or
- the invocation explicitly frames this skill as the owning sub-orchestrator for
  a named boundary.

Handoff present: proceed; the skill is running inside an Admiral run. No handoff on a
cold lifecycle request: start `admiral` first, let it run intake, persistence,
and gating, then accept the delegation back. Admiral's own delegations always
carry the handoff signal, so they pass immediately.

The check is stated in each in-scope skill's own prose and applied by the skill
itself. Nothing verifies that a skill ran it, so it is judgement in the same
sense the rest of this file is: the loop guard works because every in-scope
skill carries it, not because a validator enforces it.

## Session pin

Set `session_pin: true` while a coherent run is active or gate-pending. Release
it on `RUN_COMPLETE`, the explicit command `release admiral` or `/exit-admiral`,
or verified lock staleness. Append every release to the audit trail.

The pin lives in the run lock, whose only writer is
`harness/hooks/save_run.py`. Whether a lock is held, fresh, coherent, and
single-owner is therefore a mechanical fact, not a claim: `save_run.py create`
refuses while another run holds the pin, and `_saves.py` classifies the saved
state that precedence rule 2 reads. What remains judgement is whether a given
turn belongs to the pinned run at all.

## Deterministic reinforcement

`harness/hooks/user_prompt_submit.py` fires on every fresh user prompt and
injects a routing reminder pointing at `admiral` when no active run is detected.
It is advisory, stdlib only, and fail-open; it cannot own the host loop (see
[harness-doctrine.md](harness-doctrine.md)). It stays silent for explicit slash
commands and reinforces the session pin when a run is in progress. When it stays
silent, the target skill's own active-handoff check above is the guard that
applies instead.

Because this layer works only once the hook is registered, Admiral verifies
registration at intake with `harness/hooks/verify_registration.py` and reports
readiness with `harness/hooks/check_readiness.py`. When a hook is missing, the
verifier emits a `REGISTER_PROMPT` and Admiral offers the previewable repair
(`harness/hooks/repair_registration.py --host <host> --scope project`, then
`--apply` only with the owner's approval). Until the prompt-submit hook is
registered, entry routing falls back to this doctrine plus the skill
descriptions and per-skill entry checks.

The hook never blocks and never routes. It injects context, so at best it raises
the odds that a fresh turn is routed correctly. Treating its presence as proof
that routing happened would be exactly the overstatement this doctrine's
enforcement table exists to prevent.

## Failure paths

- **The prompt-submit hook is not registered, or the host has no hook
  lifecycle.** Routing degrades to advisory: this doctrine plus each skill's
  description and its own active-handoff check. Say so once when it is
  discovered rather than silently proceeding, and do not record a routing check
  as performed.
- **`skillset-saves/` is unreadable, or the run lock is malformed.** Precedence
  rule 2 cannot be evaluated, so it does not apply. Do not infer a pin from a
  damaged lock and do not start a second run on top of an ambiguous one: treat
  the state as unresolved, report it, and let `admiral` classify it
  (active / inactive / orphaned / missing / unreadable / conflict) before any
  new work.
- **A lock exists but is stale.** Staleness must be verified, not assumed from
  age alone where a heartbeat is available. A verified-stale lock may be
  released, and the release is appended to the audit trail.
- **Two precedence rules both match.** Apply the tie-break in
  [Precedence](#precedence). If the tie-break's three conditions cannot all be
  met, the turn is not a standalone-tool request and belongs to the active run.
- **A skill appears in no row of the routing-class table.** That is a defect in
  this file, not a licence to route freely. Treat the skill as in-scope and
  route through `admiral` until the table is corrected, because the conservative
  reading preserves intake, persistence, and gating.
- **The routing-class table and [team-manifest.yaml](team-manifest.yaml)
  disagree.** The manifest wins: it is the machine-readable roster the
  comparators already read, and this table is prose derived from it. Correct
  this file.
- **A standalone tool is asked to do lifecycle work.** It declines the lifecycle
  scope and names `admiral`, rather than quietly widening itself. Being out of
  routing scope is a statement about how the tool is reached, not permission to
  run a pipeline.
- **Tier 0 verification fails for an unknown reason.** Stop the fast path,
  reclassify, and carry the diff and the observed failure into intake. A failed
  check is never waived by the tier that produced it.
