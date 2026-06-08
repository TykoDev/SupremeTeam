# The Gatekeeper Pattern

Supreme Team enforces quality through **four adversarial gatekeepers** at two
levels, backed by a shared deterministic gate engine. Every deliverable must
earn approval — it is never assumed.

## Gatekeeper Hierarchy

| Gatekeeper | Level | What It Validates |
|-----------|-------|-------------------|
| **gatekeeper-design** | Per-phase (design) | Design specs, architecture decisions, design-system coherence, requirement completeness (design→build boundary) |
| **gatekeeper-build** | Per-phase (build) | Production code, test quality, security hardening evidence, completeness claims (build→review boundary) |
| **gatekeeper-code** | Consolidated (review) | Review report accuracy, finding evidence, severity calibration (review→delivery boundary) |
| **gatekeeper-admiral** | Cross-stage | Handoff completeness, cross-stage alignment, revision lineage, end-to-end coherence |

A fifth adversarial gate, **skill-reviewer**, sits inside the skill-maker
pipeline. It scores a skill 0–100 across a 10-dimension rubric and returns a
prioritized fix list; it does not apply fixes. Admiral maps skill-maker verdicts
onto the standard model (`SHIP` → APPROVED, `ITERATE` → REVISE, `BLOCKED` →
ESCALATE).

## How They Work

The three per-phase gatekeepers (**design**, **build**, **code**) validate work
within their sub-pipeline at each phase boundary. A specialist completes its
deliverable, and the gatekeeper challenges it before the next specialist begins.
**gatekeeper-code** uses a **consolidated** pattern — it validates the entire
review suite once after all specialists complete.

**gatekeeper-admiral** validates at the boundaries between stages, ensuring the
output of one stage is suitable input for the next. It reuses a prior verdict
only when the package revision is unchanged, and rewinds downstream work when an
upstream approval drifts.

## Deterministic Gate Engine

Each `gatekeeper-*` skill ships a thin `scripts/check.py` that declares only its
boundary's required-artifact manifest and calls a shared, stdlib-only engine at
`skills/harness/gatekeeper/_gatecheck.py`. The engine turns the *mechanically
checkable* parts of validation into a deterministic pass so the skills no longer
re-derive them as prose each run.

| Deterministic (engine) | Judgment (gatekeeper skill) |
|------------------------|-----------------------------|
| Required artifacts present for the boundary | Whether a present artifact is *substantively* adequate |
| Single-revision lineage; one submission id | Whether a contradiction across artifacts is real |
| Skip records carry the save-protocol fields | Whether a skip is *justified* for the scope |
| Blocked-phrase / contamination markers absent | Whether prose overclaims completion |
| Idempotency vs. a prior verdict (drift) | Whether a scope change warrants ESCALATE |

The engine reports **facts** (`PASS` / `FAIL` / `UNCHECKED`), never the verdict —
the skill decides, citing the report. Unlike the hooks (which **fail open**), the
gate engine **fails loud**: a gate that cannot prove a package clean must never
silently approve it (internal error → exit `2`, blocking failure → non-zero exit).
See `skills/harness/gatekeeper/README.md`.

## Adversarial Philosophy

All gatekeepers share the same core principle: **approval is earned, not given**.
A review that finds nothing is the most suspicious review of all.

Each gatekeeper:
- Identifies gaps, contradictions, and unsupported claims
- Requires evidence-backed responses to challenges
- Reports findings with the shared four-tier severity model (`critical`,
  `major`, `minor`, `info`)
- Enforces a maximum revision-cycle cap before escalation
- Documents every verdict for audit-trail traceability
- Rejects packages that add a cross-cutting constraint without naming its
  lifecycle layer, or that place it later than where it is enforceable
  (`skills/harness-doctrine.md` §5)

## Verdict Routing

| Verdict | Action |
|---------|--------|
| **APPROVED** | Advance to the next phase or stage |
| **REVISE** | Return to the owning sub-orchestrator with specific findings to address |
| **ESCALATE** | Surface the blocking issue to the user for a decision |

Maximum cross-stage revision cycles per boundary: **2**. If still failing after
2 attempts, the boundary is marked DISPUTED and escalated with both positions
documented. Remediation is always pushed back to the owning sub-orchestrator —
gatekeepers never edit a package locally.
