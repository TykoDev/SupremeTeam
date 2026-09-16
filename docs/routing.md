# Entry Routing

Skill catalogs are description-routed: the host assistant reads skill
descriptions and picks whichever one sounds closest to your request.

That works fine until it does not. "Design this system" sounds exactly like the
`commander` skill, so the host calls `commander`, and the run skips intake,
persistence, and every gate. You get a design, and nothing that produced it was
recorded.

[`skills/routing-doctrine.md`](../skills/routing-doctrine.md) closes that gap by
making `admiral` the single front door.

## Precedence

Every new turn resolves in this order:

1. **An explicit slash command, or an explicit standalone tool request.** Both are
   deterministic host routing and are honored. If a slash command targets an
   in-scope skill, that skill still runs its active-handoff check.
2. **An active session pin.** A run with a held lock and `session_pin: true` owns
   the input. It goes to the active sub-orchestrator, and no parallel skill forks
   off.
3. **The Tier 0 fast path.** Eligible minor work runs directly.
4. **A fresh lifecycle request.** Everything else in scope starts at `admiral`.
5. **Ordinary conversation**, which is none of the above.

There is no bypass keyword. Standalone tools stay reachable because they are out
of scope, not because there is an escape hatch.

## Tier 0: small things stay small

Tier 0 is for work that is local, understood, reversible, and has obvious
acceptance criteria. Typo and link fixes. Narrow doc updates. Small style
adjustments. Local renames. A bug whose cause and blast radius you already know.

File count does not decide it. A one-line change to an auth check is not Tier 0.

Eligible work runs directly: inspect, make the smallest sufficient change, verify
the affected behavior, and finish with the reasoning, the diff, the checks
actually performed with their results, and anything still unresolved. No
interview, no delegation, no saved run, no session pin, no gate package, no
verdict.

Tier 0 never touches authentication, authorization, secrets, sensitive data, trust
boundaries, security controls, deployment settings, production state, or anything
destructive. Security audits, hardening, and vulnerability remediation stay Tier 3
regardless of how small the diff looks.

An active session pin outranks it. Artifacts belonging to a pinned run stay with
their phase and cannot use Tier 0 to slip past a pending gate.

If scope grows, uncertainty shows up, or verification fails for a reason you do
not understand: stop, reclassify, and carry the diff and the observed checks into
normal intake. Tier 0 never waives a failed check.

Broad refactors, unknown failures, new features, architecture decisions,
dependency changes, and anything crossing systems take the ordinary route.

## Who can be called, and how

| Tier | Skills | How they are reached |
|---|---|---|
| Entry orchestrator | `admiral` | The front door. Lifecycle work starts here |
| In-scope, defers when cold | `design/commander`, `design/redesign`, `build/build-management`, `review/code-chief`, `skill-maker`, `investigate`, `taste`, `session-memory`, `gatekeeper-admiral` | Components of the Admiral pipeline. Reached without an active handoff, they hand off to `admiral` first, then take the delegation back |
| Internal specialists | every skill under `design/`, `build/`, `review/` not listed above | Through their owning sub-orchestrator. Not a user entry point |
| Standalone tools | `safety-guardrails/*`, `browser-automation/*`, `release-and-deployment/*`, `testing-and-qa/*` | Out of routing scope. Call them directly whenever |

"Standalone" means directly reachable without going through admiral. It does not
mean unused by the pipelines. `qa` and `ship` are both directly invokable **and**
own a pipeline when admiral delegates to them; which one is happening is decided
by how they were reached, not by the skill.

## Where requests go

| You want | It goes to |
|---|---|
| Design, build, and review a change end to end | `admiral`, then `commander`, `build-management`, `code-chief` in sequence |
| Design only, or to continue from an approved design | `admiral` picks the earliest incomplete boundary |
| To redesign an existing UI and compare alternatives | `admiral` delegates `redesign`, gated at `redesign-review`; the chosen variant then enters `commander` |
| A security audit, threat model, hardening, or remediation | `admiral` delegates `cso`, gated at `security-review` |
| To know why something is failing | `admiral` delegates `investigate`, gated at `investigation-review`; the bounded fix path returns to the owning phase |
| Product testing with recorded evidence | `admiral` delegates `qa`, or `qa-only` for a report without fixes, gated at `qa-review` |
| A new skill or a coordinated team | `skill-maker`, gated at `skill-maker-to-delivery` |
| To prepare and run a release | `ship`, gated at `deploy-readiness`, then `land-and-deploy` after a human decision |
| To checkpoint or resume | `session-memory` plus the earliest incomplete owner |

Frontend and UI work stays inside the design and review pipelines. `architect`
owns the design system; `design-qa` and `frontier` own its review evidence. There
is no separate frontend pipeline.

## The loop guard

Every in-scope skill runs an active-handoff check before doing anything. It is
also what stops Admiral's own delegations from bouncing straight back to Admiral.

A handoff is present when any of these is true:

- the prompt carries a `### Save Context` block, or
- an active run lock with `session_pin: true` exists under `skillset-saves/`, or
- the invocation explicitly frames the skill as the owning sub-orchestrator for a
  named boundary.

With a handoff, get to work. Without one, on a cold lifecycle request, start
`admiral` first and accept the delegation back. Admiral's delegations always carry
the signal, so a delegated call never loops.

## Session pinning

While a run is active or gate-pending with the lock held, `session_pin: true`.
Every later message in the session belongs to that run, even when you never say
"admiral", and gets routed to the active sub-orchestrator.

The pin clears on `RUN_COMPLETE`, on `release admiral` or `/exit-admiral`, or when
the lock is verified stale. Every release is appended to the audit trail.

## Making it deterministic

`skills/harness/hooks/user_prompt_submit.py` fires on every fresh prompt and
injects an advisory reminder: point at `admiral` when no run is active, reinforce
the pin when one is. Stdlib only, fails open, silent on slash commands.
Registration is opt-in.

Admiral checks registration at intake with `verify_registration.py` and reports
capabilities with `check_readiness.py`. Until the prompt-submit hook is registered,
routing falls back to this doctrine plus skill descriptions and the per-skill
handoff checks. See [harness.md](harness.md).

## Why bother

Starting at `admiral` buys every run one grilled intake, one persisted run with a
lock and a session pin, an MCP freshness check, execution-mode re-probing, and a
gate verdict at every boundary.

A request that enters through a sub-orchestrator gets none of it. That is the
failure this doctrine exists to prevent.
