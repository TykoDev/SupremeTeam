# Entry Routing Doctrine

Binding rule for how a request enters the Supreme Team catalog. `admiral` is the
primary entry orchestrator: the single front door for the delivery lifecycle, so
one intake, one persisted run, and one cross-stage gatekeeper govern the whole
pipeline. The catalog is description-routed, so without this rule a request like
"design this system" or "investigate this bug" would land on a sub-orchestrator
and skip intake, persistence, and gating.

## Precedence

Resolve each new user turn in this order:

1. Explicit slash command, or an explicit request for a standalone Tier-4 tool.
2. Active `admiral` session pin with a valid run lock.
3. Eligible minor task through the Tier 0 fast path below.
4. Fresh delivery-lifecycle request through `admiral`.
5. Ordinary conversation outside the delivery lifecycle.

There is no bypass keyword. Standalone tools stay reachable because they are out
of scope, not through an opt-out.

## Skill tiers

| Tier | Skills | Entry behavior |
| --- | --- | --- |
| Entry orchestrator | `admiral` | The front door. Lifecycle work initiates here. |
| In-scope (must defer) | `design/commander`, `build/build-management`, `review/code-chief`, `skill-maker`, `investigate`, `taste`, `session-memory`, `gatekeeper-admiral` | Components of the Admiral pipeline. Reached without an active handoff, they hand off to `admiral` first. |
| Internal specialists | every skill under `design/`, `build/`, `review/` not listed above | Reached only through the owning sub-orchestrator. |
| Standalone tools | `safety-guardrails/*`, `browser-automation/*`, `release-and-deployment/*`, `testing-and-qa/*` | Out of routing scope; invokable directly at any time. |

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

Product testing runs the `qa` pipeline under `qa` (or `qa-only` for a
report-only run), gated at `qa-review`. Browser tooling is engaged inside that
pipeline, never as a parallel lifecycle.

Frontend and UI work stays inside the design and review pipelines: `architect`
owns the design system per [design-doctrine.md](design-doctrine.md), and
`design-qa` and `frontier` own its review evidence. There is no separate
frontend pipeline.

Explicit preference lifecycle requests run the `taste` pipeline under Taste and
close at `taste-review`. Triggers include “remember that I prefer…”, “save this
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

Handoff present: proceed; you are running inside an Admiral run. No handoff on a
cold lifecycle request: start `admiral` first, let it run intake, persistence,
and gating, then accept the delegation back. Admiral's own delegations always
carry the handoff signal, so they pass immediately.

## Session pin

Set `session_pin: true` while a coherent run is active or gate-pending. Release
it on `RUN_COMPLETE`, the explicit command `release admiral` or `/exit-admiral`,
or verified lock staleness. Append every release to the audit trail.

## Deterministic reinforcement

`harness/hooks/user_prompt_submit.py` fires on every fresh user prompt and
injects a routing reminder pointing at `admiral` when no active run is detected.
It is advisory, stdlib only, and fail-open; it cannot own the host loop (see
[harness-doctrine.md](harness-doctrine.md)). It stays silent for explicit slash
commands and reinforces the session pin when a run is in progress.

Because this layer works only once the hook is registered, Admiral verifies
registration at intake with `harness/hooks/verify_registration.py` and reports
readiness with `harness/hooks/check_readiness.py`. When a hook is missing, the
verifier emits a `REGISTER_PROMPT` and Admiral offers the previewable repair
(`harness/hooks/repair_registration.py --host <host> --scope project`, then
`--apply` only with the owner's approval). Until the prompt-submit hook is
registered, entry routing falls back to this doctrine plus the skill
descriptions and per-skill entry checks.
