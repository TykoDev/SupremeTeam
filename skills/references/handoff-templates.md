# Unified Delegation Protocol

> **Scope**: Universal templates used by ALL sub-orchestrators (commander,
> build-management, code-chief, azure-provisioner) for delegating to specialist
> skills and submitting to per-pipeline gatekeepers. For admiral-specific
> cross-pipeline delegation templates, see `admiral/references/handoff-templates.md`.

> **Placeholder notation**: Square-bracket tokens in this file are template
> placeholders to be replaced during delegation construction. The authoritative
> persisted-path format in `save-protocol.md` uses brace variables such as
> `{run-id}`.

## Universal Handoff Template

All sub-orchestrators (`commander`, `build-management`, `code-chief`) MUST use this unified delegation template format when delegating to their respective specialist skills. This ensures `gatekeeper-admiral` can reliably parse metadata across the entire `Supreme_Team`.

```markdown
## [ORCHESTRATOR] DELEGATION: Phase [N] — [Phase Name]

### Unified Metadata Header
- **Project**: [project-slug]
- **Pipeline Mode**: [full | design-only | build-only | review-only]
- **Target Area**: [Review Target / Implementation Scope / Scope Classification]
- **Upstream Context**: [List of approved upstream deliverables relevant to this phase]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/[pipeline]/phase-[N]_[skill-name]/
- **Persistence active**: [yes/no]
- **Context tier**: [1|2|3|4]
- **Artifact mode**: [inline|reference|best-effort-inline]
- **Standalone fallback ref**: [path to standalone-context.md or "none"]
- **Skipped upstream stages**: [none or comma-separated list of skipped pipelines]

### Phase Instruction
[Explicit instructions for the specialist skill. Must include what artifacts to produce and specific quality gates.]

### Expected Deliverables / Return Contract
[Bulleted list of expected markdown documents or code artifacts. Explicitly state the Specialist MUST return control to the Orchestrator and NOT submit directly to any Gatekeeper.]

### Structured Summary Block (For Pipeline Consumption)
[Optional: A machine-readable YAML/Markdown block if the orchestrator requires summarized output (e.g., Code-Chief finding summaries)]
```

## Universal Gatekeeper Submission Template

When an orchestrator submits a package to its pipeline gatekeeper (`gatekeeper-design`, `gatekeeper-build`, `gatekeeper-code`), the following format MUST be used:

```markdown
## GATEKEEPER-[PIPELINE] REVIEW REQUEST

### Phase & Origin
- **Phase**: [Phase number and name]
- **Source Skill**: [Specialist skill name]
- **Revision Attempt**: [N]

### Submission Inventory
[List of deliverables being submitted for adversarial validation]

### Unified Context
- **Target Area**: [Scope or Review Target]
- **Upstream Foundation**: [Approved deliverables that dictate the constraints for this work]

### Orchestrator Instruction
Execute the `gatekeeper-[pipeline]` adversarial validation protocol against this submission.
Apply all challenge types. Issue an explicit verdict: APPROVED, REVISE, or ESCALATE.
```
