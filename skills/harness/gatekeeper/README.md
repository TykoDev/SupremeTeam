# Gate Validation

Two validators run at a boundary. They check different things and neither issues
a verdict; the gatekeeper skill maps their facts to
`APPROVED | REVISE | ESCALATE`.

| Validator | Input | Answers |
| --- | --- | --- |
| `check.py` | a gate manifest (`manifest.json`) | Does this submission carry the evidence [`../../gates.yaml`](../../gates.yaml) requires for this boundary, correctly hashed and bound? |
| `_gatecheck.py` (via each `gatekeeper-*/scripts/check.py`) | a phase package directory | Are the phase's markdown deliverables present, lineage-consistent, and free of blocked phrases? |

A phase submits both: the directory check confirms the package is shaped, the
boundary check confirms the evidence contract is met.

**Tier 0 is outside the pipeline.** Eligible minor tasks follow the
[Tier 0 fast path](../../routing-doctrine.md#tier-0-fast-path): focused
verification and a brief completion note, without a gate manifest, verdict, or
full security audit. There is no Tier 0 boundary and no automatic APPROVED
verdict. Once work enters a pipeline, all required evidence applies; a tier label
cannot waive a gate, security evidence, or active-run ownership.

## check.py: the boundary validator

Its boundary table is not hardcoded. It loads `skills/gates.yaml`, the canonical
gate spec, and a missing or malformed spec is an engine error (exit 2), never a
pass. Against that spec it verifies required boundary evidence, artifact-backed
evidence (keys listed under `artifact_evidence` must reference a hashed file in
the package unless the value is a sanctioned fallback), submission and revision
identity, single-revision lineage, artifact existence and SHA-256 hashes, blocked
phrases, local Markdown links, and idempotency drift against an optional prior
verdict record. A hash-mismatched artifact is still scanned for blocked phrases
and broken links.

```text
python skills/harness/gatekeeper/check.py \
  --boundary design-to-build \
  --package skillset-saves/runs/<run>/design/manifest.json \
  [--prior <previous verdict>] \
  [--verdict-out <phase>/verdict_<boundary>.json] \
  [--gates skills/gates.yaml]
```

Exit 0 for a mechanically clean package, 1 for a package defect, 2 for an engine
or input failure (including an unknown `--boundary`, which emits the
`engine_error` JSON envelope on stderr). The result carries
`mechanical_only: true`; human judgment still owns semantic quality.

**Evidence root.** Artifact paths are manifest-relative. Inside the canonical
save layout (`skillset-saves/runs/<run-id>/<phase>/`) the authorised root is the
run directory when the manifest `run_id` matches the directory and the run's
`_state.md`, so `../intake/report_grilling.md` is admissible. Anywhere else the
root is the manifest directory. Another run, traversal, absolute, drive, or UNC
paths, and links leaving the root fail with a structured failure, never an engine
error.

**Manifest schema 2.** Adds `boundary` (must match `--boundary`), `owner` (must
match the spec `submitter`), `run_id`, typed records for keys named in
`evidence_types` (scan, render, probe, audit, findings, verdict, stack_lock,
revision_ref), `inputs` that bind evidence to project files by sha256 (stale
evidence fails as `input hash drift`), and applicability records instead of bare
fallback strings. Schema 1 flat packages keep working.

**Verdict records.** `--verdict-out <path>` writes the result with `verdict_id`,
`package_fingerprint`, and `gate_spec_digest`; `--prior <record>` compares
against it and reports `prior_reusable` plus `idempotency_drift`. A verdict is
reusable only for the same boundary, submission, revision, fingerprint, and gate
spec digest.

## Boundaries

`gates.yaml` (spec revision 2) carries nine boundaries. Each names the
transition it guards and the single skill permitted to submit it. The
human-readable table lives in [`../../../docs/gatekeepers.md`](../../../docs/gatekeepers.md)
and a drift test asserts it matches `gates.yaml` exactly.

Sixteen evidence keys are artifact-backed, meaning the value must reference a
path in the package's `artifact_hashes` map rather than a bare claim:
`decisions`, `architecture`, `plan`, `tests`, `runtime`, `executed_probes`,
`rendered_verification`, `threat_model`, `denial_path_evidence`, `reproduction`,
`evidence_chain`, `test_matrix`, `link_report`, `validation_report`,
`deploy_config`, `verification_plan`, and `rollback_plan`. Eight keys accept a
sanctioned applicability record instead (`security_evidence`, `stack_lock`,
`ui_evidence`, `rendered_verification`, `denial_path_evidence`,
`vulnerability_scan`, `fixes_applied`, `team_manifest`), and only the exact
reasons listed under `fallback_values` are accepted; any other bare string fails
the artifact-backing check.

## _gatecheck.py: the package-shape validator

The shared engine behind each `gatekeeper-*/scripts/check.py`. It scans a phase
package directory for required artifacts by file pattern, verifies single-value
`revision:` lineage, checks skip records, scans for blocked phrases, compares
against a prior verdict for idempotency, and applies the harness-doctrine §5
structural check. It reports PASS / FAIL / UNCHECKED facts.

```text
python skills/design/gatekeeper-design/scripts/check.py <package-dir> [--prior <verdict>] [--json]
```

Both validators fail loud. A hook that errors lets the action proceed; a gate
that cannot prove a package clean must never approve it, so an internal error
becomes an `UNCHECKED` finding and a non-zero exit, never a hidden PASS.

## Regression tests

```text
python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"
```

`test_gate_manifests.py` covers the flat-package contract, every boundary's
complete package, every sanctioned fallback, missing evidence, artifact backing,
lineage, hashing, scanning, and engine errors, plus the drift test against
`docs/gatekeepers.md`. `test_gate_run_layout.py` covers the canonical save
layout: same-run sibling evidence, cross-run and link escapes, revision, owner,
and boundary identity, typed result records, the finding policy, waivers,
YAML-comment specs, quoted diagnostic markers, and verdict reuse.
`test_gatecheck.py` covers the package-shape engine.
