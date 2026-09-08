# Responsibility Matrix

## Responsibility

This matrix assigns one writer to each lifecycle layer and states the trigger,
inputs, and output. A layer may consult another owner, but it may not silently
take that owner's write boundary.

| Layer | Trigger | Owner | Inputs | Output | One writer |
|-------|---------|-------|--------|--------|------------|
| INTAKE | New request, resume, or explicit scope change | admiral | User intent, active run evidence, constraints | Bounded brief, tier, grilling log with deferrals and reopen triggers, initial owner, next phase | admiral writes intake, run routing, and the grilling log |
| DESIGN | Intake is accepted and the problem needs a build decision | commander | Brief, current evidence, constraints | Build contract, architecture, interface contracts, design system, stack lock, traceability, non-goals, risks | commander writes the design package and stack lock; each specialist writes only its named artifact |
| BUILD | The build contract is approved | build-management | Build contract, locked stack, named artifact boundary | Changed artifact set, test and runtime evidence, security evidence | build-management writes the build package |
| REVIEW | Build output is submitted or a risk requires recheck | code-chief | Submission, hashes, tests, evidence, known risks | Findings, proof gaps, rendered verification, verdict recommendation | code-chief writes the review packet and verdict |
| SECURITY | Security audit, threat model, hardening, or remediation is requested | cso | Scope, threat model inputs, target surface, authorization | Threat model, graded findings, deny-path evidence, remediation plan, residual risk | cso writes the security packet; security-review writes the scan, mr-robot the deny-path evidence |
| INVESTIGATION | The failure mechanism is unclear | investigate | Symptom, logs, runtime clues, environment | Reproduction, evidence chain, mechanism, bounded fix path, residual uncertainty | investigate writes the investigation package and changes no product code |
| QA | Product testing with recorded evidence is requested | qa | Built surface, declared scope, environment | Test matrix, executed probes, defects, fixes applied, residual risk | qa writes the QA package; qa-only writes the report-only variant |
| SKILL CREATION | A skill or coordinated team is requested | skill-maker | Skill intent, trigger language, packaging target | Skills, review scorecard, link and validation reports, package | skill-maker writes the package; skill-creator drafts; skill-reviewer scores |
| GATE | A phase boundary requests advancement | the boundary's gatekeeper | Required artifact, revision lineage, hashes, evidence | APPROVED, REVISE, or ESCALATE with missing facts | the gatekeeper writes the verdict only |
| RELEASE | Gate approves an externally visible delivery | land-and-deploy | Approved package, deployment settings, rollback, owner intent | Release result, verification evidence, follow-up | land-and-deploy writes the release record |
| SAFETY | A destructive, guarded, frozen, or boundary-sensitive action is requested | guard or freeze | Explicit intent, path boundary, current run, risk evidence | Allow, deny, or guarded next action with audit evidence | the selected guard or freeze owner writes its record |
| MEMORY | A checkpoint, resume, or durable learning is required | session-memory | Run state, evidence paths, boundary | Run record, audit trail, checkpoint | session-memory writes the run record through save_run.py only |

Specialists (researcher, architect, planner, engineer, bob-the-builder,
test-builder, security-builder, cross-check-build-confirm, debugger,
health-check, bug-review, code-review, quality-review, security-review,
mr-robot, frontier, design-qa, devex-review) work inside these layers under the
owning lead. Their write boundaries are the artifact ids in
[`../ownership.yaml`](../ownership.yaml).

## One-writer rule

Each active artifact has exactly one writer identified by owner, path, and
revision. Readers may comment, validate, or return findings, but they do not
edit the artifact. Transfer ownership only through a new handoff with a new
revision, and keep the artifact hash unchanged until the new writer records a
change.

`admiral` writes lifecycle routing and cross-layer handoffs; `session-memory`
writes the run record. A phase owner writes only its phase artifact. A
gatekeeper never repairs the submission. `land-and-deploy` never changes an
approved package without a new revision. The selected `guard` or `freeze` owner
never widens a path boundary while applying a check.
