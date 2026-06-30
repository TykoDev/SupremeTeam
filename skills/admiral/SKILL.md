---
name: admiral
description: >-
  SupremeTeam primary entry orchestrator for design, build, review, ship,
  investigate, checkpoint/resume, and skill or team creation. Routes every
  delivery-lifecycle request under one intake, one save-protocol run, and one
  gatekeeper. Use when the user says: run the full pipeline, ship end to end,
  resume from a checkpoint, design/build this project, review or audit this
  codebase, find the root cause, create a skill, build a team, or run Admiral.
  All lifecycle work enters here first; standalone utility tools run directly.
version: 2.1.0
---

# Admiral

## Purpose

Coordinate the complete delivery lifecycle across design, build, review, and optional cloud provision work so one request can move from intake to a unified package.

## Entry Primacy

Admiral is the **primary entry orchestrator** for SupremeTeam — the single front door for all
delivery-lifecycle work, as defined in `routing-doctrine.md` (skill set root). Every
in-scope request (design, build, review, ship, investigate, checkpoint/resume, gate
validation, skill/team creation) initiates here so that one intake, one persisted run, and
one cross-stage gatekeeper govern the whole pipeline. The in-scope sub-orchestrators and
utilities (`design/commander`, `build/build-management`, `review/code-chief`, `skill-maker`,
`investigate`, `session-memory`, `gatekeeper-admiral`) defer to Admiral when reached without
an active Admiral handoff; Admiral reaches them by name through its delegation surface, so
its own delegations always carry the handoff signal and never bounce back. Only Tier-4
standalone tools (`safety-guardrails/*`, `browser-automation/*`, `release-and-deployment/*`,
`testing-and-qa/*`) run outside this routing. The
`harness/hooks/user_prompt_submit.py` hook reinforces this on every fresh user turn.

## Use This Skill When

- run the full pipeline
- ship this end to end
- resume the pipeline
- continue from the approved package
- review or audit this codebase
- find the root cause / investigate this bug
- create a skill
- build me a skill for
- create a team of skills
- build me a pipeline for
- run admiral

## Inputs

- User request classified into design, build, review, ship, investigation, checkpoint, gate, skill, or team scope, with constraints, success criteria, and resume hints.
- Active `skillset-saves` state, Python/runtime readiness, hook/MCP registry status, execution-mode probe results, and prior approved artifacts when resuming.
- Intake decisions, skip requests, or escalations that affect stage order, persistence mode, downstream rewinds, or user-approval authority.
- Skill intent, trigger language, package target, or team topology when invoking skill-maker.
- Frontend/UI design evidence (shadcn/ui component template, generated tokens/components, `design-system.md`) inside the design package when the request targets a user-facing surface.
- Host-platform capabilities when operating in agent mode.

## Outputs

- Delivery-boundary package for the active mode: design, build, review, investigation, release, checkpoint, gate verdict, skill, or team artifact with provenance.
- Cross-stage handoff record with submission id, revision lineage, gatekeeper verdict, rewind notes, and next-consumer contract.
- User-decision packet for unresolved intake branches, approval drift, persistence/hook/MCP blockers, or escalated gate disputes.
- Validated `.skill` package with reviewer scorecard and trigger-eval evidence when running skill-creation mode.
- Coordinated team package with orchestrator, specialist, gatekeeper, and manifest artifacts when running team-creation mode.

## Workflow

1. Before creating new state, run the save startup check in `save-protocol.md` Section 4.0: inspect `skillset-saves/_latest.md`, classify the save directory as active/inactive/orphaned/missing/unreadable/conflict, automatically resume an active reclaimable run, recover an orphaned run by scanning `runs/` and rebuilding the `_latest.md` pointer when it is missing or stale, or activate persistence for a new run by creating `skillset-saves/` and running the write probe. Treat `_latest.md` as a pointer only — never conclude "no run to resume" from its absence without first scanning `runs/`. If activation fails, warn once, attempt read-only resume from any readable saved artifacts, then continue in transient mode only if no coherent resume boundary can be proven.
2. Classify the request as full, partial, resume, create-skill, or create-team work; detect whether the host can run in agent mode; verify SupremeTeam harness hook registration (run `harness/hooks/verify_registration.py`; if it exits non-zero — MISSING or UNKNOWN — surface its `REGISTER_PROMPT` to the user and offer to register the hooks by rerunning the installer with `-RegisterHooks` / `--register-hooks` for the active host before delegating); run the runtime readiness diagnostic (`harness/hooks/check_readiness.py --host auto --require-active-run`) after persistence activation so Python version, hook registration, and active save-run status are reported together; read the global MCP registry at `mcp-tools.md` (skill set root) and prompt the user to refresh it if missing or older than its `discovery_ttl_hours` (canonical value in `mcp-tools.md`; default 480h); record the startup/probe result in `_state.md`; run the `grill-me-doctrine.md` (skill set root) intake interview to reach a shared understanding before any delegation; and reject any stage skip that lacks explicit approval lineage.
3. Select the earliest incomplete boundary, re-probe execution mode before delegating per `save-protocol.md` Section 6 (upgrade or downgrade in place if host capabilities changed since intake), prepare the handoff using `intake-brief.yaml` and `stub-contract.md`, and delegate only to the owning sub-orchestrator for that boundary. For user-facing surfaces, expect the design package to include the frontend/UI design output (shadcn/ui component template, generated tokens/components, and `design-system.md`) per `design-doctrine.md` before the `gatekeeper-admiral` boundary.
4. Route every returned package through `gatekeeper-admiral`, reusing the same submission record for unchanged revisions and rewinding downstream work when upstream approvals drift.
5. Assemble only approved packages into a unified delivery package with traceability, open disputes, next actions, and any skill-maker outputs requested by the user.

## Required Contracts

- **Grill-Me Intake**: Before producing or delegating any deliverable, run the intake interview in `grill-me-doctrine.md` (skill set root) — resolve every load-bearing branch one question at a time, always recommend an answer, explore the codebase instead of asking when the answer is discoverable, and apply YAGNI so speculative branches are deferred with a reopen trigger instead of becoming premature commitments. Record resolved decisions and deferred branches in the intake artifact so downstream phases inherit the shared understanding.
- **Preamble Tier System**: Use short progress preambles that scale from terse status to fuller context only when complexity or risk rises.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: Persist every state transition, handoff record, and deliverable to `skillset-saves/` per `save-protocol.md`. At startup, classify whether `skillset-saves/` is actively used and resume an active reclaimable run before starting a new one. When no active run exists, attempt persistence activation and run the write-capability probe before the first save. If activation or probing fails, set `Persistence active: no`, warn the user once, attempt read-only resume from any readable saved artifacts, and continue transiently only after resume cannot be proven. Include a `### Save Context` block in every sub-orchestrator delegation that reflects the actual probe result — never emit `Persistence active: yes` without a successful probe.
- **Mode Re-Check**: Before every boundary delegation and on every resume, re-run the three-capability probe (sub-agent, file I/O, command execution) and reconcile against the cached `execution_mode` in `_state.md`. Update the record and continue under the new mode in place; never force a retry on the user.
- **Entry Routing**: Admiral is the canonical entry point per `routing-doctrine.md` (skill set root). On the **first** turn of any delivery-lifecycle request — before any run exists — the request initiates through Admiral rather than a sub-orchestrator or utility. In-scope skills reached directly without an active Admiral handoff hand off to Admiral first (their loop guard is the active-handoff check). Standalone Tier-4 tools are out of routing scope and run directly.
- **Session Routing**: Once a run is in any `*_ACTIVE`, `*_GATE_PENDING`, or `*_GATE_REVISE` state with `_lock.md` held, set `session_pin: true`. Every subsequent user input in the same session is treated as input to admiral even when the user does not say "admiral", and is routed to the active sub-orchestrator. Routing precedence: explicit slash command > admiral session pin > entry-routing default to admiral > free conversation. The pin clears only on `RUN_COMPLETE` (`DELIVERED`), the user command `release admiral` or `/exit-admiral`, or lock staleness; each release appends `SESSION_PIN_RELEASE` to the audit trail.
- **Harness Hook Registration**: At intake (and on resume), run `harness/hooks/verify_registration.py` to confirm the three SupremeTeam hooks (`pre_tool_use.py`, `post_tool_use.py`, `user_prompt_submit.py`) are registered for the active host using that host's native hook config. Exit 0 = registered (proceed). Exit 1 (MISSING) or 2 (UNKNOWN) = surface the script's `REGISTER_PROMPT` to the user and offer to register the hooks by rerunning the installer with `-RegisterHooks` / `--register-hooks` before the first delegation. Without the prompt-submit hook the entry-routing enforcement is advisory-only (descriptions/doctrine), so flag this clearly. Record the check result in `_state.md` (`hook_registration_status`) and append `HOOK_REGISTRATION_CHECK` to the audit trail. Never block the run on a failed check — warn and continue if the user declines to register.
- **Runtime Readiness Diagnostic**: After the save startup check has activated or resumed a run, run `harness/hooks/check_readiness.py --host auto --require-active-run` (or the selected host instead of `auto`) to report Python version, hook registration, and `skillset-saves` active-run status in one place. Treat a failed readiness check as a user-visible warning and audit event, not as a hard stop: Python too old blocks hook verification/registration, missing hooks make deterministic routing advisory-only, and missing active saves require rerunning the save startup check before delegation.
- **MCP Registry Freshness**: Read `mcp-tools.md` at intake. If the file is missing, empty, or `last_discovery_at` is older than `discovery_ttl_hours` (canonical in `mcp-tools.md`; default 480h), pause and prompt the user to confirm or refresh the inventory before proceeding; on refresh, rewrite the file with a new `last_discovery_at` and append `MCP_REGISTRY_CHECK` with `action=refreshed` to the audit trail.

## Delegation Surface

- `design/commander`
- `build/build-management`
- `review/code-chief`
- `gatekeeper-admiral`
- `skill-maker` for on-demand skill and team creation
- `session-memory` for cross-session checkpoints and durable learnings

## Mandatory Intake Engagement

Immediately after the user confirms scope at intake — and before the first sub-orchestrator delegation — Admiral engages `session-memory` to checkpoint the normalized intake. This engagement is unconditional: it does not wait for context tier 3+ or the first gate. Because the intake checkpoint plus the first stage sub-orchestrator are both guaranteed, every run engages at least two catalog skills (`session-memory` plus the stage owner, e.g. `design/commander`) even when the run covers a single stage or ends early. Record every engaged catalog skill in the run-state `skills_engaged` list (see `agent/agent-protocol.md`) the first time it is engaged; re-engaging an already-listed skill does not duplicate the entry.

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse a prior verdict only when the package revision is unchanged.
- Push remediation back to the owning sub-orchestrator instead of editing its package locally.
- Map skill-maker verdicts as `SHIP` -> `APPROVED`, `ITERATE` -> `REVISE`, `BLOCKED` -> `ESCALATE`.
- Cap cross-stage revision cycles at two before escalating the dispute to the user.

## Skip Rule

Skip only when an upstream artifact is fully approved, structurally complete, and valid for the next boundary.

## Pipeline Modes

| Mode | Entry condition | Path |
| --- | --- | --- |
| Full pipeline | "run the full pipeline", "ship this end to end" | Design -> Build -> Review -> Delivery |
| Partial pipeline | "just design", "just review this code" | Only the explicitly requested approved subset |
| Resume | Active latest run or existing approved artifacts detected | Start from the earliest incomplete boundary after lock and lineage validation |
| Create-skill | "create a skill", "build me a skill" | Intake -> Skill-maker -> Delivery |
| Create-team | "create a team", "build me a pipeline" | Intake -> Skill-maker team mode or in-catalog team package -> Delivery |

## Agent Mode

Admiral can operate in two execution modes depending on the host platform.

**Agent mode** uses `agent/agent-manifest.yaml`, `agent/agent-protocol.md`, and the adapter docs under `agent/adapters/` to manage state programmatically, delegate sub-agents, and validate boundaries with live tool access.

**Skill mode** keeps the same stage sequencing, gatekeeper routing, and rewind rules, but expresses them as instructions for the host agent to carry out manually.

At intake, detect whether the host exposes sub-agent delegation, file operations, and command execution. Record the detected mode in the run state record so resumes do not mix autonomous and instruction-only behavior.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A resume package claims approval but the revision lineage or gate record does not match the submitted artifact set | Rewind to the earliest affected boundary and explain exactly which approval chain broke. |
| An upstream package changes after downstream work has already started | Invalidate the dependent handoffs, preserve the superseded evidence, and replay only the boundaries affected by the drift. |
| A create-skill or create-team request arrives without usable trigger language, success criteria, or packaging target | Stop at intake, collect the missing intent, and do not hand skill-maker an underspecified brief. |
| The host loses a required tool capability mid-run, such as sub-agent delegation or file writes | Fall back to skill mode only for the affected boundary, record the degraded execution path, and keep the remaining approvals consistent. |
| `skillset-saves/` contains an active latest run when the user sends a fresh-looking request | Treat the session pin and saved state as authoritative: run the resume protocol, present the active boundary, and do not fork a new run unless the user explicitly asks for one. |
| Persistence activation fails after a missing or inactive `skillset-saves/` directory is detected | Warn once, record `persistence_activation_result: failed` when writable, try read-only resume from any readable latest artifacts, then continue in transient mode only if no coherent boundary can be proven. |
| A saved latest run is unreadable or partially corrupt | Preserve any readable artifacts, classify the directory as `unreadable`, attempt read-only resume from the earliest provable boundary, and otherwise continue transiently with a clear warning instead of overwriting the evidence. |
| `_latest.md` is missing or stale but `runs/` still holds a non-terminal run | Classify the directory `orphaned`, not `missing`. Rebuild `_latest.md` to point at the most recent non-terminal run, append `LATEST_POINTER_REBUILT`, and run the resume protocol. Never fork a fresh run over a recoverable orphan — a lost pointer is not a lost run. |
| Two handoff submissions refer to the same boundary but carry conflicting verdict histories | Preserve both records, treat the boundary as disputed, and escalate rather than silently normalizing the conflict. |
| Persistence write-probe fails at intake but admiral still emits `Persistence active: yes` | Treat as a contract violation. Downgrade the run to `Persistence active: no`, warn the user once, and rewrite every Save Context block accordingly before any sub-orchestrator delegation. |
| Mode probe at a boundary disagrees with the cached `execution_mode` | Reconcile in place: update `_state.md`, append `MODE_RECHECK` with `cached`, `detected`, and `action`, continue under the new mode. Do not abort the delegation, do not force the user to retry. |
| User input arrives mid-run without the keyword "admiral" while a run is `*_ACTIVE` | Honor the session pin. Route the input through the active sub-orchestrator, append the routing decision to the audit trail, and never fork a parallel skill that bypasses the run. |
| `mcp-tools.md` is missing or `last_discovery_at` exceeds `discovery_ttl_hours` (default 480h) at intake | Pause at intake, prompt the user with the auto-detected MCP list, and only proceed once the registry is confirmed or rewritten with a fresh `last_discovery_at`. |
| `verify_registration.py` reports MISSING or UNKNOWN at intake — one or more harness hooks are not registered for the active host | Surface the `REGISTER_PROMPT`, explain that entry routing is advisory-only until the prompt-submit hook is registered, and offer to register all three hooks by rerunning the installer with `-RegisterHooks` / `--register-hooks`. If the user declines, warn once and continue (the description/doctrine layer still applies). A new or changed hook config may need `/hooks` or a restart to load. |
| `check_readiness.py` reports Python too old, hooks missing, or no active pinned save run after startup | Record `RUNTIME_READINESS_CHECK`, surface the specific failed dimension, retry only the save startup check when saves are missing, and otherwise continue with an explicit degraded-mode note unless the user approves hook registration or Python installation. |

## Save Protocol

Persistence is mandatory when file-system tools are available. For the full save-trigger table, directory structure, file formats, write-ownership matrix, `### Save Context` block template, and resume protocol, see `../save-protocol.md`.

## References

- `routing-doctrine.md` (skill set root) for the entry-routing contract that makes Admiral the canonical front door, the in-scope vs standalone tiers, the active-handoff loop guard, and the `UserPromptSubmit` reinforcement hook.
- `grill-me-doctrine.md` (skill set root) for the binding intake interview protocol run at intake before any delegation.
- `references/workflow.md` for the detailed intake, sequencing, rewind, and delivery rules.
- `references/examples.md` for concrete full-pipeline, resume, and skill-maker request patterns.
- `intake-brief.yaml` for the normalized intake surface Admiral passes into a new run.
- `stub-contract.md` for the stage ownership and handoff contract summary.
- `save-protocol.md` (skill set root) for the persistent save system: directory structure, file formats, write probe, mode re-check, session pin, save triggers, and resume protocol.
- `mcp-tools.md` (skill set root) for the global MCP tool registry; admiral enforces its `discovery_ttl_hours` freshness rule (default 480h) at intake.
- `harness/hooks/check_readiness.py` for the combined runtime readiness diagnostic used after persistence activation/resume.
- `agent/agent-manifest.yaml` for agent capabilities and platform support.
- `agent/agent-protocol.md` for agent-mode execution behavior.
- `agent/adapters/copilot.md` for GitHub Copilot integration details.
- `agent/adapters/codex.md` for Codex integration details.
- `agent/adapters/claude.md` for Claude Code integration details.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/` together. Keep generated reports and archives outside the skill directory.
