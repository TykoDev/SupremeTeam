# Delegation Workflow Reference — Gatekeeper Azure

## Delegation Request Format

When gatekeeper-azure identifies an issue that requires a specialist response,
construct a delegation request:

```markdown
## DELEGATION REQUEST

### Header
- **From**: gatekeeper-azure
- **To**: [azure-planner | azure-architect | azure-configurator | azure-deployer | azure-verifier]
- **Challenge ID**: [GK-AZ-CH-001]
- **Challenge Type**: [existence | accuracy | completeness | proportionality | consistency]
- **Round**: [1 | 2]
- **Priority**: [Critical | Major | Minor]

### Context
- **Phase Gate**: [1 — Planning | 2 — Architecture | 3 — Configuration | 4 — Deployment | 5 — Verification]
- **Finding Reference**: [Original finding ID, or GAP-prefix for missing items]
- **Deliverable Section**: [Which part of the deliverable or package is challenged]

### Challenge
[Precise description of what is being challenged]

### Specific Question
[A single answerable question]

### Evidence Required
[Exactly what the skill must provide]

### Deadline
[If this blocks the pipeline, note urgency]
```

---

## Delegation Response Format

The originating skill responds with one of three resolutions:

```markdown
## DELEGATION RESPONSE

### Header
- **From**: [azure-planner | azure-architect | azure-configurator | azure-deployer | azure-verifier]
- **To**: gatekeeper-azure
- **Challenge ID**: [GK-AZ-CH-001]
- **Round**: [1 | 2]

### Resolution
**[corrected | defended | withdrawn]**

### Evidence
[Specific evidence addressing the challenge]

### Details

#### If Corrected:
- **What changed**: [Description of the fix]
- **Resources modified**: [List of affected resources or artifacts]
- **Updated deliverable**: [Reference to the amended section]

#### If Defended:
- **Defense**: [Why the original deliverable is correct]
- **Evidence**: [Docs or reasoning supporting the defense]

#### If Withdrawn:
- **Reason**: [Why the original claim is retracted]
- **Impact**: [Downstream effect]
```

---

## Round Management

### Round 1: Initial Challenge

- Gatekeeper-azure issues the challenge with explicit evidence requirements
- The target skill responds with correction, defense, or withdrawal

### Round 2: Follow-Up Challenge

If Round 1 is unconvincing:

- Gatekeeper issues a focused rebuttal
- The skill must provide stronger evidence or correct the issue

### After Round 2: Disputed Status

If still unresolved:

1. Mark the finding **Disputed**
2. Document both positions
3. Return the dispute to azure-provisioner for escalation
4. Record the user's decision in the traceability record

---

## Phase 5 Final Sweep Routing

During the Phase 5 exit gate, the final adversarial sweep may identify issues in
any earlier Azure phase. In that case:

1. Gatekeeper-azure targets the **earliest responsible skill**
2. Azure-provisioner rewinds to that phase
3. All downstream phases after the rewound phase are re-run and re-gated
4. Consolidation remains blocked until the replayed phases are approved

Example:

- Final sweep finds over-privileged RBAC from Phase 3
- Gatekeeper routes the challenge to `azure-configurator`
- Azure-provisioner rewinds to Phase 3
- Phases 4 and 5 are replayed after the fix

---

## Batch Delegation

Batch related findings only when they target the same skill and same effective
phase context.

### When to Batch

- Multiple findings in the same deliverable section
- Multiple accuracy or completeness issues on the same resource family
- Multiple final-sweep findings that all belong to the same upstream skill

### When Not to Batch

- Findings spanning different target skills
- Critical blockers that need immediate isolated resolution
- Findings that imply different rewind points in the state machine

---

## Escalation Path

```text
gatekeeper-azure -> azure-provisioner -> user
```

Gatekeeper-azure never escalates directly to the user.

---

## Revision Tracking

Track all delegation rounds per finding:

| Phase Gate | Finding ID | Target Skill | Round 1 | Round 2 | Final Status |
|-----------|------------|--------------|---------|---------|--------------|
| 2 | GK-AZ-CH-001 | azure-architect | Corrected | - | Resolved |
| 5 | GK-AZ-CH-004 | azure-configurator | Defended | Disputed | Escalated |
| 5 | GK-AZ-CH-007 | azure-verifier | Withdrawn | - | Resolved |

This tracking is included in the gatekeeper verdict and forwarded to
azure-provisioner for the Azure pipeline record.
