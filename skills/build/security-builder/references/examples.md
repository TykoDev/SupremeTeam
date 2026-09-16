# Example Invocations

Six worked passes, one per stage plus the build-phase variants. Example 1 is the
design-phase `security_seed`, Example 5 carries a build checkpoint all the way
to the typed `findings` record `build/build-management` folds into the
`build-to-review` manifest, and Example 6 is a remediation return to
`review/cso` inside the `security` pipeline.

## Contents

1. Seed the security requirements (design stage)
2. Harden the build
3. Review build security
4. Check dependency risk
5. Build checkpoint returned as a typed findings record
6. Remediation returned to `review/cso`

## Example 1 — Seed the security requirements (design stage)

**User request:** seed the security requirements for this design

**Context:** Handoff from `design/commander` carrying `Phase: design` and `Return boundary: design-to-build`. The design adds a partner-facing webhook ingress and moves notification rendering from a trusted internal service to a tenant-configurable template. No code exists yet.

**Stage selected:** `security-seed`. The fields decide it — a build checkpoint here would have nothing to grade.

**Trust boundaries the design introduces or moves:**

| Boundary | Movement | Control the build owes |
| --- | --- | --- |
| Partner → ingress | New. Untrusted input crosses into the request path for the first time | Signature verification on every request before the body is parsed; reject on absent or malformed signature, with a constant-time comparison |
| Ingress → dispatcher | New. Partner-controlled payload reaches internal routing | Schema validation before dispatch; unknown fields rejected rather than ignored |
| Tenant template → renderer | Moved. Rendering input is now tenant-authored rather than internal | Sandboxed rendering with no filesystem, network, or environment access; an explicit allowlist of template functions |
| Renderer → recipient | Moved. Output now derives from tenant input | Output escaping per channel, and a size ceiling so a template cannot generate an unbounded message |
| Config → secrets | Unchanged | Restated as unchanged so the build checkpoint has a complete baseline rather than an implied one |

**`security_seed` evidence handed to `design/commander`:** the table above, plus
the data classification per boundary (partner payloads are untrusted and may
carry recipient personal data; templates are tenant-authored and untrusted).

**Gate facts stated with it:** the key is not artifact-backed at
`design-to-build`, carries no typed record, and has **no sanctioned fallback** —
`../../../gates.yaml` `fallback_values` has no entry for it, so it cannot be waived
at that boundary.

**Explicitly not done:** nothing is graded, no scan is run, and no control is
claimed implemented. Those belong to the build checkpoint, which uses this table
as its baseline.

## Example 2 — Harden the build

**User request:** harden the build

**Output:**
- Finding: attachment uploads trust the client-supplied filename and content type.
- Remediation: sanitize filenames, enforce server-side content checks, and rerun the upload regression tests.
- Gate note: the build advances only after the rerun evidence is attached to the same revision — a closed finding with no rerun behind it fails at the gate.

## Example 3 — Review build security

**User request:** review build security

**Output:**
- Scope: the token issuance flow, admin endpoints, and a newly added dependency for document parsing.
- Risk: the document parser ships with a high-severity advisory in a transitive package, so the package is not security-clean.
- Next move: replace or pin the dependency before `build/cross-check-build-confirm` treats the build as complete.

## Example 4 — Check dependency risk

**User request:** check dependency risk

**Output:**
- Result: first-party code is unchanged, but the build introduces generated SDK files and a third-party auth adapter.
- Handling: mark the non-first-party surfaces explicitly, attach the scan record, and narrow the security claim to the reviewed boundaries.
- Recommendation: if the auth adapter requires policy changes, route that back through design rather than hiding it as a dependency tweak.

## Example 5 — Build checkpoint returned as a typed findings record

**User request:** prepare the security pass — notification service

**Context:** Handoff from `build/build-management` carrying `Phase: build` and `Return boundary: build-to-review`. Run `2026-04-19-notify`, revision 3. The baseline is the seed from Example 1.

**Stage selected:** `security-checkpoint`. Each control below is graded against
the seeded boundary it belongs to, so the two checkpoints read as one contract.

**Scan, recorded as a typed record rather than narrated:**

```bash
python skills/scripts/scan_record.py \
  --out skillset-saves/runs/2026-04-19-notify/build/evidence/security-scan.json \
  --input requirements.lock \
  --tool pip-audit --version-command "pip-audit --version" \
  --fail-exit-codes 1 \
  -- pip-audit -r requirements.lock
```

The raw scanner output is stored beside the record, and `--input` binds it by
sha256 to `requirements.lock` so a later lockfile change fails as drift rather
than passing on a stale scan.

**`security_evidence` handed to `build/build-management`** — the typed `findings`
record, one item per graded control:

```json
"security_evidence": {
  "items": [
    { "id": "SEC-04", "severity": "Critical", "status": "verified",
      "note": "signature verification runs before body parse; constant-time compare; rerun proves an unsigned request is rejected" },
    { "id": "SEC-07", "severity": "Major", "status": "verified",
      "note": "schema validation rejects unknown fields; rerun covers the unknown-field case" },
    { "id": "SEC-09", "severity": "Major", "status": "deferred",
      "owner": "build-management",
      "reopen_trigger": "the renderer gains any filesystem or network capability, or a template function is added to the allowlist",
      "note": "template sandbox has no network or filesystem access; the function allowlist is present but not yet enforced at load time" },
    { "id": "SEC-11", "severity": "Minor", "status": "verified",
      "note": "per-channel output escaping applied; size ceiling set at 64KB" },
    { "id": "SEC-12", "severity": "Info", "status": "not-applicable",
      "reason": "secrets boundary unchanged this revision; restated from the seed so the baseline stays complete" }
  ]
}
```

**Why each status is legal at the gate:** `../../../gates.yaml` `finding_policy`
requires a Critical to be verified or not-applicable with a reason — `SEC-04` is
verified. A Major must be verified, not-applicable with a reason, or deferred
with **both** a named owner and a reopen trigger — `SEC-09` carries both, which
is what keeps it from blocking. `SEC-12` carries a reason because
`not-applicable` without one fails mechanically.

**Fallback not used.** `no trust-boundary change - security-builder not engaged`
is the only sanctioned wording for this key, and it would be false here: three
boundaries moved. Had it been true, it would travel as the `reason` of an
applicability record `{applicable: false, reason, scope, decided_by}`, which is
the only form `check.py` accepts at schema 2.

## Example 6 — Remediation returned to `review/cso`

**User request:** apply the authorized fixes

**Context:** Handoff from `review/cso` carrying `Return boundary: security-review`. The `security` pipeline has already run `scope-and-threat-model`, `posture-assessment`, and `adversarial-probe`, and triage authorized exactly three fixes. `../../../pipelines.yaml` places `remediation` as a conditional stage of that pipeline, run when fixes are authorized.

**Stage selected:** `remediation`. Security-builder holds no gate here;
`review/cso` owns `security-review` and submits there.

**Authorized fix set, applied and proven:**

| Fix | Authorized scope | Proof |
| --- | --- | --- |
| F-1 Pin `xml-parse-core` to the patched `2.1.4` | Dependency manifest only | Re-run `scan_record.py` against the new lockfile; the advisory no longer matches |
| F-2 Enforce the template function allowlist at load time | `renderer/sandbox.py` | Rerun exercises the exploit path — a template calling a non-allowlisted function is rejected at load, not at call |
| F-3 Reject unsigned webhook requests before body parse | `ingress/verify.py` | Rerun sends an unsigned and a wrong-signature request; both rejected before parse, confirmed from the request log |

**Refused, and returned as a finding instead:** the same missing signature check
exists on a second, internal-only ingress path. The fix is two lines and
obviously correct, and it is **not** in the authorized set. It is recorded as
`SEC-14`, Major, `status: open`, with its recommended fix and its location, and
returned to `review/cso` for triage. An engagement that widens itself is no
longer the engagement that was reviewed — and "the fix was two lines" is the
exact reasoning that produces an unreviewed auth change.

**Escalated rather than applied:** F-2's allowlist enforcement surfaced a
tenancy question — two tenants currently share one template cache key. Changing
that alters tenancy behavior beyond the scoped surface, so it is escalated to
`review/cso` with the observation and the recommended direction, not fixed here.

**Remediation record returned to `review/cso`:** the three applied fixes with
their proofs, the one refused fix as `SEC-14`, the tenancy escalation, and the
residual risk. `review/cso` folds it into the package it submits at
`security-review`; this pass submits nothing.
