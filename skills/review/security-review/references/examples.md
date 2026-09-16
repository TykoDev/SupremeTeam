# Example Invocations

Four worked outputs in the packet shape `../SKILL.md` mandates. The first three
are review-pipeline packets returned to `review/code-chief`; the fourth is the
`posture-assessment` stage of the `security` pipeline, returning the
`vulnerability_scan` record to `cso`. Severities use the shared four-tier model
— Critical | Major | Minor | Info — and nothing else: "blocking" and
"conditional" describe a finding's consequence and its confidence, never its
grade. Every finding carries a stable `SEC-NN` id and a status, because that is
what `../../../gates.yaml` `evidence_types.findings` requires of the items
`code-chief` and `cso` merge into `findings`.

## Example 1 — review pipeline: file-upload surface

**User request:** review security of the file-upload pipeline

**Output:**
- Outcome: security-review, `security-review` stage, revision r3, 2 findings: 1 Critical, 0 Major, 1 Minor, 0 Info.
- Evidence: three trust boundaries examined — the multipart upload handler, the object-store write path, and the image-processing worker. Injection sinks, upload-route authorization, and the worker's media handling were checked. No dependency or lockfile changed in this surface, so `vulnerability_scan` carries `no dependency or source scan surface - scanner not engaged` as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`, not a scan record.
- Findings:
  - `SEC-01` | **Critical** | `upload/handler.py:88` | confirmed | status `open` | the handler trusts the client-supplied content type, so the worker is reachable with a crafted polyglot body sent as `Content-Type: image/png`; the precondition is any authenticated account | validate the file signature before enqueueing work and restrict the worker to the permitted media types.
  - `SEC-02` | **Minor** | `upload/handler.py:141` | confirmed | status `open` | the rejection message distinguishes "unsupported type" from "too large", which discloses the accepted-type list | return one generic rejection.
- Open risks: the object store's bucket policy is not in the supplied artifacts, so the blast radius of a written payload stays unconfirmed.
- Next action: `build/security-builder` adds signature validation; the re-review is a delta over the handler alone.
- Revision: r3.
- Handoff to `review/code-chief`: both items enter `findings` as `{id, severity, status}`, and `SEC-01` blocks the review package at `Critical` until it is verified. `code-chief` issues the verdict; this lens does not.

## Example 2 — review pipeline: admin export

**User request:** check for vulnerabilities in the new admin export feature

**Output:**
- Outcome: security-review, `security-review` stage, revision r1, 1 finding: 0 Critical, 1 Major, 0 Minor, 0 Info.
- Evidence: three boundaries examined — the admin export endpoint, the CSV generation path, and the authorization guard. Injection sinks and CSV formula injection were checked across the exported columns as generated and came back clean; no dependency changed, so no scan record is owed by this pass.
- Findings:
  - `SEC-03` | **Major** | `admin/export.py:52` | confirmed | status `open` | export authorization checks role membership but never narrows to the caller's tenant, so an elevated shared account reads another tenant's rows; the route is in the shipped table with no configuration gate in front of it | scope the query by tenant at the guard, not in the view.
- Open risks: whether the same guard protects the scheduled-export job is not visible in the supplied artifacts.
- Next action: `review/code-chief` routes `SEC-03` to its fix owner, and asks `review/mr-robot` to pressure-test tenant-boundary abuse cases once the trust-boundary mapping is recorded — the chained attack narrative is that lens's work, not this one's.
- Revision: r1.

## Example 3 — review pipeline: dependency risk

**User request:** audit the dependency risk in this release

**Command:**

```bash
python skills/scripts/scan_record.py \
  --out review/evidence/scan-pip-audit.json \
  --input requirements.txt \
  --input requirements.lock \
  --version-command "pip-audit --version" \
  -- pip-audit -r requirements.txt --strict
```

**Output:**
- Outcome: security-review, `security-review` stage, revision r2, 2 findings: 0 Critical, 1 Major, 1 Minor, 0 Info.
- Evidence: the updated dependency manifest, the lockfile delta, and the code paths that load the new parser library. Scan record `review/evidence/scan-pip-audit.json` — `result.status: fail`, `exit_code: 1` (declared in `--fail-exit-codes`), with `requirements.txt` and `requirements.lock` both bound by sha256.
- Findings:
  - `SEC-04` | **Major** | `parsers/xml.py` via `defused-fork@0.9.1` | conditional | status `open` | the pinned version carries a known advisory, but the vulnerable feature is not reachable from the shipped configuration, so the claim stays conditional rather than promoted on the advisory alone | pin past the advisory, or record the unreachable path as accepted risk with an owner.
  - `SEC-05` | **Minor** | `requirements.txt` vs `requirements.lock` | confirmed | status `open` | the manifest allows a version the lockfile does not resolve to, so the install is not reproducible — a supply-chain gap independent of which version is vulnerable | reconcile the two files and re-lock.
- Open risks: transitive packages the scanner reported as unaudited are out of coverage, and the record's `--limitation` says so.
- Next action: `review/code-chief` merges both items; the scan record path and digest ship with the packet so nobody re-scans the tree.
- Revision: r2.

## Example 4 — security pipeline: posture assessment for `cso`

**User request (delegated by `cso`):** run the posture assessment against the scoped threat model

**Command:**

```bash
python skills/scripts/scan_record.py \
  --project-root . \
  --out skillset-saves/runs/2026-05-02_admin-audit_b41d/security/evidence/vulnerability-scan.json \
  --input package.json \
  --input package-lock.json \
  --version-command "npm --version" \
  --limitation "optional peer dependencies not installed in this environment" \
  -- npm audit --audit-level=moderate
```

**Returned to `cso` unchanged:**
- Record: `security/evidence/vulnerability-scan.json` — `sha256:9b2e…d417`.
- `result.status: fail`, `exit_code: 1`, `tool: npm`, inputs bound: `package.json` `sha256:31ca…`, `package-lock.json` `sha256:7d08…`.
- Limitation on the record: optional peer dependencies were not installed, so their advisories are out of coverage. Stated here because a limitation `cso` never sees becomes a coverage claim it did not make.
- Defensive findings behind the record, each traced to a boundary in `cso`'s threat model and each carrying the `{id, severity, status}` shape `../../../gates.yaml` `evidence_types.findings` requires: `SEC-06` | **Major** | status `open` | the session store's cookie flags omit `SameSite` and `Secure`; `SEC-07` | **Minor** | status `open` | a deprecated transitive parser remains on the dependency path.
- Secrets check: the retained raw output was reviewed before handover and echoes no registry credential; the record ships as routine evidence.
- Not returned: the triage, the remediation plan, and the residual risk. `cso` owns those keys and closes the boundary.
