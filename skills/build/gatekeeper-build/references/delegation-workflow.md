# Delegation Workflow Reference

## Delegation Request Format

When gatekeeper-build identifies an issue that requires the originating skill to respond, construct a delegation request:

```markdown
## DELEGATION REQUEST

### Header
- **From**: gatekeeper-build
- **To**: [bob-the-builder | test-builder | security-builder | cross-check-build-confirm]
- **Challenge ID**: [GK-CH-001]
- **Challenge Type**: [existence | accuracy | completeness | proportionality | consistency]
- **Round**: [1 | 2]
- **Priority**: [Critical | Major | Minor]

### Context
- **Phase**: [1 — Implementation | 2 — Testing | 3 — Security Audit | 4 — Completeness Scan]
- **Finding Reference**: [Original finding ID if challenging an existing finding, or GAP-prefix for missing items]
- **Deliverable Section**: [Which part of the deliverable is being challenged]

### Challenge
[Precise, specific description of what is being challenged]

### Specific Question
[A single, answerable question the skill must address]

### Evidence Required
[Exactly what the skill must provide to resolve this challenge]

### Deadline
[If this blocks the pipeline, note urgency]
```

---

## Delegation Response Format

The originating skill responds with one of three resolutions:

```markdown
## DELEGATION RESPONSE

### Header
- **From**: [bob-the-builder | test-builder | security-builder | cross-check-build-confirm]
- **To**: gatekeeper-build
- **Challenge ID**: [GK-CH-001] (matching)
- **Round**: [1 | 2] (matching)

### Resolution
**[corrected | defended | withdrawn]**

### Evidence
[Specific evidence addressing the challenge question]

### Details

#### If Corrected:
- **What changed**: [Description of the fix or amendment]
- **Files modified**: [List of modified files]
- **Updated deliverable**: [Reference to the amended section]

#### If Defended:
- **Defense**: [Why the original work is correct as-is]
- **Evidence**: [Code references, logic explanation, or spec references supporting the defense]

#### If Withdrawn:
- **Reason**: [Why the original claim is being retracted]
- **Impact**: [How this affects the overall deliverable]
```

---

## Round Management

### Round 1: Initial Challenge

- Gatekeeper issues the challenge with clear question and evidence requirements
- Skill responds with correction, defense, or withdrawal
- If response is satisfactory → challenge resolved
- If response is unconvincing → proceed to Round 2

### Round 2: Follow-Up Challenge

- Gatekeeper issues a follow-up with specific rebuttal explaining why Round 1 response was insufficient
- Skill responds with additional evidence or concedes
- If response is satisfactory → challenge resolved
- If still unresolved → mark as Disputed

### After Round 2: Disputed Status

```markdown
## DISPUTED FINDING

### Challenge ID: [GK-CH-001]
### Finding: [Description]

### Gatekeeper Position:
[What the gatekeeper believes and why]

### Skill Position:
[What the skill defends and why]

### Evidence Summary:
| Round | Gatekeeper Argument | Skill Response |
|-------|-------------------|----------------|
| 1 | [argument] | [response] |
| 2 | [rebuttal] | [response] |

### User Action Required:
[Explain what decision the user needs to make]
```

**Rules for disputed findings:**
- No more than 2 Critical findings may be in Disputed status
- If more than 2 Critical findings are disputed, the verdict MUST be ESCALATE
- Disputed findings are fully documented for the user's judgment

---

## Batch Delegation Strategy

Group related challenges targeting the same skill into a single delegation:

### When to Batch

- Multiple challenges target the same file or module
- Challenges are of the same type (e.g., multiple existence challenges)
- Addressing one challenge may resolve others

### Batch Format

```markdown
## BATCH DELEGATION REQUEST

### Header
- **From**: gatekeeper-build
- **To**: [target skill]
- **Challenge Count**: [N]
- **Round**: [1]

### Challenges

#### GK-CH-001: [Title]
- **Type**: [existence]
- **Question**: [...]
- **Evidence Required**: [...]

#### GK-CH-002: [Title]
- **Type**: [accuracy]
- **Question**: [...]
- **Evidence Required**: [...]

#### GK-CH-003: [Title]
- **Type**: [completeness]
- **Question**: [...]
- **Evidence Required**: [...]

### Note
These challenges are related. Addressing GK-CH-001 may impact GK-CH-002.
Please address in order and note any dependencies.
```

### Batch Response

The skill responds to each challenge individually within a single response, noting any dependencies between resolutions.

---

## Escalation Procedures

### When to Escalate

| Condition | Escalation Target |
|-----------|------------------|
| Round 2 exhausted, still unresolved | Mark as Disputed, include in verdict |
| Fundamental misalignment with spec | ESCALATE verdict → build-management → user |
| Skill repeatedly fails same challenge type | ESCALATE → build-management for re-delegation |
| More than 2 Critical disputed findings | ESCALATE verdict → build-management → user |

### Escalation Format

```markdown
## ESCALATION NOTICE

### From: gatekeeper-build
### To: build-management
### Severity: [REVISE | ESCALATE]

### Summary
[Brief description of the persistent issue]

### Challenge History
| Challenge ID | Type | Rounds | Outcome |
|-------------|------|--------|---------|
| GK-CH-001 | existence | 2 | Disputed |
| GK-CH-005 | completeness | 2 | Unresolved |

### Recommendation
[Suggested course of action: re-delegate, re-scope, consult user]
```

---

## Resolution Tracking Ledger

Maintain a running ledger of all delegation activity:

```markdown
## Delegation Tracking Ledger

### Phase 1 Reviews
| ID | Type | Target | Question Summary | R1 | R2 | Status |
|----|------|--------|-----------------|-----|-----|--------|
| GK-CH-001 | existence | bob | Missing order endpoint | corrected | — | Resolved |
| GK-CH-002 | accuracy | bob | Validation logic incorrect | defended | — | Accepted |
| GK-CH-003 | completeness | bob | 2 of 8 endpoints missing | corrected | — | Resolved |

### Phase 2 Reviews
| ID | Type | Target | Question Summary | R1 | R2 | Status |
|----|------|--------|-----------------|-----|-----|--------|
| GK-CH-010 | accuracy | test | Assertion too broad | corrected | — | Resolved |
| GK-CH-011 | completeness | test | Auth tests missing | corrected | — | Resolved |

### Phase 3 Reviews
| ID | Type | Target | Question Summary | R1 | R2 | Status |
|----|------|--------|-----------------|-----|-----|--------|
| GK-CH-020 | accuracy | security | CWE mapping incorrect | corrected | — | Resolved |

### Phase 4 Reviews
| ID | Type | Target | Question Summary | R1 | R2 | Status |
|----|------|--------|-----------------|-----|-----|--------|
| GK-CH-030 | completeness | cross-check-build-confirm | Runtime evidence missing from CLEAN report | corrected | — | Resolved |

### Metrics
- Total challenges issued: [N]
- Resolved in Round 1: [N] ([%])
- Resolved in Round 2: [N] ([%])
- Disputed: [N]
- Challenge acceptance rate: [%] (corrected or upheld vs defended or withdrawn)
```
