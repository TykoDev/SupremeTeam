# Entry Routing

Skill catalogs are description-routed: the host picks the skill whose
description sounds closest. "Investigate this bug" lands on `investigate` and
skips intake, persistence and every gate. [`routing-doctrine.md`](../skills/routing-doctrine.md)
closes that gap: `admiral` is the single front door.

## Precedence

1. An explicit slash command or standalone tool request.
2. An active session pin with a held lock.
3. The Tier 0 fast path.
4. A fresh lifecycle request, through `admiral`.
5. Ordinary conversation.

There is no bypass keyword.

## Tier 0

Local, understood, reversible work with obvious acceptance: typo and link fixes,
narrow doc updates, small style changes, local renames, a bug whose cause and
blast radius are known. File count does not decide it. It runs directly, with no
interview, run, pin, package or verdict, and ends with a brief note: the Tier 0
rationale, the changes, the checks run with their results, and anything
unresolved. It never touches authentication, authorization, secrets,
sensitive data, trust boundaries, security controls, deployment or production
state, or anything destructive; security work is Tier 3 whatever its size. An
active pin outranks it. If scope grows or a check fails for an unknown reason,
stop and reclassify into normal intake.

## Routing classes

| Routing class | Skills | How they are reached |
|---|---|---|
| Entry orchestrator | `admiral` | The front door |
| Pipeline owners (must defer) | `design/commander`, `build/build-management`, `review/code-chief`, `review/cso`, `investigate`, `design/redesign`, `skill-maker`, `taste` | Reached cold, they hand off to `admiral` first |
| Dual-mode entry | `qa`, `qa-only`, `ship` | Tools when called by name; inside their gated pipeline when reached through `admiral` |
| Gatekeepers (must defer) | `gatekeeper-admiral`, `design/gatekeeper-design`, `build/gatekeeper-build`, `review/gatekeeper-code` | Only by a submitting owner at the boundary they validate |
| Session memory | `session-memory` | Engaged by `admiral` at its checkpoints |
| Internal specialists | every skill under `design/`, `build/`, `review/` not named above; `taste/taste-review`; `skill-maker/skill-creator`; `skill-maker/skill-reviewer` | Through their owning sub-orchestrator |
| Standalone tools | `audit-improve`, `careful`, `freeze`, `guard`, `unfreeze`, `browse`, `open-browser`, `setup-browser-cookies`, `pair-agent`, `benchmark`, `setup-deploy`, `land-and-deploy`, `document-release` | Call them directly |

A host that scans one level deep registers the 22 skills at the install root by
name; the 31 nested ones are reached by path through the skill that delegates to
them.

## Where requests go

| You want | It goes to |
|---|---|
| Design, build and review end to end | `admiral`, then `commander`, `build-management`, `code-chief` |
| Design only, or continue from an approved design | `admiral`, at the earliest incomplete boundary |
| Redesign an existing UI | `admiral` delegates `redesign`; the chosen variant enters `commander` |
| Security audit, threat model, hardening | `admiral` delegates `cso` |
| Why something fails | `admiral` delegates `investigate`; the fix path returns to the owning phase |
| Product testing with evidence | `admiral` delegates `qa`; a report-only run stays under `qa`, which runs the sweep through `qa-only` |
| A new skill or team | `admiral` delegates `skill-maker` |
| A release | `admiral` delegates `ship`; `land-and-deploy` runs after `deploy-readiness` approves and a human go decision is recorded |
| Checkpoint or resume | `admiral` engages `session-memory`, then the earliest incomplete owner |

Frontend work stays inside design and review: `architect` owns the design system;
`design-qa` and `frontier` own its review evidence.

## The loop guard

Every in-scope skill checks for an active handoff before working: a
`### Save Context` block in the prompt, a coherent, fresh pinned run that
`save_run.py status` classifies as `active` or `orphaned` under
`skillset-saves/`, or an invocation that names it as the owning
sub-orchestrator for a boundary. With a handoff it works; without one, on a cold
lifecycle request, it starts `admiral` and accepts the delegation back.
Admiral's delegations always carry the signal, so nothing loops.

## Session pin

While a run is active or gate-pending with the lock held, every message belongs
to that run and routes to the active sub-orchestrator. The pin clears on
`RUN_COMPLETE`, on `release admiral` or `/exit-admiral`, or when the lock is
verified stale; every release is recorded by `save_run.py`.

## Enforcement

`user_prompt_submit.py` runs on every fresh prompt: it points at `admiral` with
no active run, reinforces the pin with one, and adds no routing reminder to an
explicit slash command. It is registered with the installer's `--register-hooks`;
until then routing is advisory, and `admiral` says so at intake ([harness.md](harness.md)).
