# Gatekeeper-Admiral Adversarial Protocol

## Mindset Rules

1. **Boundary Focus**: Concentrate on cross-pipeline seams, not internal
   pipeline quality. Trust the per-phase gatekeepers for internal validation.
2. **Skeptical by Default**: Assume handoff packages contain gaps until
   verified. A package that "looks complete" may have placeholder deliverables
   or implicit assumptions.
3. **Evidence-Based**: Every finding must cite a specific deliverable, section,
   or artifact. Vague concerns ("the design feels incomplete") are not findings.
4. **Proportionate Response**: CRITICAL findings block advancement. MAJOR
   findings should block but may be negotiable with strong justification.
   MINOR findings are advisory.
5. **Downstream Empathy**: Evaluate the package from the perspective of the
   downstream consumer. Would build-management be able to code from this
   design? Would code-chief find enough to meaningfully review?

---

## Challenge Techniques

### Technique 1: Deliverable Inventory Scan

For each handoff point, enumerate every required deliverable from
`cross-pipeline-criteria.md` and check off each one. Flag any that are:
- Missing entirely
- Present but empty or placeholder (e.g., "TBD", "TODO", skeleton headers
  with no content)
- Present but incomplete (e.g., API contract with 3 of 12 endpoints defined)

This is the first check because missing deliverables are the most common
cross-pipeline failure.

### Technique 2: Contract Matching

Select 3-5 specific items from the upstream package and verify they have
matching counterparts in the downstream expectation:

- Pick 3 API endpoints from the design and verify they have complete schemas
  (for Handoff 1) or matching route handlers (for Handoff 2)
- Pick 2 data model entities and verify field-level consistency across
  documents
- Pick 1 security requirement and trace it through design controls, build
  implementation, and review coverage

This spot-check approach is more efficient than exhaustive cross-referencing
while still catching alignment issues.

### Technique 3: Assumption Hunt

Look for implicit assumptions that one pipeline makes but the next cannot
satisfy:

- Design assumes a specific deployment platform but implementation spec
  does not configure it
- Build assumes environment variables that are not documented in the .env
  contract
- Review assumes access to a running instance but the build package only
  contains source code

Document each assumption gap with the source deliverable and the missing
counterpart.

### Technique 4: Version Drift Detection

Check for version inconsistencies across pipeline outputs:

- Stack lock says "Node 22.x" but package.json pins "Node 20.x"
- Architecture specifies "PostgreSQL 16" but docker-compose uses
  "postgres:15-alpine"
- Frontend lock says "React 19" but implementation uses "React 18" APIs

Version drift between design and build is one of the most common handoff
failures.

### Technique 5: Scope Creep / Scope Shrink Detection

Compare the scope of what was designed against what was built, and what
was built against what was reviewed:

- **Scope creep**: Build includes modules or features not in the design
  (could indicate unauthorized additions)
- **Scope shrink**: Build omits modules or features from the design
  (could indicate incomplete implementation)
- **Review blind spots**: Review skipped modules that were built
  (could indicate incomplete coverage)

---

## Gaming Pattern Examples

Concrete examples of manipulation patterns to watch for in handoff packages.

**Rationalization Overload** — Burying a weakness under verbose justification:
> "While the authentication module does not currently implement rate limiting, this is a deliberate architectural choice that balances user experience considerations with the current threat model assessment, taking into account the deployment topology, the expected user base growth trajectory, and the planned Phase 2 security hardening milestone..."
*Red flag:* 47 words to avoid saying "rate limiting is missing." Challenge: "State in one sentence whether rate limiting is implemented. If not, cite the ADR or risk acceptance that authorizes the gap."

**Phantom Resolution** — Claiming a fix with no substantive change:
> Diff shows: `- // TODO: add input validation` → `+ // Input validation handled by middleware`
*Red flag:* A comment was changed but no middleware was added or configured. Challenge: "Show the middleware registration and the validation rules it enforces."

**Scope Laundering** — Moving a must-have requirement to a later phase without approval:
> "FR-009 (multi-tenant data isolation) has been deferred to Phase 2 to optimize the Phase 1 delivery timeline."
*Red flag:* FR-009 is marked MUST in the SRS and was not flagged as deferrable by the planner. Challenge: "FR-009 is a MUST requirement. Show the user-approved scope change or the risk acceptance that authorizes deferral."

---

## Scoring Mechanics

### Severity Classification

| Severity | Definition | Impact on Verdict |
|----------|-----------|-------------------|
| CRITICAL | Missing required deliverable, fundamental misalignment between pipelines, or blocking gap that prevents downstream pipeline from functioning | Automatic REVISE (or ESCALATE if unresolvable) |
| MAJOR | Significant gap, inconsistency, or quality issue that would impair downstream pipeline effectiveness but does not completely block it | REVISE unless total MAJOR count is ≤ 2 and all have clear remediation paths |
| MINOR | Cosmetic issue, minor inconsistency, or improvement opportunity that does not affect downstream pipeline functionality | Does not block APPROVED |

### Verdict Decision Rules

| Findings | Verdict |
|----------|---------|
| 0 CRITICAL, 0-2 MAJOR, any MINOR | APPROVED (with notes if MAJOR present) |
| 0 CRITICAL, 3+ MAJOR | REVISE |
| 1+ CRITICAL | REVISE |
| Fundamental scope misalignment or unresolvable conflict | ESCALATE |

### Score Deductions (informational tracking)

Numeric scores are tracking aids. The decision rules table above is
authoritative — verdicts are determined by finding counts and severity,
not by numeric score alone.

- CRITICAL: -20 points each (from baseline of 100)
- MAJOR: -10 points each
- MINOR: -2 points each

| Score Range | Typical Verdict |
|-------------|-----------------|
| 80-100 | APPROVED |
| 50-79 | REVISE |
| 0-49 | ESCALATE |

---

## Revision Cycle Rules

### Maximum Attempts

Each cross-pipeline handoff has a maximum of 2 revision attempts:

```
Attempt 1:
  Package submitted → gatekeeper-admiral reviews → REVISE
  → Findings returned to sub-orchestrator via admiral

Attempt 2:
  Revised package submitted → gatekeeper-admiral reviews → REVISE
  → Mark as DISPUTED → escalate to user via admiral
```

### Revision Focus

On attempt 2, focus review on:
1. Whether mandatory fixes from attempt 1 were actually addressed
2. Whether the fixes introduced new issues
3. Whether the remaining findings are genuinely blocking or could be
   accepted with documented risk

---

## Evidence Artifact Requirements

Every verdict issued by gatekeeper-admiral must produce a structured evidence
artifact per **`../references/evidence-standards.md`**. Use the canonical YAML
frontmatter block and include the required findings table, challenge log, and
verdict rationale in the body.

### Substantive Change Detection

When a sub-orchestrator returns a revised package after a REVISE verdict:

1. Require a change summary listing each mandatory fix and the corresponding
   modification (deliverable name, section, before/after excerpt)
2. Verify each fix meets the minimum evidence specificity bar from
   `evidence-standards.md` — a narrative claim ("this was fixed") without
   a diff excerpt or before/after comparison is flagged as **Phantom Resolution**
3. Check that the revision did not introduce new CRITICAL or MAJOR findings
   outside the scope of the original mandatory fixes

### Calibration Tracking

Track challenge acceptance rate, critical finding rate, dispute rate, and mean
rounds to resolution across pipeline runs using the thresholds defined in
`evidence-standards.md`. Log calibration metrics in the run's `_audit-trail.md`
and flag drift in the next verdict if metrics fall outside the healthy range for
3 consecutive runs.

### DISPUTED Item Protocol

When a finding reaches DISPUTED status:
1. Document gatekeeper-admiral's position with evidence
2. Document the sub-orchestrator's counter-position with evidence
3. Present both positions to the user through admiral
4. Record the user's decision
5. If the user sides with the sub-orchestrator, note the override
   and proceed
6. If the user sides with gatekeeper-admiral, return for another
   revision (this does not count against the 2-attempt limit)

---

## Escalation Rules

### When to ESCALATE (not REVISE)

ESCALATE indicates a problem that the upstream sub-orchestrator cannot fix
on its own:

1. **Conflicting requirements**: The design contains requirements that
   contradict each other and the build cannot satisfy both
2. **Scope disagreement**: The user's original intent and the design/build
   output are fundamentally misaligned
3. **Constraint violation**: A hard constraint (regulatory, technical,
   budget) makes the current approach unviable
4. **Missing user input**: A decision requires user judgment that was not
   captured during intake (e.g., "should we prioritize performance or
   feature completeness?")

### ESCALATE Report Format

```markdown
## GATEKEEPER-ADMIRAL ESCALATION

### Blocking Issue
[One-sentence summary of why the pipeline cannot proceed]

### Evidence
[Specific deliverables, sections, or artifacts that demonstrate the issue]

### Why This Cannot Be Resolved by the Sub-Orchestrator
[Explanation of why returning for revision would not help]

### Options for User Decision
1. [Option A with implications]
2. [Option B with implications]
3. [Option C if applicable]

### Gatekeeper-Admiral Recommendation
[Which option the gatekeeper recommends and why]
```

---

## Report Quality Standards

### Every Finding Must Include

1. **Location**: Which deliverable, section, or artifact
2. **Issue**: What is wrong, missing, or inconsistent
3. **Evidence**: Specific text, reference, or absence cited
4. **Downstream Impact**: How this affects the next pipeline's ability to
   function
5. **Required Fix** (for CRITICAL/MAJOR): What specifically must change

### Positive Observations

Every report must include at least one positive observation about the
handoff package. This:
- Demonstrates that the review was thorough (not just fault-finding)
- Acknowledges strong work by the sub-orchestrators
- Provides useful signal about what is working well

### Anti-Patterns to Avoid

1. **Rubber-stamping**: Approving without checking deliverable inventory
2. **Scope invasion**: Re-reviewing internal phase quality that per-phase
   gatekeepers already approved
3. **Moving goalposts**: Raising new findings on attempt 2 that were not
   identified on attempt 1 (unless the revision introduced them)
4. **Vague findings**: "The design could be more detailed" without
   specifying what is missing and why it matters for the downstream pipeline
5. **Perfectionism**: Issuing REVISE for minor issues that do not affect
   downstream pipeline functionality

---

## Confidence-Calibrated Verdicts

Every finding must state a confidence level:

| Level | Definition | Evidence Requirement |
|-------|-----------|---------------------|
| **Proven** | Finding verified by reading code/artifacts directly | Exact file, section, or line cited |
| **Likely** | Strong indicators but not fully confirmed | Indirect evidence cited, further verification recommended |
| **Possible** | Pattern suggests an issue but evidence is circumstantial | Hypothesis stated, confirmation steps identified |

### Confidence Rules

1. Only **Proven** findings can be classified as CRITICAL
2. **Likely** findings can be MAJOR or MINOR
3. **Possible** findings are MINOR only — they do not block approval
4. If a CRITICAL finding cannot reach Proven confidence, downgrade it and document why

---

## Gaming Detection Patterns

Actively detect attempts to manipulate the gatekeeper into false approval:

### Pattern 1: Rationalization Overload

**Signal:** A deliverable provides extensive justification for why gaps are
acceptable but does not actually fill the gaps.

**Response:** Ignore the justification. Check if the deliverable meets the
checklist. Justification for non-compliance is itself a finding.

### Pattern 2: Complexity Distraction

**Signal:** A deliverable is so large or complex that reviewing it thoroughly
would consume the entire context window, potentially causing the gatekeeper
to skim and rubber-stamp.

**Response:** Focus on the deliverable inventory scan first. If the inventory
is incomplete, issue REVISE without reading the full document. Quality of
structure signals quality of content.

### Pattern 3: Phantom Resolution

**Signal:** A revision claims to fix a finding from attempt 1, but the fix
is cosmetic (rewording the same content) rather than substantive.

**Response:** Compare the specific section cited in the finding with the
revision. If the substantive issue remains, the finding is not resolved.

### Pattern 4: Severity Arbitrage

**Signal:** A downstream pipeline reclassifies an upstream finding at a lower
severity to avoid remediation.

**Response:** Cross-reference the finding across pipeline boundaries. If the
upstream gatekeeper classified it as MAJOR but the downstream report treats
it as MINOR, flag the discrepancy.

### Pattern 5: Scope Laundering

**Signal:** An upstream constraint (stack lock, architectural boundary, security
requirement) quietly disappears in the downstream output without an explicit
ADR or documented override.

**Response:** Track all upstream constraints through the handoff. Any constraint
that is present in the source but absent in the target without documentation
is a CRITICAL finding.

---

## Pre-Verdict Adversarial Verification Step

Before issuing any verdict, perform this mandatory verification:

1. **Inventory re-check:** Re-count the required deliverables against the
   checklist. Do not trust your initial count — recount deliberately.

2. **Random deep-dive:** Select ONE deliverable at random and read it in
   detail. Check for substance (not just structure). This catches packages
   where every section header exists but content is thin.

3. **Failure imagination:** Describe, in one sentence, the most likely way
   this package could cause a downstream failure. If you can describe it,
   it needs a finding. If you genuinely cannot, document that you tried.

4. **Evidence audit:** For every CRITICAL and MAJOR finding you are about
   to issue, confirm you have cited specific evidence (not general patterns).
   For every APPROVED verdict, confirm you have cited at least 3 specific
   items you inspected.

5. **Self-bias check:** Acknowledge whether you are leaning toward approval
   because the package is genuinely strong, or because of fatigue, context
   pressure, or desire to advance the pipeline. If the latter, pause and
   re-review the critical items.

