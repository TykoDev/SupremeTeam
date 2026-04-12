# The Gatekeeper Pattern

Supreme Team includes five gatekeepers operating at different levels of the
pipeline. Every deliverable must earn approval — it is never assumed.

## Gatekeeper Hierarchy

| Gatekeeper | Level | What It Validates |
|-----------|-------|-------------------|
| **gatekeeper-design** | Per-phase (design) | Design specs, architecture decisions, requirement completeness |
| **gatekeeper-build** | Per-phase (build) | Production code, test quality, security audit accuracy |
| **gatekeeper-code** | Consolidated (review) | Review report accuracy, finding evidence, severity calibration |
| **gatekeeper-azure** | Per-phase (azure) | Azure deliverable accuracy, configuration correctness, deployment safety |
| **gatekeeper-admiral** | Cross-pipeline | Handoff completeness, cross-pipeline alignment, end-to-end coherence |

## How They Work

Three per-phase gatekeepers (**design**, **build**, **azure**) validate work
within their sub-pipeline at each phase boundary. A specialist completes its
deliverable, and the gatekeeper challenges it before the next specialist begins.

**Gatekeeper-code** uses a **consolidated** pattern — it validates the entire
review suite once after all six specialists complete, rather than after each
individual specialist.

**Gatekeeper-admiral** validates at the boundaries between sub-pipelines,
ensuring the output of one pipeline is suitable input for the next.

## Adversarial Philosophy

All gatekeepers share the same core principle: **approval is earned, not given**.
A review that finds nothing is the most suspicious review of all.

Each gatekeeper uses a structured challenge protocol:
- Identifies gaps, contradictions, and unsupported claims
- Requires evidence-backed responses to challenges
- Enforces maximum revision cycles before escalation to the user
- Documents all verdicts for audit trail traceability

## Verdict Routing

For every gatekeeper submission:

| Verdict | Action |
|---------|--------|
| **APPROVED** | Advance to the next phase or pipeline stage |
| **REVISE** | Return to the same sub-orchestrator with specific findings to address |
| **ESCALATE** | Surface the blocking issue to the user for a decision |

Maximum revision cycles per handoff: **2**. If still failing after 2 attempts,
the issue is marked as DISPUTED and escalated with both positions documented.
