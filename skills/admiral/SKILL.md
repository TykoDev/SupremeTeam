---
name: admiral
description: >-
  SupremeTeam front door for the delivery lifecycle. Use to run the full
  pipeline, ship end to end, resume from a checkpoint or an approved package,
  design or build this project, redesign the UI, review or audit this codebase,
  run a security audit, QA a product or test it like a user, find the root
  cause, manage Taste preferences, set or change design preferences, create a
  skill, build a team, or run Admiral — even when the request never says
  Admiral. Standalone guardrail, browser, release, and testing tools run
  directly.
version: 2.1.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Admiral

## Purpose

Admiral routes and records; it authors no phase deliverable. Its boundary is the space *between* stages — intake, run state, delegation, gate routing, rewind, and delivery assembly — because a lifecycle request that enters through a sub-orchestrator loses the one thing no single stage can supply: a run whose approvals, revisions, and persistence stay consistent across stage handoffs.

Two things are most often got wrong. Resume starts from the newest artifact found on disk instead of the earliest incomplete *approved* boundary, which silently launders unapproved work into the package. And a missing `_latest.md` is read as "no run", which forks a second run over a recoverable orphan; the pointer is not the run, `runs/` is.

## Entry Primacy

Admiral is the **primary entry orchestrator** for SupremeTeam — the single front door for all
delivery-lifecycle work, as defined in `routing-doctrine.md` (skill set root). Every
in-scope request (design, redesign, build, review, security audit, product QA, ship,
investigate, explicit Taste management, checkpoint/resume, gate validation, skill/team
creation) initiates here so that one intake, one persisted run, and
one cross-stage gatekeeper govern the whole pipeline. The in-scope sub-orchestrators and
utilities (`design/commander`, `design/redesign`, `build/build-management`, `review/code-chief`, `skill-maker`,
`investigate`, `taste`, `session-memory`, `gatekeeper-admiral`) defer to Admiral when reached without
an active Admiral handoff; Admiral reaches them by name through its delegation surface, so
its own delegations always carry the handoff signal and never bounce back. Only standalone
tools (`careful`, `freeze`, `guard`, `unfreeze`, `browse`, `open-browser`, `setup-browser-cookies`, `pair-agent`, `benchmark`, and
`setup-deploy`, `land-and-deploy`, `document-release`) run outside this routing; `qa`, `qa-only`,
and `ship` are dual-mode — invoked by name they run directly, but a cold
lifecycle request for QA or release enters here. The
`harness/hooks/user_prompt_submit.py` hook reinforces this on every fresh user turn.

## Use This Skill When

- run the full pipeline
- ship this end to end
- resume the pipeline
- continue from the approved package
- design or build this project
- redesign the UI / refresh the look and feel
- review or audit this codebase
- run a security audit / threat-model this system
- QA this product / test it like a user
- find the root cause / investigate this bug
- set or change my design preferences
- create a skill
- build me a skill for
- create a team of skills
- build me a pipeline for
- run admiral

Each phrasing above maps to one route in `references/routing.md`; a request that
matches none of them is free conversation, and standalone tools
(`careful`, `freeze`, `guard`, `unfreeze`, `browse`, `open-browser`, `setup-browser-cookies`, `pair-agent`,
`ship`, `setup-deploy`, `land-and-deploy`, `document-release`, `qa`, `qa-only`, `benchmark` — invoked by name) run without entering a run at all.

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

## Preamble Tier

Select the tier before acting, per `../execution-contract.md` clause 1. Tier is a
property of the run, not of a skill.

| Tier | Blast radius | Ceremony |
| --- | --- | --- |
| 0 | Local, understood, reversible; acceptance is obvious | Direct change, focused verification, brief completion note |
| 1 | Bounded and read-only | Intake, evidence, no state change |
| 2 | Multi-step edits, delegation, external coordination | Full pipeline route, saved run, gate package |
| 3 | Destructive, security-sensitive, production, irreversible | Tier 2 plus explicit owner intent and a fresh human go decision |

## Execution Contract

Canonical source: `../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a paraphrase
is drift, and `skills/validation/test_catalog_contracts.py` compares them exactly.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Tier 0 Fast Path

Before the workflow below, apply the Tier 0 fast path in
`../routing-doctrine.md#tier-0-fast-path`. For an eligible minor task, inspect,
change, verify, and report directly: no intake interview, delegation, readiness
probe, saved run, session pin, phase manifest, or gatekeeper verdict. Finish with
the rationale, the changes, the checks actually performed with their results, and
any remaining limitation.

Tier 0 never covers authentication, authorization, secrets, sensitive-data
handling, trust boundaries, security controls, deployment settings, production
state, or destructive behavior. An active session pin takes precedence: its
artifacts stay with the owning phase and cannot use Tier 0 to bypass a pending
gate. If scope grows or verification fails for an unknown reason, stop, reclassify
to Tier 1, 2, or 3, and carry the diff and observed checks into normal intake.
Never use Tier 0 to waive a failed check.

The workflow below applies after Tier 0 has been ruled out.

## Workflow

1. **Classify the save directory before creating state.** Inspect `skillset-saves/_latest.md` and classify the directory as active, inactive, orphaned, missing, unreadable, or conflict per `save-protocol.md` §2 Startup, then resume an active reclaimable run before starting a new one. `_latest.md` is a pointer, not the run: never conclude "no run to resume" from its absence without scanning `runs/` first and rebuilding the pointer over a recoverable orphan. If activation fails, warn once, attempt read-only resume from any readable saved artifacts, and continue transiently only when no coherent resume boundary can be proven.
2. **Establish readiness and shared understanding.** Classify the request as full, partial, resume, create-skill, or create-team, and probe whether the host supports agent mode. Then run the four intake contracts in `references/contracts.md` — Harness Hook Registration, Runtime Readiness Diagnostic, MCP Registry Freshness, and Grill-Me Intake — recording each result in `_state.md` and the audit trail. The grilling result is written to `skillset-saves/runs/{run-id}/intake/report_grilling.md`, which is the hashed artifact behind the `decisions` gate key, so a design package whose decisions are not backed by it fails `design-to-build` mechanically. Reject any stage skip that lacks explicit approval lineage.
3. **Create the run, then delegate the earliest incomplete boundary.** Create through `session-memory` (`python skills/harness/hooks/save_run.py create --run-id <run> --evidence skillset-saves/runs/<run>/intake/report_grilling.md`) before the first delegation, and checkpoint (`checkpoint --expect-revision <n>`) before every later one. A `refused` result is a contract violation to resolve, never something to work around by hand-editing save files. Resolve every generated destination with `python skills/scripts/output_paths.py`. Re-probe execution mode at the boundary, prepare the handoff from `intake-brief.yaml` and `stub-contract.md`, and delegate only to the sub-orchestrator that owns that boundary.
4. **Gate every returned package.** Route it through `gatekeeper-admiral`, which validates against the canonical spec `../gates.yaml` with `python skills/harness/gatekeeper/check.py --boundary <boundary> --package <phase>/manifest.json --prior <phase>/verdict_<boundary>.json --verdict-out <phase>/verdict_<boundary>.cross-stage.json` — the `--prior` is the phase gatekeeper's record when one exists, and the cross-stage record is written beside it, never over it. Exit 0 is a mechanical fact, not approval. Reuse a verdict only when the result reports `prior_reusable: true`, and rewind to the earliest affected boundary when upstream evidence changes.
5. **Assemble only approved packages** into one delivery package with traceability, open disputes, next actions, and any skill-maker outputs the user requested.

## Required Contracts

Fifteen contracts bind this run. The decision each one forces is stated here;
`references/contracts.md` carries their full normative text, and neither document
paraphrases the other.

**At intake, before any run exists**

- **Grill-Me Intake**: reach a shared understanding before delegating anything, and write the result to the intake artifact that backs the `decisions` gate key.
- **Harness Hook Registration**: run `verify_registration.py`; without the prompt-submit hook, entry routing is advisory-only, and that is said out loud rather than assumed away.
- **Runtime Readiness Diagnostic**: run `check_readiness.py`; a failed dimension degrades the run with a named warning, never blocks it silently.
- **MCP Registry Freshness**: a registry older than its TTL is confirmed or refreshed before it is trusted.

**Persistence and mode, at every boundary**

- **Save-Protocol Adherence**: probe before claiming persistence; `Persistence active: yes` without a successful probe is a contract violation.
- **Mode Re-Check**: reconcile the capability probe against the cached mode in place; a changed host updates the record rather than failing the delegation.
- **One Writer**: admiral writes intake, routing, the grilling log, cross-stage handoffs, and the delivery package — and nothing a phase lead, gatekeeper, or `session-memory` owns.

**Routing, on every user turn**

- **Entry Routing**: the first turn of a lifecycle request initiates here, not at a sub-orchestrator.
- **Session Routing**: while a run is active and the lock is held, the session is pinned and every input routes through the active sub-orchestrator.

**Gate and evidence, at every submission**

- **Gate Spec Authority**: `../gates.yaml` and `../pipelines.yaml` decide required evidence, fallbacks, submitters, and stage maps. An evidence key they do not declare is never accepted or required.
- **Stack Lock**: `stack_lock` is required at `design-to-build`, detected with `check_runtime.py --detect-project`, never invented.
- **Design System Evidence**: a user-facing surface owes `ui_evidence` at `design-to-build` and `rendered_verification` at `review-to-delivery`; a run with no such surface carries the sanctioned applicability record.
- **Taste**: resolve applicable user Taste for presentation and interaction choices, keep the current explicit instruction highest, and surface conflicts with mandatory requirements rather than normalizing them.
- **Shared severity**: Critical | Major | Minor | Info, per execution-contract clause 3 above.
- **Canonical Contracts**: apply `../contracts/` at the point each one governs — evidence claims, delegations, state transitions, ownership questions, and `RUN_COMPLETE`.

## Delegation Surface

- `design/commander`
- `build/build-management`
- `review/code-chief`
- `design/redesign` for the redesign pipeline, gated at `redesign-review`; its chosen variant then enters `design/commander` as the design-system input
- `review/cso` for the security pipeline, gated at `security-review`
- `investigate` for the investigation pipeline, gated at `investigation-review`
- `qa` for the qa pipeline, gated at `qa-review`; a report-only run stays under `qa`, which may run the sweep through `qa-only` but remains the only `qa-review` submitter
- `ship` for the release pipeline, gated at `deploy-readiness`, after delivery approval and with a fresh human go decision
- `gatekeeper-admiral`
- `skill-maker` for on-demand skill and team creation
- `taste` for explicit preference inspection and lifecycle mutation
- `session-memory` for cross-session checkpoints and durable learnings

## Mandatory Intake Engagement

Immediately after the user confirms scope at intake — and before the first sub-orchestrator delegation — Admiral engages `session-memory` to checkpoint the normalized intake. This engagement is unconditional: it does not wait for context tier 3+ or the first gate. Because the intake checkpoint plus the first stage sub-orchestrator are both guaranteed, every run engages at least two catalog skills (`session-memory` plus the stage owner, e.g. `design/commander`) even when the run covers a single stage or ends early. Record every engaged catalog skill in the run-state `skills_engaged` list (see `agent/agent-protocol.md`) the first time it is engaged; re-engaging an already-listed skill does not duplicate the entry.

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse a prior verdict only when the package revision is unchanged.
- Push remediation back to the owning sub-orchestrator instead of editing its package locally.
- Map skill-maker verdicts as `SHIP` -> `APPROVED`, `ITERATE` -> `REVISE`, `BLOCKED` -> `ESCALATE`.
- Cap cross-stage revision cycles at two before escalating the dispute to the user.
- Treat every `REVISE` as one packet (`../gates.yaml` `revise_policy`): forward all of `revise_packet.by_owner` plus the gatekeeper's judgment findings to the owning sub-orchestrator in one delegation, expect it to fan owner groups out in parallel and resubmit once, and pass `--prior` on the resubmission so the gate re-judges only `changed_evidence`.

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

## Pipeline Routes

`references/routing.md` carries the full request-to-route map with each route's
closing boundary. Three rules decide the rest:

- The delivery chain is `design/commander` then `build/build-management` then `review/code-chief`, closing at `design-to-build`, `build-to-review`, and `review-to-delivery`. A partial request enters it at the earliest incomplete boundary rather than at the stage the user named.
- Every other pipeline — redesign, security, investigation, qa, taste, skill-maker, release — is a single-owner route closing at its own boundary, listed with that owner and boundary in the Delegation Surface above. Its output returns here; it never chains into the next stage on its own.
- `../pipelines.yaml` is the authoritative stage map. When prose and file disagree, the file wins.

## Agent Mode

Admiral can operate in two execution modes depending on the host platform.

**Agent mode** uses `agent/agent-manifest.yaml`, `agent/agent-protocol.md`, and the adapter docs under `agent/adapters/` to manage state programmatically, delegate sub-agents, and validate boundaries with live tool access.

**Skill mode** keeps the same stage sequencing, gatekeeper routing, and rewind rules, but expresses them as instructions for the host agent to carry out manually.

At intake, detect whether the host exposes sub-agent delegation, file operations, and command execution. Record the detected mode in the run state record so resumes do not mix autonomous and instruction-only behavior.

## Failure Modes

These five change what Admiral does next. The lineage, persistence, mode, and
readiness failures whose handling is procedural rather than routing are in
`references/failure-modes.md`, which repeats none of these rows.

| Scenario | Response |
| --- | --- |
| The request names no deliverable, or the intake brief comes back malformed, empty, or self-contradicting (a resume hint with no run id, a stage skip with no approval lineage) | Do not classify a mode from a guess. Name the missing or conflicting field, ask the one question that resolves it under `grill-me-doctrine.md`, and create no run until scope is answerable. An unparseable brief is an intake failure, never a Tier 0 shortcut. |
| `_latest.md` is missing or stale but `runs/` still holds a non-terminal run | Classify the directory `orphaned`, not `missing`. Rebuild `_latest.md` to point at the most recent non-terminal run, append `LATEST_POINTER_REBUILT`, and run the resume protocol. Never fork a fresh run over a recoverable orphan — a lost pointer is not a lost run. |
| A boundary returns `REVISE` twice, exhausting `../gates.yaml` `revise_policy.cycle_cap` of 2 | Stop resubmitting. Run `save_run.py checkpoint --run-id {run-id} --owner admiral --expect-revision <n> --set phase_state=DISPUTED_AWAITING_USER --next-action "<dispute>"` — a checkpoint rather than `block`, so the run keeps the session pin while the user decides — preserve both revise packets and both verdicts as evidence, and return a user-decision packet naming the unclosed evidence keys, their owners, and the options. A third cycle is escalation, not another attempt. |
| A required tool or host capability is unavailable: sub-agent delegation, file writes, or the Python the harness scripts need | Fall back to skill mode for the affected boundary only, record the degraded execution path in `_state.md`, and keep the remaining approvals consistent. When Python is what is missing, the gate cannot be validated mechanically: mark the boundary unverified rather than approved, and name the check that did not run. |
| User input arrives mid-run without the keyword "admiral" while a run is `*_ACTIVE` | Honor the session pin. Route the input through the active sub-orchestrator, append the routing decision to the audit trail, and never fork a parallel skill that bypasses the run. |

## Save Protocol

Persistence is mandatory when file-system tools are available. For the full save-trigger table, directory structure, file formats, write-ownership matrix, `### Save Context` block template, and resume protocol, see `../save-protocol.md`.

## References

- `gates.yaml` (skill set root) for the canonical gate spec: ten boundaries with their required evidence, artifact-backed keys, sanctioned fallbacks, typed records, and submitters.
- `pipelines.yaml` (skill set root) for the ten pipelines, their ordered stages, stage owners, closing boundary, and required scripts.
- `ownership.yaml` and `save-ownership.yaml` (skill set root) for the one-writer contracts at artifact and path level.
- `execution-contract.md` (skill set root) for the canonical preamble clauses and the tier table.
- `contracts/` (skill set root) for evidence standards, handoff templates, the workflow state machine, the responsibility matrix, universal frameworks, and the delivery template.
- `tech-stacks/registry.yaml` (skill set root) for the stack overlays behind `stack_lock`.
- `harness/gatekeeper/check.py` for the boundary validator that loads `gates.yaml`.
- `harness/hooks/save_run.py` for the run lifecycle operations `session-memory` uses.
- `routing-doctrine.md` (skill set root) for the entry-routing contract that makes Admiral the canonical front door, the in-scope vs standalone routing classes, the active-handoff loop guard, and the `UserPromptSubmit` reinforcement hook.
- `grill-me-doctrine.md` (skill set root) for the binding intake interview protocol run at intake before any delegation.
- `taste-doctrine.md` (skill set root) for the canonical scope, provenance, lifecycle, and deterministic resolution of user-authored or explicitly confirmed presentation and interaction preferences.
- `references/routing.md` for the full request-to-route map and the frontend/UI routing note.
- `references/contracts.md` for the full normative text of the fifteen contracts the Required Contracts section names.
- `references/workflow.md` for the detailed intake, sequencing, rewind, and delivery rules.
- `references/failure-modes.md` for the lineage, persistence, mode, and readiness failures the SKILL.md table does not carry.
- `references/examples.md` for concrete Tier 0, full-pipeline, resume, redesign, security, QA, and skill-maker request patterns.
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

Package `SKILL.md`, `references/workflow.md`, `references/routing.md`, `references/contracts.md`, `references/failure-modes.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/` together. Keep generated reports and archives outside the skill directory.
