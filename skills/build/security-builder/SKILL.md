---
name: security-builder
description: >-
  This skill should be used when the user or build-management asks to
  "audit code security", "check for vulnerabilities", "review security
  of the build", "scan for security issues", "validate input handling",
  "check authentication code", "review access control implementation",
  "audit cryptography usage", "check for injection vulnerabilities",
  "assess dependency security", "verify OWASP compliance in the code",
  or "run a security audit". It performs systematic security auditing of
  built code, mapping all findings to OWASP Top 10, CWE Top 25, and
    NIST SSDF frameworks with actionable remediation guidance. Distinct from
    security-review (review pipeline): security-builder operates during the
    build phase, auditing newly-written code before it ships.
version: 1.0.0
---

# Security Builder — Code Security Auditor

## Purpose

Security Builder is the dedicated security auditor for the Build Team SkillSet.
It examines actual implemented code — not designs or specifications — for
vulnerabilities, insecure patterns, and compliance gaps. Every finding is mapped
to established security frameworks and includes actionable remediation guidance.
Security findings that require code changes are packaged separately for routing
to bob-the-builder through build-management. Security Builder is a specialist
phase in the canonical pipeline, not a final approver — its output is not
accepted until `gatekeeper-build` validates it through build-management.

## Core Principle

> "Audit the code that exists, not the code that was planned. The implementation
> is the only source of truth for security posture. Verify every claim by
> examining the actual code paths."

---

## Security Audit Workflow

### Step 1: Risk Assessment

Classify the codebase before beginning detailed analysis:

1. **Data sensitivity**: What data does the application handle? (PII, financial, healthcare, credentials, public)
2. **Exposure surface**: Is this a public API, internal service, user-facing application, or background worker?
3. **Trust boundaries**: Where does external input enter the system? Where does sensitive data exit?
4. **Regulatory scope**: Does this codebase fall under GDPR, HIPAA, PCI-DSS, SOC 2, or other compliance frameworks?

Assign a risk tier:

| Tier | Criteria | Audit Depth |
|------|----------|-------------|
| **Critical** | Handles credentials, payment data, or PHI; public-facing | Full audit, all OWASP categories, threat model |
| **High** | Handles PII or business-critical data; API exposed | Full OWASP sweep, focused threat model |
| **Medium** | Internal service with no direct user input | OWASP Top 5, dependency scan, secrets check |
| **Low** | Internal tooling, no sensitive data | Dependency scan, secrets check, basic input validation |

### Step 2: OWASP Top 10 Sweep

Systematically check the codebase against OWASP Top 10:2025:

| # | Category | What to Check |
|---|----------|--------------|
| A01 | Broken Access Control | Authorization checks on every endpoint, IDOR protection, CORS configuration |
| A02 | Cryptographic Failures | Algorithm strength, key management, TLS configuration, password hashing |
| A03 | Injection | SQL, NoSQL, command, LDAP, XSS — trace all inputs to sinks |
| A04 | Insecure Design | Business logic flaws, missing rate limiting, abuse scenario coverage |
| A05 | Security Misconfiguration | Default credentials, verbose errors, unnecessary features enabled |
| A06 | Vulnerable Components | Known CVEs in dependencies, outdated packages, unmaintained libraries |
| A07 | Authentication Failures | Credential storage, session management, brute-force protection, MFA |
| A08 | Data Integrity Failures | Deserialization safety, CI/CD pipeline integrity, update mechanisms |
| A09 | Logging Failures | Sensitive data in logs, insufficient audit trails, log injection |
| A10 | SSRF | Server-side request forgery in URL-fetching, webhook, or redirect logic |

### Step 3: Input/Output Trace Analysis

For every external input entry point identified in Step 1:

1. **Trace the input**: Follow the data from entry point through all transformations to storage or output
2. **Identify sinks**: Where does the data end up? (SQL query, HTML template, shell command, log file, response body)
3. **Verify sanitization**: Is the data validated, encoded, or escaped before reaching each sink?
4. **Check bypass potential**: Can the sanitization be circumvented through encoding tricks, double encoding, or type confusion?

### Step 4: Authentication and Authorization Audit

1. **Credential storage**: Verify passwords use bcrypt/scrypt/argon2 with appropriate cost factors
2. **Session management**: Check token generation (cryptographic randomness), storage (httpOnly, secure flags), and expiration
3. **Authorization enforcement**: Verify every endpoint checks permissions — not just the UI hiding buttons
4. **Privilege escalation**: Test for horizontal (accessing other users' data) and vertical (accessing admin functions) escalation paths
5. **API key management**: Verify API keys are scoped, rotatable, and not hardcoded

### Step 5: Dependency and Supply Chain Scan

1. **Known vulnerabilities**: Check all dependencies against CVE databases (NVD, OSV, GitHub Advisory)
2. **Outdated packages**: Flag packages more than 2 major versions behind
3. **Unmaintained packages**: Flag packages with no commits in 12+ months
4. **Lockfile integrity**: Verify lockfile exists and is committed to version control
5. **License compliance**: Flag copyleft licenses (GPL) in proprietary projects

### Step 6: Secrets Detection

Scan the entire codebase for hardcoded secrets:

1. **API keys and tokens**: Search for patterns matching common key formats (AWS, Stripe, GitHub, etc.)
2. **Connection strings**: Check for embedded database credentials in code or committed config files
3. **Private keys**: Search for PEM-encoded keys or certificate files in the repository
4. **Environment file exposure**: Verify `.env` files are in `.gitignore` and not committed

---

## Framework Alignment

All findings MUST be mapped to at least one of these frameworks:

| Framework | Version | Use |
|-----------|---------|-----|
| **OWASP Top 10** | 2025 | Primary risk categorization |
| **CWE Top 25** | 2025 | Weakness taxonomy for precise classification |
| **NIST SSDF** | v1.1 | Secure development practice verification |
| **OWASP ASVS** | 5.0 | Technical control requirements (L1/L2/L3) |
| **CVSS** | v4.0 | Severity scoring |

---

## Severity Classification

| Severity | CVSS Score | Definition | Examples |
|----------|-----------|------------|---------|
| **Critical** | 9.0-10.0 | Immediate exploitation risk, data breach likely | SQL injection in auth, hardcoded admin credentials, RCE |
| **High** | 7.0-8.9 | Exploitation possible with moderate effort | Stored XSS, broken access control, weak crypto |
| **Medium** | 4.0-6.9 | Exploitation requires specific conditions | Reflected XSS with CSP, verbose error messages, missing rate limiting |
| **Low** | 0.1-3.9 | Minimal exploitability or impact | Missing security headers, information disclosure in non-sensitive contexts |

---

## Remediation Handoff

Package security findings requiring code changes for routing to bob-the-builder:

```markdown
## SECURITY REMEDIATION PACKAGE

### Critical Findings (Fix Immediately)
| ID | CWE | Finding | File:Line | Required Fix |
|----|-----|---------|-----------|-------------|
| SEC-001 | CWE-89 | SQL injection in user search | src/user/repo.ts:42 | Parameterize query |
| SEC-002 | CWE-798 | Hardcoded API key | src/config/stripe.ts:3 | Move to env variable |

### High Findings (Fix Before Delivery)
| ID | CWE | Finding | File:Line | Required Fix |
|----|-----|---------|-----------|-------------|
| SEC-003 | CWE-862 | Missing auth check on admin endpoint | src/admin/routes.ts:15 | Add auth middleware |

### Medium Findings (Recommended Fix)
| ID | CWE | Finding | File:Line | Recommended Fix |
|----|-----|---------|-----------|----------------|
| SEC-004 | CWE-532 | Sensitive data in logs | src/auth/service.ts:28 | Redact PII before logging |
```

---

## Output Format

Structure the security audit report as follows:

```markdown
## Security Audit Report

### Risk Assessment
- Data sensitivity: [level]
- Exposure surface: [type]
- Risk tier: [Critical | High | Medium | Low]
- Compliance scope: [frameworks]

### Findings Summary
| Severity | Count |
|----------|-------|
| Critical | [N] |
| High | [N] |
| Medium | [N] |
| Low | [N] |

### Detailed Findings
#### [SEC-001]: [Title]
- **Severity**: [Critical | High | Medium | Low]
- **CWE**: [CWE-ID — Name]
- **OWASP**: [A0X — Category]
- **Location**: [file:line]
- **Description**: [What is vulnerable]
- **Evidence**: [Code snippet or reproduction steps]
- **Impact**: [What an attacker could achieve]
- **Remediation**: [Specific fix with code example]

### Dependency Scan Results
| Package | Current | Vuln ID | Severity | Fix Version |
|---------|---------|---------|----------|-------------|

### Secrets Scan Results
| Type | File | Line | Status |
|------|------|------|--------|

### Audit Coverage
- OWASP Top 10 categories checked: [N]/10
- Input entry points traced: [N]/[total]
- Endpoints with auth verification: [N]/[total]
```

---

## Handoff to Gatekeeper

Submit the security audit through build-management for mandatory
`gatekeeper-build` review. The audit is not accepted until the gatekeeper issues
`APPROVED`.

If the approved audit includes remediation items, build-management routes those
items to `bob-the-builder`, then sends the updated code back to
`gatekeeper-build` for re-validation before the canonical workflow may advance to
`cross-check-build-confirm`.

If gatekeeper issues a `REVISE` verdict, address the specific findings and
resubmit through build-management.

---

## Additional Resources

### Reference Files

For detailed checklists, vulnerability patterns, and remediation guidance:
- **`references/security-checklist.md`** — Complete secure coding checklist with OWASP Top 10 mapping, CWE Top 25 weakness patterns, ASVS control verification procedures, AI-specific threat assessment, and supply chain verification steps
- **`references/vulnerability-patterns.md`** — Common vulnerability patterns by language and framework including injection variants, authentication bypass techniques, insecure deserialization, broken access control, cryptographic failures, SSRF, and path traversal with detection guidance
- **`references/remediation-guide.md`** — Remediation priority matrix, fix patterns for each vulnerability category, verification procedures to confirm fixes, and structured remediation report format for bob-the-builder

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: build
   phase: 3
   skill: security-builder
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
