# Example Invocations

Findings use the shared four-tier model — Critical | Major | Minor | Info — that
`../../../gates.yaml` `finding_policy` grades at the `security-review` boundary. No
other severity vocabulary is admissible in a package this skill submits.

## Contents

1. Example 1 — codebase security audit
2. Example 2 — security-chief posture review
3. Example 3 — challenging the accepted risk
4. Example 4 — the submission artifact
5. Example 5 — a REVISE round

## Example 1 — codebase security audit

**User request:** audit this codebase for security issues

**Output:**
- Scope: the authenticated admin surface, its session store, and the two destructive account actions. Excluded: the marketing site, which shares no session.
- Finding SEC-001 — **Critical**, status `verified`: privileged admin actions are protected by a role check but not by step-up authentication, so a stolen session reaches the most damaging path unchallenged. Remediation owner `build/security-builder`; fixed and re-probed in this engagement.
- Finding SEC-002 — **Major**, status `deferred`, owner `build/security-builder`, reopen trigger `the next change to the break-glass flow`: the monitoring playbook detects the destructive action after the fact and is not a preventive control.
- Evidence: `threat-model.md` (hashed), `scan-pip-audit.json` (`result.status: pass`), `probe-admin-denial.log` (hashed).
- Residual risk: break-glass access remains unmodelled pending an owner decision.

## Example 2 — security-chief posture review

**User request:** review this like a security chief

**Output:**
- Finding SEC-010 — **Major**, status `verified`: the product posture depends on one third-party identity provider, and the package documents no token revocation, outage fallback, or emergency lockout procedure. The business cannot state how privileged access is contained during a provider disruption.
- Finding SEC-011 — **Info**: the provider's own status history shows two multi-hour outages in the last year; recorded as context for the resilience decision, not as a defect.
- Remediation plan: identity-provider resilience is assigned to `build/security-builder` as a control gap with a named fix path, not left as an implementation detail.
- Evidence gap: `vulnerability_scan` carries the sanctioned applicability record `no dependency or source scan surface - scanner not engaged`, decided by the engagement owner, because the identity flow is entirely managed.

## Example 3 — challenging the accepted risk

**User request:** challenge the product security posture

**Output:**
- Finding SEC-020 — **Critical**, status `not-applicable`, reason `the reported cross-tenant path is unreachable in this deployment; the filter runs inside the database role, not the application`: recorded with its reason so the Critical is closed on evidence rather than on assertion.
- Finding SEC-021 — **Major**, status `verified`: encryption at rest is present, but tenant isolation still depends on application-layer filters with no database-level guardrail, so a single query-path mistake becomes a cross-tenant incident rather than a local bug.
- Finding SEC-022 — **Minor**, status `recorded`: the isolation test suite covers two of the five tenant-scoped tables.
- Next move: require the database-level isolation boundary, or record the accepted risk with a named owner and a reopen trigger in `residual_risk`.

## Example 4 — the submission artifact

The package this skill delivers is `security/manifest.json`. Schema 2 requires
`boundary`, `owner`, `run_id` inside a run, one `revision`, typed records for the
keys in `evidence_types`, and an applicability record — never a bare string — for
a waived key. This is the manifest for the Example 1 engagement after
remediation, abridged in two ways: to one finding and one `artifact_hashes` entry
per key, and at the hash level — every sha256 below is shown truncated with an
ellipsis for legibility. A real manifest carries the full 64-character digest for
every entry, and the boundary validator rejects a truncated one, so do not copy
these values or their shape:

```json
{
  "schema_version": 2,
  "boundary": "security-review",
  "owner": "cso",
  "run_id": "2026-05-02_admin-audit_b41d",
  "revision": 3,
  "artifact_hashes": {
    "security/reports/threat-model.md": "31ca9f0b…",
    "security/evidence/scan-pip-audit.json": "9b2e4417…",
    "security/evidence/scan-pip-audit.stdout.txt": "4d8a1c60…",
    "security/evidence/scan-pip-audit.stderr.txt": "e91f3b72…",
    "security/evidence/probe-admin-denial.log": "c07d1a55…"
  },
  "evidence": {
    "scope": "Authenticated admin surface, its session store, and the two destructive account actions. Excluded: the marketing site, which shares no session. Active probing authorized by the engagement owner; remediation authorized.",
    "threat_model": "security/reports/threat-model.md",
    "vulnerability_scan": {
      "artifacts": ["security/evidence/scan-pip-audit.stdout.txt",
                    "security/evidence/scan-pip-audit.stderr.txt"],
      "tool": "pip-audit",
      "command": "pip-audit -r requirements.txt --strict",
      "exit_code": 0,
      "observed_at": "2026-05-02T14:07:11Z",
      "inputs": [{"path": "requirements.txt", "sha256": "7d08be21…"}],
      "result": {"status": "pass"}
    },
    "denial_path_evidence": {
      "artifacts": ["security/evidence/probe-admin-denial.log"],
      "result": {"status": "pass"}
    },
    "findings": {
      "items": [
        {"id": "SEC-002", "severity": "Major", "status": "deferred",
         "owner": "build/security-builder",
         "reopen_trigger": "the next change to the break-glass flow"}
      ]
    },
    "remediation_plan": "SEC-001 applied and re-probed at revision 3. SEC-002 deferred to build/security-builder with the reopen trigger above.",
    "residual_risk": "Break-glass access remains unmodelled pending an owner decision; reopen on the next change to that flow."
  }
}
```

Self-check before submitting, and fix every mechanical failure first:

```bash
python skills/harness/gatekeeper/check.py --boundary security-review --package skillset-saves/runs/2026-05-02_admin-audit_b41d/security/manifest.json
```

## Example 5 — a REVISE round

**Gate verdict on revision 2:** `REVISE`, with `revise_packet.by_owner` naming
two owners.

**Packet as received:**

| Owner | Failing key | Reason |
| --- | --- | --- |
| `security-review` | `vulnerability_scan` | `result.status: error` — the scanner exited on a code outside `--fail-exit-codes`, so the record is a data gap, not a scan |
| `cso` | `findings` | SEC-014 is a deferred **Major** with no `reopen_trigger`, which `finding_policy.major_deferral` requires |

**Response:**
- Treated as one packet: both owners delegated in parallel in the same turn, every failing item for one owner batched into a single revision delegation rather than sent one at a time.
- `security-review` re-ran the scan with the observed exit code classified, returning `result.status: fail` with the findings it had printed, plus a `--limitation` for the transitive tree it could not resolve.
- `cso` re-triaged SEC-014 itself, assigning `build/security-builder` as owner and `the next change to the export authorization path` as the reopen trigger.
- Resubmitted **once**, at revision 3, with `--prior` so the gate re-judges only `changed_evidence`:

```bash
python skills/harness/gatekeeper/check.py --boundary security-review --package skillset-saves/runs/2026-05-02_admin-audit_b41d/security/manifest.json --prior skillset-saves/runs/2026-05-02_admin-audit_b41d/security/verdict_security-review.json
```

- `scope`, `threat_model`, `denial_path_evidence`, and `residual_risk` came back as `unchanged_evidence` and carried their prior judgment; only the two repaired keys were re-judged.
- Cycle count: 1 of `revise_policy.cycle_cap` 2. A third cycle escalates instead of resubmitting.
