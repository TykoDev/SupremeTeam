---
name: skill-maker
description: >
  End-to-end orchestrator for creating, reviewing, improving, optimizing, and packaging Claude
  skills and coordinated skill teams. Use when the user says "create a skill", "run the skill
  pipeline", "review this skill", "harden this skill", "take this skill to 100", "optimize the
  description", "fix triggering", or describes a desired skill behavior without naming one —
  and when `admiral` delegates skill or team creation. Routes drafting, evals, fixes, scoring,
  and packaging to specialists; not for general code review, architecture, or non-skill
  authoring.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Skill Maker

## Purpose

Keep authorship and judgment in different hands. One specialist writes the skill,
another scores it, and this orchestrator owns only the loop between them — which
is why it never edits a file it is about to have reviewed, and never softens a
verdict it does not like. The stage model exists so that a skill reaching 100 has
been through an adversary rather than an author's own second reading.

Cold lifecycle requests first enter admiral; skill-maker then runs as its
delegated sub-orchestrator under the routing contract.

> "Orchestrate, delegate, gate. The orchestrator routes work and enforces the quality
> loop. It never writes skill content or scores rubric dimensions — that is the
> specialists' job."

## Use This Skill When

Use this orchestrator to **run the authoring loop** — draft, score, fix, re-score, package — rather than to write or judge a skill directly:

- "run the skill pipeline" — take an intent through drafting, review, and packaging in one governed run
- "review this skill" — schedule the adversarial score and route its findings back to the drafter
- "harden this skill" / "take this skill to 100" — iterate the loop until the rubric stops moving
- "optimize the description" / "fix triggering" — tune the trigger surface through the eval-and-fix cycle

Route elsewhere for the score itself (`skill-maker/skill-reviewer`) or the file edits (`skill-maker/skill-creator`); both are reached through this orchestrator and neither is entered directly. A cold lifecycle request enters `admiral` first, which owns the bare "create a skill" phrasing and delegates here.

## Entry Routing

Skill-maker is a component of the **Admiral** delivery pipeline; `admiral` (the SupremeTeam
pipeline orchestrator) is the primary entry orchestrator (see `../routing-doctrine.md` —
gates which orchestrator owns a given request and prevents double-routing). Before starting Stage 0, run the
**active-handoff check** — a handoff is present when the prompt carries a `### Save Context`
block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or `admiral`
explicitly delegates a skill/team-creation request (the `## Admiral Integration` contract
below).

- **Handoff present** → proceed with the pipeline; this is a delegated Admiral run.
- **No handoff (cold/direct invocation for a create/review/improve request)** → do not run
  standalone. Start `admiral` first (its Create-skill / Create-team mode), let it run intake
  and persistence, then accept the delegation back. This is the loop guard: Admiral delegates
  with the handoff signal, so a routed call proceeds immediately and never re-bootstraps
  Admiral.

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

## Pipeline overview

```
User Request
    │
    ▼
┌─────────────┐
│ Stage 0      │  Intake — classify mode, gather context
│ INTAKE       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Stage 1      │  Delegate to skill-creator (Create mode)
│ CREATE       │  → draft SKILL.md + supporting files
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Stage 2      │  Delegate to skill-reviewer
│ REVIEW       │  → scorecard + findings report
└──────┬──────┘
       │
       ▼
  score = 100? ──yes──→ Stage 4 (Optimize)
       │
      no
       │
       ▼
┌─────────────┐
│ Stage 3      │  Delegate to skill-creator (Improve mode)
│ IMPROVE      │  → apply reviewer findings
└──────┬──────┘
       │
       └──→ Loop back to Stage 2
              (max 5 cycles)

       ▼
┌─────────────┐
│ Stage 4      │  Delegate to skill-creator (Optimize mode)
│ OPTIMIZE     │  → description trigger accuracy
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Stage 5      │  Delegate to skill-creator (Package mode)
│ PACKAGE &    │  → .skill file + delivery report
│ DELIVER      │
└─────────────┘
```

---

## Stage 0 — Intake

Before classifying, run the `../grill-me-doctrine.md` intake interview — gates entry into
the pipeline by ensuring the skill's purpose, trigger language, and success criteria are
understood before any drafting begins — one question at a time, always recommending an
answer, and exploring existing skills and code instead of asking when the answer is
discoverable. If the doctrine file is absent (standalone install), run a brief inline
intake interview covering purpose, trigger language, and success criteria instead.

Classify the user's request into one of four entry modes:

| Mode | Entry condition | Starts at |
|------|----------------|-----------|
| **Full pipeline** | "Create a skill", "make a skill", "take this to 100" | Stage 1 |
| **Review-only** | "Review this skill", "score my skill", "audit this" | Stage 2 (skip 1) |
| **Improve-only** | "Fix these findings", "improve this skill" | Stage 3 (skip 1-2) |
| **Optimize-only** | "Optimize the description", "fix triggering" | Stage 4 (skip 1-3) |

For **full pipeline** and **improve-only**, confirm the user's intent and constraints
before proceeding. For **review-only**, just need the skill path. For
**optimize-only**, need the skill path and optionally existing eval queries.

If the user provides an existing skill path, validate it before proceeding, the
same way skill-reviewer does at its own Phase 1.1: resolve the path, confirm it
lands on a real directory **inside the working area** — no traversal through
`..`, a symlink, or an absolute path outside the project root — and confirm a
readable `SKILL.md` exists inside it. If the path escapes the working area, does
not exist, or has no SKILL.md, stop and ask the user to confirm the location
rather than delegating a guessed path; every downstream stage writes to whatever
path this one accepts.

**Track A ownership.** Behavioral evals belong to skill-creator and run inside
Stage 1 and Stage 3, not as a stage of their own. The orchestrator asks for them
in the Create and Improve handoffs, accepts "none run" as a valid answer for a
skill with subjective outputs, and forwards whatever came back to Stage 2 so the
reviewer scores against both tracks. Eval results accumulate: a later review sees
every prior iteration's runs.

---

## Stage 1 — Create

Delegate to **skill-creator** in Create mode.

**Handoff includes:**
- User intent and constraints from intake
- Entry mode (new skill vs. harden existing)
- Path to existing skill (if hardening)
- Any example files or context the user provided

**Expected return:**
- Draft SKILL.md with frontmatter
- Supporting files (references/, scripts/, agents/, examples/ as needed)
- Behavioral eval results (if Track A evals were run)
- Skill directory path

**On return:** Verify the skill directory exists and SKILL.md is present. If
skill-creator reports blockers, surface them to the user and re-delegate with
clarifications. Proceed to Stage 2.

---

## Stage 2 — Review

Delegate to **skill-reviewer**.

**Handoff includes:**
- Skill directory path
- Iteration number (1 for first review, N+1 for subsequent)
- Previous scorecard (if iteration > 1, for delta tracking)
- Behavioral eval results (if available from Stage 1 or Stage 3)

**Expected return:**
- Scorecard (10 dimensions, each scored with evidence)
- Findings list (F-01, F-02, ... with severity, location, fix instructions)
- Verdict: SHIP (100/100) | ITERATE (< 100) | BLOCKED (critical findings)
- Iteration history (if iteration > 1)

**On return:**
- If **SHIP** → proceed to Stage 4 (Optimize), or Stage 5 when this is the re-review after optimization
- If **ITERATE** → proceed to Stage 3 (Improve)
- If **BLOCKED** → surface critical findings to user, get guidance, then either
  proceed to Stage 3 or abort

Present the scorecard and key findings to the user between stages. The user should
see progress at every iteration boundary.

---

## Stage 3 — Improve

Delegate to **skill-creator** in Improve mode.

**Handoff includes:**
- Skill directory path
- Full findings list from reviewer (prioritized: critical → major → minor)
- Current scorecard with scores per dimension
- Iteration number
- Any user guidance or overrides ("skip finding F-04", "prioritize security")

**Expected return:**
- Updated skill files
- Summary of changes made (which findings addressed, which deferred)
- Updated behavioral eval results (if re-run)

**On return:** Proceed to Stage 2 (Review) for the next scoring pass.

---

## Stage 4 — Optimize

Delegate to **skill-creator** in Optimize mode.

**Handoff includes:**
- Skill directory path
- Current description (confirmed at 100/100 by reviewer)
- Existing eval queries (if any from previous stages)

**Expected return:**
- Optimized description
- Trigger eval results (before/after accuracy)
- `best_description` selected by test-set score

**On return:** If the optimized description changed, return to Stage 2 to review
the exact revised files before packaging. After that review passes, proceed to
Stage 5 without repeating optimization. If no file changed, reuse the matching
review and proceed to Stage 5.

---

## Stage 5 — Package & Deliver

Delegate to **skill-creator** in Package mode.

**Handoff includes:**
- Skill directory path
- Output directory: the active run's `skillset-saves/runs/{run-id}/skill-creation/packages/` (resolved with `python skills/scripts/output_paths.py --kind packages`), or `.harness-state/packages/` outside a run; never the skill directory or the project root

**Expected return:**
- `.skill` file path
- Package contents summary

**Final delivery to user:**
Compile the delivery report using `references/delivery-template.md` — the blank
form — and present it with the packaged skill. Include the full iteration history,
final scorecard, and changes summary. `references/examples.md` shows the same
template filled in for a complete run, alongside the gate manifest it produced.

### Gate submission — `skill-maker-to-delivery`

This skill is the submitter at the `skill-maker-to-delivery` boundary (`../gates.yaml`).
Its four required evidence keys come from three owners, so the package is assembled from
what the specialists return rather than restated by the orchestrator:

| Key | Owner | Content | Backing |
|-----|-------|---------|---------|
| `skills` | skill-maker | The delivered skill directories, each with its final rubric score. | Narrative |
| `team_manifest` | skill-maker | For a team, the manifest describing component relationships and the delegation surface between them. For a single skill, the wording exactly as `../gates.yaml` `fallback_values.team_manifest` spells it — `single skill - no team manifest produced` — carried as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`, since schema 2 refuses a bare string. | Narrative |
| `link_report` | skill-reviewer | Every bundled pointer resolved, with broken and orphaned files listed. | Artifact-backed — a hashed file |
| `validation_report` | skill-creator | The `quick_validate.py` result for each delivered skill. | Artifact-backed — a hashed file |

Run the self-check before submitting, so the boundary is judged deterministically:

```bash
python skills/harness/gatekeeper/check.py --boundary skill-maker-to-delivery --package <manifest.json>
```

`link_report` and `validation_report` must reference hashed files in the package's
`artifact_hashes` map. A bare claim that validation passed is not evidence. A
single-skill run carries the sanctioned `team_manifest` wording byte-for-byte as
the `reason` of an applicability record
`{applicable: false, reason, scope, decided_by}`, never as the key's own value:
the manifest is `schema_version: 2`, where `check.py` refuses a bare fallback
string outright. A paraphrase such as "no team was created" is not the sanctioned
wording and fails the mechanical check before any judgment is applied, and so
does the sanctioned wording written as a bare string.

**When the self-check fails**, do not submit. The checker groups every failure by
the evidence key it names and by that key's owner, so read the failure list as a
routing table:

| Failure | Response |
| --- | --- |
| A key is missing or falsy | Re-delegate to that key's owner: `link_report` to skill-reviewer, `validation_report` to skill-creator, `skills` and `team_manifest` to this orchestrator's own packaging step. Never fill another owner's key to make the check pass. |
| `link_report` or `validation_report` names a path absent from `artifact_hashes` | The file was described rather than shipped. Get the file written and hashed, then rebuild the manifest; hand-adding the hash of a file nobody produced is a fabricated artifact. |
| `team_manifest` carries a paraphrase, or a bare string — even the sanctioned one | Put the exact wording `single skill - no team manifest produced` in the `reason` field of an applicability record `{applicable: false, reason, scope, decided_by}`, or produce the real manifest for a team run. At schema 2 a bare string is rejected with `bare fallback string not accepted at schema 2: team_manifest (use an applicability record)`, so re-spelling the value is not the fix; re-shaping it is. `references/examples.md` shows the record. |
| The checker itself errors, or the boundary spec cannot be loaded | Treat gate-engine failure as `ESCALATE`, never as approval. Report the error and the unjudged package rather than submitting on a machine that did not run. |

Fix every mechanical failure and re-run the self-check before submitting, so the
gatekeeper spends judgment only on a package that already passes the machine.

---

## Quality gate management

### Review-improve loop rules

| Rule | Value |
|------|-------|
| Max review-improve cycles | 5 |
| Plateau detection | If score unchanged for 2 consecutive iterations, escalate |
| Plateau escalation | Present findings to user with: "Score plateaued at X/100. The remaining findings may need your input. Options: (a) override and ship, (b) provide guidance on specific findings, (c) abort." |
| Critical finding policy | Critical blocks gate approval until a verified fix or an explicit not-applicable reason, per `../gates.yaml`. A user-requested partial delivery does not constitute gate approval. |
| Score threshold for optimization | 100/100 (description optimization only runs after perfect score) |

### What the orchestrator never does

- **Never modifies skill files directly** — route all changes through skill-creator.
- **Never scores rubric dimensions** — route all scoring through skill-reviewer.
- **Never overrides a reviewer verdict.** If the reviewer says ITERATE, the
  orchestrator iterates — unless the user explicitly overrides.
- **Never invents findings.** Passes reviewer output to creator verbatim.

### User visibility

Present to the user at every stage boundary:
- Current score and delta from previous iteration
- Key findings (critical and major only for brevity)
- What happens next and estimated remaining stages
- Option to override, skip stages, or abort

---

## Adaptive behavior

### Partial pipeline support

Users can enter at any stage and exit early. The intent-to-stages mapping is
tabulated once, in `references/workflow-protocol.md` § Partial pipeline handling;
read it there rather than from a second copy that can drift out of agreement.

Honor explicit user requests to skip stages, and record which stages were skipped
so the delivery report reflects what actually ran. If the user says "ship it"
during the review loop, present the current score and confirm before skipping
remaining iterations — a skipped review is a delivery at an unknown score, not a
faster 100.

### Handling user feedback mid-loop

The user may provide feedback at any stage boundary:
- **Redirect:** "Actually, the skill should also handle X" → add to constraints,
  re-delegate to creator in Improve mode with the new requirement
- **Override:** "F-04 is not a real issue, skip it" → note the override, exclude from
  future improve handoffs, tell reviewer to not re-flag
- **Abort:** "Stop, this isn't working" → present current state, offer to save
  progress, clean exit

### Error recovery

| Error | Response |
|-------|----------|
| Specialist returns incomplete output | Re-delegate with explicit note about what is missing |
| Specialist cannot access skill files | Verify path, ask user to confirm location |
| Review score regresses (lower than previous) | Flag regression to user, include both scorecards, ask whether to continue or revert |
| Max iterations reached without 100/100 | Present final state, offer: (a) ship at current score, (b) continue manually, (c) start over |
| User provides conflicting instructions | Surface the conflict, ask for clarification, do not guess |

---

## Team Creation Protocol

When the request is to create a coordinated *team* of skills (e.g. "create a team of
skills", "build me a pipeline of skills") rather than a single skill:

1. Capture the team purpose, pipeline stages, specialist roles, and interaction patterns.
2. Generate the orchestrator skill first — it defines the delegation surface and stage model.
3. Generate each specialist skill with inputs/outputs shaped for the orchestrator's handoff contracts.
4. Generate the gatekeeper skill with verdict vocabulary and evidence standards matching the orchestrator's boundary rules.
5. Run each generated skill through the standard review-improve loop (Stages 2-3).
6. Package all skills as a coordinated team with a team manifest describing relationships.

---

## Admiral Integration

When invoked by Admiral (or another parent orchestrator) as a utility orchestrator:

- Admiral provides the skill intent or team description as input.
- Skill-maker runs its full pipeline autonomously and returns the delivery package.
- Verdict mapping for Admiral's handoff protocol: `SHIP` → `APPROVED`, `ITERATE` →
  `REVISE`, `BLOCKED` → `ESCALATE`.
- Admiral's `gatekeeper-admiral` validates the skill-maker output at the cross-pipeline
  boundary.
- Maximum revision cycles when called by Admiral: **2** (per Admiral's standard handoff
  rules), distinct from the internal max of 5 review-improve cycles.

---

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with
`Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path
   specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`,
   `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that
   path, so it is not an orchestrator-owned file either — phase state is published only
   through `save_run.py checkpoint`, which keeps revision lineage and the audit trail
   coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and
deliver output inline as usual.

---

## Reference files

| File | Purpose | When to read |
|------|---------|-------------|
| `../grill-me-doctrine.md` | Binding intake interview protocol | At Stage 0, before classifying the request |
| `references/workflow-protocol.md` | State machine, transitions, resume protocol | Before starting any pipeline run |
| `references/handoff-templates.md` | Delegation templates for all 5 handoff types | Before each delegation |
| `references/delivery-template.md` | Blank delivery report format to fill in | At Stage 5 |
| `references/examples.md` | Worked runs: a filled delivery report, a gate manifest, a plateau escalation, a REVISE round | At Stage 5, and whenever an output shape is unclear |
| `references/skill-guide.md` | Canonical skill authoring guide (shared) | When user asks about skill structure |
| `intake-brief.yaml` | Trigger set, inputs, outputs, and acceptance contract | Confirming the pipeline's intake surface |
| `stub-contract.md` | Stage model, handoff rules, quality and delivery contract | Confirming stage boundaries and verdict vocabulary |
| `agent/agent-manifest.yaml` | Agent-mode delegation capabilities and fallback behavior | When invoked as a sub-orchestrator (e.g. by Admiral) |
| `skill-creator/SKILL.md` | Creation specialist capabilities and modes | Understanding what creator can do |
| `skill-reviewer/SKILL.md` | Review specialist capabilities and phases | Understanding what reviewer reports |

## Bundled Support Surface

The `skill-creator/` subtree is intentionally bundled with skill-maker because the
orchestrator delegates every substantive create, improve, optimize, eval, and package
operation there.

| Path | Purpose | Owner |
|------|---------|-------|
| `skill-creator/agents/grader.md` | Grades assertion results against skill outputs. | skill-creator eval mode |
| `skill-creator/agents/comparator.md` | Runs blind A/B comparisons for current vs. baseline outputs. | skill-creator eval mode |
| `skill-creator/agents/analyzer.md` | Explains why one output beat another and proposes improvement themes. | skill-creator improve mode |
| `skill-creator/assets/eval_review.html` | Static query-review template for trigger eval approval. | skill-creator optimize mode |
| `skill-creator/eval-viewer/` | Generates and serves reviewable eval-result reports. | skill-creator eval mode |
| `skill-creator/scripts/` | Validation, eval, benchmark aggregation, description optimization, reporting, and packaging utilities. | skill-creator modes |

Treat generated eval workspaces, packaged archives, benchmark outputs, and review
reports as run artifacts. Keep them outside this skill directory unless a script
explicitly writes a temporary file that is excluded from packaging.
