---
name: gatekeeper-build
description: >-
  Validates build-phase deliverables, hardening evidence, and completeness claims
  before code work can advance. Use when the user asks to validate the build
  deliverable, review build phase output, check build readiness, challenge this
  build packet, or verify whether implementation evidence is ready for review —
  even when they only ask "is the build ready?". Gates the build→review boundary
  only; defers the other gates to `design/gatekeeper-design`,
  `review/gatekeeper-code`, and `gatekeeper-admiral`.
version: 1.0.0
---

# Gatekeeper Build

## Purpose

Validate build-phase deliverables, hardening evidence, and completeness claims before code work can advance.

## Use This Skill When

Use this gate at the **build→review boundary** — deciding whether build evidence can advance to review:

- "validate the build deliverable" / "check build readiness" — confirm implementation, test, and hardening evidence is present
- "review build phase output" — verify completeness claims against what was actually built
- "challenge this build packet" — pressure the evidence rather than the intent behind it

Route elsewhere for a different boundary: the design→build gate (`design/gatekeeper-design`), the review→delivery gate (`review/gatekeeper-code`), or the cross-stage delivery gate (`gatekeeper-admiral`).

## Inputs

- Build packet with implementation diff, test-builder evidence, security-builder evidence, health-check results, and completeness certification.
- Pipeline context from `build/build-management` with approved design scope, revision delta, skip records, and deterministic pre-check output.
- Prior build-gate verdict when the same package is being resubmitted for idempotency or drift review.

## Outputs

- Build-readiness verdict with `APPROVED`, `REVISE`, or `ESCALATE`, tied to the implementation revision and build evidence set.
- Build findings naming stale or missing implementation diffs, test evidence, security hardening, health checks, completeness claims, or vendored-surface treatment.
- Required remediation instructions for `build/build-management`, including which build specialist must repair the packet before review can consume it.

## Deterministic Pre-Check (script)

Run the deterministic gate engine **before** applying judgment:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

**Input validation (required before invoking):** `<package-dir>` is an untrusted input sourced from build context. Before passing it to the script, confirm that it resolves to an existing directory inside the expected build/package working area. Reject any path that does not exist, falls outside the designated working area, or contains traversal sequences (`../`). If the path fails validation, return `ESCALATE` and name the invalid path rather than invoking the script. This prevents path-injection into the gate engine from a malformed or manipulated build context. `scripts/check.py` enforces the same guard in code as a backstop — it resolves `<package-dir>`, requires an existing directory inside the working tree, and exits 2 (without running the gate) on a missing, non-directory, or out-of-tree path.

`scripts/check.py` declares this boundary's required-artifact manifest (implementation diff, test-builder evidence, security-builder outcome, cross-check-build-confirm certification, build-gate lineage) and calls the shared engine at `../../harness/gatekeeper/_gatecheck.py`. It mechanizes package shape, single-revision lineage, skip-record completeness, the blocked-phrase scan, idempotency drift against `--prior`, and harness-doctrine §5 structure, returning `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status`. It **never emits a verdict**: apply judgment to the `FAIL` and `UNCHECKED` findings — and to vendoring/scope questions the script cannot decide — to choose `APPROVED` / `REVISE` / `ESCALATE`. The script fails loud — a blocking failure exits non-zero, an internal error exits 2. See `../../harness/gatekeeper/README.md`.

## Workflow

1. Run `scripts/check.py` to verify the build-phase packet includes the implementation diff summary, test-builder evidence, security-builder outcome, cross-check-build-confirm certification, and gatekeeper-build lineage for the current revision.
2. Cross-check hardening evidence and completeness claims against the actual changed modules, test reruns, unresolved findings, migrations, configuration edits, and any generated or third-party surfaces.
3. Decide the narrowest justified verdict and return only the mandatory changes build-management must make before the packet can advance to review.
4. Preserve verdict history across build resubmissions and flag any silent drift between the code surface, evidence set, and completeness certification.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Harness-doctrine citation**: When the package adds or changes a cross-cutting runtime intervention, check it against `../../harness-doctrine.md` §5 and cite the violated section by number in the verdict.

## Verdict Model

- **APPROVED**: The package is ready to advance with its current evidence.
- **REVISE**: The package can progress after specific mandatory changes.
- **ESCALATE**: The package cannot advance without external judgment or a broader scope decision.

## Evidence Standard

- Tie every major and critical finding to a concrete file, artifact, or observable behavior.
- Reject claims of completion that are not backed by a visible deliverable.
- Preserve contradictory evidence instead of normalizing it away.

## Skip Rule

Do not skip gate evaluation; only reuse a prior verdict when the exact package revision is unchanged.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The completeness certification says the build is clean, but the attached tests or security evidence are missing or older than the implementation revision | Reject the package and require a coherent evidence set tied to the submitted code revision. |
| Generated or vendored code appears in the package without ownership, scan notes, or change rationale | Return `REVISE`, isolate the affected files, and require explicit treatment of non-first-party surfaces. |
| A claimed build fix quietly widens scope beyond the approved design or implementation contract | Escalate the scope expansion instead of letting the build packet smuggle a design change downstream. |
| The resubmission changes the code surface but leaves the revision delta or blocker summary unchanged | Treat the verdict as stale, require a fresh delta summary, and prevent silent re-gating. |

## Save Protocol

Gatekeepers do not write directly to `skillset-saves/`. The delegating orchestrator captures the gatekeeper verdict and writes it to the appropriate `gatekeeper-verdict.md` file. Return verdict output inline as usual.

## References

- `scripts/check.py` for the deterministic gate engine wrapper and this boundary's artifact manifest.
- `../../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed build-package validation sequence and verdict rules.
- `references/examples.md` for concrete build-gate examples.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
