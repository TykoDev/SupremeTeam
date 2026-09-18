# Example Invocations

Five worked outputs in the packet shape `../SKILL.md` mandates. The first three
are review-pipeline packets returned to `review/code-chief`; the fourth is the
`posture-assessment` stage of the `security` pipeline, returning the
`vulnerability_scan` record to `cso`; the fifth is a REVISE delta over the
fourth, showing the re-run and the input re-bind that a stale sha256 otherwise
fails on. Severities use the shared four-tier model
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
python skills/scripts/output_paths.py --run-id 2026-05-02-deps --phase review --kind evidence --name vulnerability-scan.json
# -> skillset-saves/runs/2026-05-02-deps/review/evidence/vulnerability-scan.json

python skills/scripts/scan_record.py --out skillset-saves/runs/2026-05-02-deps/review/evidence/vulnerability-scan.json --input requirements.txt --input requirements.lock --version-command "pip-audit --version" -- pip-audit -r requirements.txt --strict
```

**Output:**
- Outcome: security-review, `security-review` stage, revision r2, 2 findings: 0 Critical, 1 Major, 1 Minor, 0 Info.
- Evidence: the updated dependency manifest, the lockfile delta, and the code paths that load the new parser library. Scan record `review/evidence/vulnerability-scan.json` — the destination resolved above — `result.status: fail`, `exit_code: 1` (declared in `--fail-exit-codes`), with `requirements.txt` and `requirements.lock` both bound by sha256.
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
python skills/scripts/scan_record.py --project-root . --out skillset-saves/runs/2026-05-02_admin-audit_b41d/security/evidence/vulnerability-scan.json --input package.json --input package-lock.json --version-command "npm --version" --limitation "optional peer dependencies not installed in this environment" -- npm audit --audit-level=moderate
```

**Returned to `cso` unchanged:**
- Record: `security/evidence/vulnerability-scan.json` — `sha256:9b2e…d417`.
- `result.status: fail`, `exit_code: 1`, `tool: npm`, inputs bound: `package.json` `sha256:31ca…`, `package-lock.json` `sha256:7d08…`.
- Limitation on the record: optional peer dependencies were not installed, so their advisories are out of coverage. Stated here because a limitation `cso` never sees becomes a coverage claim it did not make.
- Defensive findings behind the record, each traced to a boundary in `cso`'s threat model and each carrying the `{id, severity, status}` shape `../../../gates.yaml` `evidence_types.findings` requires: `SEC-06` | **Major** | status `open` | the session store's cookie flags omit `SameSite` and `Secure`; `SEC-07` | **Minor** | status `open` | a deprecated transitive parser, `tar-stream@2.2.0`, remains on the dependency path.
- Secrets check: the retained raw output was reviewed before handover and echoes no registry credential; the record ships as routine evidence.
- Not returned: the triage, the remediation plan, and the residual risk. `cso` owns those keys and closes the boundary.

## Example 5 — a REVISE delta: re-running the scan and re-binding its inputs

The round after Example 4. `cso` sub-delegates the packet's `security-review`
group, which holds the `vulnerability_scan` failures and nothing else;
`changed_evidence` names `package-lock.json`. This is the case the first four
passes cannot show — the scan record is the one artifact this lens owns, and the
two ways a REVISE round breaks it are both mechanical.

**User request:** re-run the security scan against the REVISE packet

**Output:**
- Outcome: security-review delta, `posture-assessment` stage, r2 <- r1, 1 finding verified, 1 carried.
- Evidence: the dependency bump in `package-lock.json` only. **The scan was re-run, not re-read** — `scan_record.py` executed again over the changed inputs, producing a new record with `result.status: pass`. Re-reading the r1 record would have verified nothing, and hand-editing its `result.status` would have fabricated the artifact the boundary checks.
- **The re-bind, and what it costs to forget:** the new record's `inputs` carry `package-lock.json` at `2060229e67426248…`, the post-fix digest. The r1 record bound `8cc8d4cf224c778b…`. Shipping a clean re-run that still carries the pre-fix sha256 is the most common failure of this round: the scan passes, the artifact-backing check fails, and the round is spent for nothing. The record is rewritten to the run's own destination, resolved with `output_paths.py`, never over the r1 record — the prior record stays as lineage.
- Findings:
  - `SEC-07` | **Minor** | `package-lock.json` :: `tar-stream@2.2.0` | status `verified` | the advisory path is closed by the bump to 3.1.7, and the re-run reports `pass` over the re-bound lockfile. Same id, same severity as Example 4 graded it — a verified finding keeps the severity it was reported at, because the grade describes the weakness that was found, not how much work the fix turned out to be. Promoting it to Major on the way out would misreport the r1 round.
  - `SEC-06` | **Major** | the session store's cookie flags | status `open` | unchanged from r1. `changed_evidence` names `package-lock.json` only, and no sink whose reachability runs through the lockfile touches the session store, so this finding is carried forward under its original id and severity rather than re-judged. It is not a scan finding and the re-run says nothing about it; carrying it is what keeps the round from reading as a clean pass.
- Open risks: the re-run covers the lockfile alone. Whether the bumped transitive dependency changes runtime behavior is a build question, not a scan result.
- Next action: `cso` folds the new record into the security package. Cycle 1 of a `cycle_cap` of 2 is spent. `SEC-06` is the Major that would stand at the cap: it returns unchanged with its blocking status intact, and the cap is never a reason to downgrade it to fit the round.
- Revision: r2 <- r1.
