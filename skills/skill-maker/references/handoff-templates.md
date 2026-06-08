# Handoff Templates — Skill Maker Pipeline

Delegation templates for all orchestrator → specialist handoffs. Use the appropriate
template for each stage transition.

## Contents

1. Create handoff
2. Review handoff
3. Improve handoff
4. Optimize handoff
5. Package handoff
6. Usage notes

---

## Template 1 — Create Handoff (Orchestrator → Skill Creator)

**Stage:** 1 (Create)
**Delegate to:** skill-creator — Create mode

```markdown
## Delegation: Create Skill

**Mode:** Create
**Execution mode:** Synchronous — return when draft is complete

### User intent
[Paste or summarize the user's skill request — what the skill should do, when it
should trigger, expected output format, constraints]

### Entry type
- [ ] New skill from scratch
- [ ] Harden existing skill at: [path]

### Context provided
[List any example files, reference docs, or prior conversation context the user
shared]

### Constraints
[Any explicit constraints — max file count, required workflow pattern, specific
environments to support, etc.]

### Expected deliverable
- SKILL.md with valid frontmatter (name, description)
- Supporting files as needed (references/, scripts/, agents/, examples/)
- Behavioral eval results (if evals were run)
- Skill directory path

### Return contract
Return the skill directory path and a brief summary of what was created. If evals
were run, include results. If blockers were encountered, describe them.
```

---

## Template 2 — Review Handoff (Orchestrator → Skill Reviewer)

**Stage:** 2 (Review)
**Delegate to:** skill-reviewer

```markdown
## Delegation: Review Skill

**Execution mode:** Synchronous — return when review report is complete

### Skill path
[Absolute path to skill directory]

### Iteration
[N] (1 = first review, 2+ = re-review after improvement)

### Previous scorecard
[If iteration > 1, paste or reference the previous scorecard so the reviewer can
track deltas. For iteration 1, write "N/A — first review".]

### Behavioral eval results
[If available from creator, paste summary. Otherwise: "No behavioral eval results
available for this iteration."]

### User overrides
[List any findings the user asked to skip or deprioritize. Reviewer should not
re-flag these unless new evidence emerges.]

### Expected deliverable
- Full scorecard (10 dimensions with scores and evidence)
- Findings list (F-01, F-02, ... prioritized by severity)
- Verdict: SHIP | ITERATE | BLOCKED
- Iteration history (if iteration > 1)

### Return contract
Return the complete review report. If the skill path is invalid or SKILL.md is
missing, return an error immediately rather than attempting a partial review.
```

---

## Template 3 — Improve Handoff (Orchestrator → Skill Creator)

**Stage:** 3 (Improve)
**Delegate to:** skill-creator — Improve mode

```markdown
## Delegation: Improve Skill

**Mode:** Improve
**Execution mode:** Synchronous — return when improvements are applied

### Skill path
[Absolute path to skill directory]

### Iteration
[N] (which improve cycle this is)

### Current scorecard
[Paste the full scorecard from the reviewer — all 10 dimensions with scores]

### Findings to address
[Paste the full findings list, prioritized: critical → major → minor]

### User guidance
[Any user overrides, priorities, or instructions:
- "Skip F-04"
- "Prioritize security findings"
- "Also add handling for edge case X"
- Or: "No specific guidance — address all findings in priority order"]

### Expected deliverable
- Updated skill files
- Summary of changes (which findings addressed, which deferred and why)
- Updated behavioral eval results (if re-run)

### Return contract
Return the changes summary. List each finding ID and whether it was addressed,
partially addressed, or deferred. If a finding cannot be addressed without user
input, note it as blocked.
```

---

## Template 4 — Optimize Handoff (Orchestrator → Skill Creator)

**Stage:** 4 (Optimize)
**Delegate to:** skill-creator — Optimize mode

```markdown
## Delegation: Optimize Description

**Mode:** Optimize
**Execution mode:** Synchronous — return when optimization is complete

### Skill path
[Absolute path to skill directory]

### Current description
[Paste the current frontmatter description — this is the 100/100 reviewed version]

### Existing eval queries
[If trigger eval queries exist from previous stages, paste them. Otherwise:
"No existing eval queries — generate new ones."]

### Expected deliverable
- Optimized `best_description`
- Trigger eval results (before/after accuracy scores)
- The eval query set used

### Return contract
Return the `best_description` and eval scores. If the optimization made no
improvement (original was already optimal), say so — do not force changes.
```

---

## Template 5 — Package Handoff (Orchestrator → Skill Creator)

**Stage:** 5 (Package)
**Delegate to:** skill-creator — Package mode

```markdown
## Delegation: Package Skill

**Mode:** Package
**Execution mode:** Synchronous — return when .skill file is created

### Skill path
[Absolute path to skill directory]

### Expected deliverable
- `.skill` file path
- Package contents list (files included)

### Return contract
Return the `.skill` file path and contents list. If packaging fails (missing files,
permission errors), return the error details.
```

---

## Usage notes

- **Fill in all bracketed placeholders** before delegating. Do not send templates with
  unfilled `[placeholders]`.
- **Paste artifacts inline** when they are short (< 50 lines). For longer artifacts,
  reference by file path.
- **Accumulate context across iterations** — each improve handoff should include the
  latest scorecard, not the first one.
- **User overrides are binding** — if the user says skip a finding, the orchestrator
  must exclude it from the improve handoff and tell the reviewer not to re-flag it.
