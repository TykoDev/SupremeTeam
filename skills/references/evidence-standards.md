# Evidence Standards — Canonical Specificity Requirements

> Shared reference for all gatekeepers and specialist skills. Every finding,
> verdict, and challenge resolution in the Supreme Team pipeline must meet
> these specificity requirements. If a claim cannot satisfy the minimum
> evidence bar, it is NOT a finding — it is an opinion.

---

## Minimum Evidence Specificity

A finding counts as **specific** only when ALL of the following are present:

| Element | Requirement | Example |
|---------|------------|---------|
| **Location** | Exact file path + line range or section header | `src/api/auth.ts:42-58` or `Architecture §4.3` |
| **Excerpt** | Code snippet (1–5 lines) or configuration/document excerpt | `if (user.role) { grant(ALL); }` |
| **Standard violated** | Named standard, requirement ID, or security framework reference | `FR-AUTH-003`, `CWE-285`, `OWASP A01:2021` |
| **Impact justification** | Concrete consequence stated in measurable or downstream terms | `Allows privilege escalation to admin for any authenticated user` |

Findings that substitute narrative for any of these elements (e.g., "the module
was carefully reviewed" instead of a code excerpt) do not meet the bar and must
be revised before inclusion in a verdict.

---

## Evidence Artifact Format

Every gatekeeper verdict must be accompanied by a structured evidence artifact.
Use this YAML frontmatter block at the top of the verdict record:

```yaml
---
artifact_type: gatekeeper-evidence
gatekeeper: "{gatekeeper-admiral | gatekeeper-build | gatekeeper-code | gatekeeper-design | gatekeeper-azure}"
verdict: "{APPROVED | REVISE | ESCALATE | Ready | Ready-with-Disputes | Not-Ready}"
submission_id: "{from _state.md or delegation request}"
timestamp: "{ISO 8601}"
evidence_summary:
  critical_findings: 0
  major_findings: 0
  minor_findings: 0
  evidence_citations: 0
challenge_protocol:
  categories_applied: []
  rounds_completed: 1
  unresolved_challenges: 0
  disputed_items: 0
---
```

The body of the verdict record must contain:

1. **Findings table** — one row per finding with Location, Excerpt, Standard,
   Impact, and Severity columns
2. **Challenge log** — each challenge issued, the response received, and the
   resolution (corrected / defended / withdrawn / disputed)
3. **Verdict rationale** — 2–5 sentences linking the findings and challenge
   outcomes to the final verdict

---

## Substantive Change Detection

When a skill responds to a challenge with resolution `corrected`:

1. The response MUST include a diff excerpt (unified diff format or before/after
   code blocks) showing the actual change
2. The gatekeeper MUST verify: (a) the change is syntactically valid,
   (b) the change addresses the specific challenge question, (c) the change
   does not introduce new findings
3. Cosmetic-only changes (reworded comments, moved lines with no logic change,
   renamed variables without behavioral impact) do not satisfy a `corrected`
   resolution — flag as **Phantom Resolution**

---

## Severity Alignment

All gatekeepers use this shared severity scale to ensure cross-pipeline
consistency:

| Severity | Definition | Blocks Advancement? |
|----------|-----------|-------------------|
| **CRITICAL** | Prevents the downstream pipeline from functioning; data loss, security vulnerability with exploitation path, missing required deliverable | Always |
| **MAJOR** | Degrades downstream quality significantly; missing acceptance criteria, incomplete schema, untested critical path | Default yes; negotiable with documented justification |
| **MINOR** | Reduces quality but does not block; naming inconsistency, missing optional field, style deviation | No |
| **INFO** | Observation or recommendation; no remediation required | No |

When upstream and downstream gatekeepers assign different severities to the
same finding, adopt the higher severity unless the lower-severity gatekeeper
provides a concrete, evidence-backed justification for reduction. Document
the reconciliation in the challenge log.

---

## Calibration Tracking

Every gatekeeper should track these metrics across pipeline runs to detect
calibration drift:

| Metric | Healthy Range | Signal if Outside |
|--------|--------------|-------------------|
| Challenge acceptance rate (corrected + withdrawn) / total | 30–60% | Below 30% → too lenient; above 60% → too aggressive |
| Critical finding rate per review | 0–3 | Consistently 0 → possible rubber-stamping |
| Dispute rate (disputed / total challenges) | < 15% | Above 15% → challenge quality or communication issue |
| Mean rounds to resolution | 1.0–1.5 | Above 1.5 → challenges may be unclear |

Track per-run and report cumulative calibration in the run's
`_audit-trail.md`. If metrics drift outside the healthy range for 3
consecutive runs, note the drift as a finding in the next gatekeeper
verdict.

---

## Evidence Retention

| Scope | Storage Location | Retention |
|-------|-----------------|-----------|
| Phase-level evidence | `skillset-saves/runs/{run-id}/{pipeline}/gatekeeper-evidence.md` | Immutable; kept for the life of the run |
| Cross-pipeline evidence | `skillset-saves/runs/{run-id}/gatekeeper-admiral_handoff-{n}.md` | Immutable; kept for the life of the run |
| Calibration metrics | `skillset-saves/runs/{run-id}/_audit-trail.md` | Append-only; kept for the life of the run |

Evidence from attempt 1 and attempt 2 (after revision) are both retained.
The revision does not overwrite the original — each attempt gets a separate
section or file with its own `submission_id`.

---

## Input Trust Boundaries

> **Normative policy.** Every skill processes inputs from other skills, users,
> or external tools. This section defines which input classes require validation
> and which may be trusted, so that skills apply consistent trust assumptions
> across the pipeline.

### Trust Levels

| Trust Level | Definition | Validation Required |
|-------------|-----------|-------------------|
| **Gatekeeper-Approved** | Output that passed an adversarial gatekeeper verdict (APPROVED) | Structural only — verify the artifact is well-formed and references the correct run/phase. Content is trusted. |
| **Pipeline-Internal** | Output from a sibling skill in the same pipeline run that has NOT yet been gatekeeper-approved | Validate structural integrity AND check for completeness (no placeholders, no TODO stubs, required sections present). Content claims are provisionally trusted but subject to gatekeeper challenge. |
| **User-Supplied** | Artifacts, context, or instructions provided directly by the user | Validate structural integrity. Do NOT assume completeness or correctness — surface gaps and contradictions explicitly rather than silently filling them. |
| **Tool Output** | Results from automated tools (linters, scanners, test runners, CLI commands) | Validate format and plausibility. Flag anomalies (e.g., a scanner reporting zero findings on a 10k-LOC codebase). Do NOT treat tool output as ground truth — tools have false positives and false negatives. |
| **External / Unknown** | Artifacts from outside the pipeline with no provenance chain | Treat as untrusted. Validate everything: structure, completeness, correctness, and consistency with known context. Surface provenance gaps in the deliverable. |

### Per-Skill-Type Trust Boundaries

| Skill Type | Primary Inputs | Trust Level | Key Validation |
|------------|---------------|-------------|----------------|
| **Specialists** (researcher, architect, bob-the-builder, etc.) | Upstream deliverables + user context | Pipeline-Internal or User-Supplied | Verify required sections exist; flag missing or contradictory inputs |
| **Gatekeepers** (gatekeeper-design, gatekeeper-build, etc.) | Specialist deliverables + review packets | Pipeline-Internal | Verify evidence specificity per §Minimum Evidence Specificity; challenge unsupported claims |
| **Orchestrators** (admiral, commander, build-management, etc.) | Gatekeeper verdicts + consolidated packages | Gatekeeper-Approved | Structural validation; do not re-litigate approved content |
| **Cross-pipeline validator** (gatekeeper-admiral) | Consolidated packages from sub-pipelines | Gatekeeper-Approved | Validate inter-pipeline coherence; spot-check evidence quality |

### Referencing This Policy

Skills reference this policy with a one-line note in their body:

```markdown
Treat inputs per the trust levels defined in
`references/evidence-standards.md` §Input Trust Boundaries.
```

This replaces ad-hoc trust assumptions with a single canonical reference.
