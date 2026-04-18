---
name: security-review
description: >-
  This skill should be used when the user asks to "review security",
  "check for vulnerabilities", "do a security audit", "review for
  OWASP issues", "security scan this PR", "review authorization
  logic", "check authentication code", "validate this against OWASP
  ASVS", "assess supply chain security", "review this dependency
  change", "check for data leakage", "assess AI security", "check
  NIST SSDF compliance", "is this secure?", or "audit the auth
  flow". Systematic defensive security analysis using NIST SSDF,
  OWASP ASVS, CWE Top 25, and STRIDE threat modeling with risk-tiered
  depth. Produces findings with CWE IDs, severity (CVSS-aligned), and
  remediation guidance. DO NOT USE for offensive penetration testing
  (use mr-robot). DO NOT USE for build-phase security controls (use
  security-builder). DO NOT USE for Azure-specific security review
  (use azure pipeline skills).
version: 1.0.0

---

# Security Review — Security Assessment Specialist

## Purpose

Perform dedicated security analysis focused exclusively on exploitability, security requirements compliance, and threat mitigation. This skill is distinct from bug-review (which targets correctness defects) and code-review (which applies a holistic assessment). The sole objective is to identify code that can be exploited by adversaries, violates security requirements, or introduces vulnerabilities into the software supply chain. All findings are mapped to established security frameworks and weakness taxonomies.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

## Frameworks Alignment

Anchor every security review to the applicable frameworks. The primary frameworks are:

- **NIST SSDF v1.1** — Secure development practices; PW.7 mandates code review for vulnerability detection
- **OWASP ASVS 5.0** — Technical control requirements at three compliance levels (L1 basic, L2 standard, L3 critical)
- **OWASP Top 10:2025** — Risk categorization; XSS #1, Missing Authorization surged to #4
- **CWE Top 25:2025** — Weakness taxonomy for classifying findings
- **Microsoft Continuous SDL** — Expanded for AI-specific threats (prompt injection, training data poisoning)
- **EU AI Act / RAD-AI** — For AI in high-risk contexts; extends documentation for probabilistic behaviors

Consult `references/frameworks.md` for detailed framework descriptions, comparison tables, compliance mapping anchors, and version-specific changes.

## Operational Framework Mapping

Map each review activity to its anchoring framework:

| Review activity | Primary anchors |
|-----------------|-----------------|
| Risk tier assessment | NIST SSDF PW.7, OWASP ASVS level selection |
| Auth and access control | OWASP ASVS V1-V4, CWE Top 25 |
| Threat model delta | STRIDE, MITRE ATT&CK |
| Supply chain review | NIST SSDF PS.3/PW.4, OWASP Top 10:2025 |
| AI-specific review | Microsoft Continuous SDL, EU AI Act / RAD-AI |

Consult `references/frameworks.md` for the full operational-use column with detailed mapping rationale.

## Threat Modeling Integration

Treat threat modeling as a code review input, not a separate once-per-project activity.

**When to Trigger.** Create or update a lightweight threat model whenever a PR introduces: a new data flow, a trust boundary change, authentication or authorization modifications, a new external dependency, or API surface changes.

**STRIDE Application.** Classify threats using STRIDE categories: Spoofing (identity), Tampering (data integrity), Repudiation (deniability), Information Disclosure (confidentiality), Denial of Service (availability), Elevation of Privilege (authorization). Map each identified threat to mitigations in the code.

**ATT&CK Cross-Reference.** Enrich the threat model with MITRE ATT&CK real-world adversary tactics and techniques. Focus on CI/CD compromise, credential abuse, and supply-chain attack patterns relevant to the change.

**Validation During Review.** For each PR with threat model implications:
1. Verify that trust boundaries and entry points affected by the change are identified
2. Confirm that mitigations for each identified threat are implemented in the code
3. Validate that security tests cover the threat scenarios
4. For High-risk changes, require security specialist approval enforced via CODEOWNERS

## Security Review Workflow

Apply a risk-tiered approach to determine review depth.

**Step 1: Risk Tier Assessment.** Classify the change based on what is touched:
- **Low:** UI styling, documentation, test-only changes, non-sensitive configuration
- **Medium:** Business logic, data processing, non-auth API endpoints, internal tooling
- **High:** Authentication/authorization, payment/financial logic, cryptographic operations, deserialization of untrusted data, CI/CD pipeline configuration, new external dependencies, AI/ML model integration

**Step 2: Automated Gate Verification.** Confirm that CI/CD automated security gates have executed and review their results:
- SAST findings (CodeQL, Semgrep) — review any new alerts, verify suppressions are justified
- SCA findings — check for vulnerable dependencies, verify patch availability
- Secrets detection — confirm no new secrets detected, verify push protection is active
- Normalize results to SARIF format for unified triage where possible

### Tool Output Validation

Treat automated security tools as leads, not verdicts:

- Reproduce or trace each High/Critical alert to a concrete code path or configuration path
- Re-score dependency findings based on reachable code paths, exposure, and exploit prerequisites instead of inheriting vendor severity blindly
- Reject suppressions that do not state whether the alert is a false positive, accepted risk, or mitigated elsewhere
- If required automated gates did not run, record a tooling gap and manually inspect the affected control area before finalizing the report

Rationale: disciplined triage prevents false positives, false negatives, and severity inflation.

**Step 3: Apply Secure Coding Checklist.** Systematically evaluate the changed code against the secure coding checklist (see summary below and full checklist in `references/secure-coding-checklist.md`).

**Step 4: Threat Model Alignment (Medium/High Tier).** For Medium and High risk changes, validate that the code change aligns with the threat model. Verify mitigations for identified threats are present and tested.

**Step 5: AI-Specific Threat Assessment.** If the change involves AI/ML components, evaluate for:
- **Prompt Injection:** Can external user inputs manipulate AI system instructions or hijack workflows?
- **Data/Model Poisoning:** Is training data integrity validated? Can dependency chains corrupt model outputs?
- **Excessive Agency:** Are AI agent permissions scoped with strict RBAC? Can agents escalate privileges?
- **Shadow AI:** Are ungoverned data flows or unauthorized AI tools creating compliance blind spots?
- **PII Leakage:** Can sensitive data leak through system prompts, telemetry, or unauthorized channels?

**Step 6: Supply Chain Evaluation.** For changes that add or update dependencies:
- Verify SBOM generation is configured (CycloneDX or SPDX)
- Run SCA with reachability analysis (is the vulnerable code actually called?)
- Check transitive dependency chains for known vulnerabilities
- Validate dependency provenance and integrity (SLSA alignment, signatures)
- Check for malicious package indicators: typosquatting, dependency confusion, post-install scripts with network calls, recent maintainer ownership transfers (454,600+ malicious npm packages detected in 2025)
- Perform reachability analysis: are the vulnerable code paths in dependencies actually called by the application? Reachability-aware SCA (Semgrep Supply Chain, Snyk Reachability) reduces false positives by up to 98%
- Consult `references/supply-chain.md` for detailed supply chain gate procedures

**Step 7: API Security Assessment (API-Heavy Codebases).** For applications with significant API surface areas, cross-reference findings against the OWASP API Security Top 10 (2023):
- **API1: BOLA** — Broken Object Level Authorization (most prevalent API vulnerability)
- **API2: Broken Authentication** — Weak token handling, missing rate limiting
- **API3: BOPLA** — Broken Object Property Level Authorization (mass assignment, excessive data exposure)
- **API4: Unrestricted Resource Consumption** — Missing rate limits, pagination abuse
- **API5: BFLA** — Broken Function Level Authorization (admin endpoints exposed)
- **API7: SSRF** — Server-Side Request Forgery via URL parameters
- **API8: Security Misconfiguration** — CORS, headers, error verbosity
- **API9: Improper Inventory Management** — Undocumented or deprecated endpoints
- **API10: Unsafe Consumption of APIs** — Trusting third-party API responses without validation

## Secure Coding Checklist Summary

Apply these checks to every security-relevant code change. The full checklist with detailed sub-items is in `references/secure-coding-checklist.md`.

**Input Validation.** Trace every external input (HTTP body, query string, headers, environment variables, queue payloads, webhook bodies) to its first validation point. Confirm server-side type, length, format, and allow-list checks exist before business logic runs. Validation failures must reject the request or payload immediately. Data sources must be classified explicitly as trusted or untrusted.

**Output Encoding.** Inspect every sink where data leaves the application: HTML rendering, SQL queries, shell commands, log output, and outbound templates. Confirm template auto-escaping stays enabled, SQL uses parameterized queries, shell invocations avoid raw concatenation, and user input never reaches HTML sinks without sanitization or safe APIs.

**Authentication.** Verify credential creation, token issuance, session establishment, and service-to-service authentication flows. Confirm MFA where required, OAuth2/OIDC or equivalent for inter-service auth, bcrypt or Argon2 for password storage, no embedded passwords, and proper token rotation or secure cookie handling where sessions exist.

**Session Management.** Check session identifier generation, rotation, invalidation, and expiry rules. Confirm fixation prevention on login or privilege change, secure cookie attributes (`Secure`, `HttpOnly`, `SameSite`), and server-side revocation or logout behavior.

**Access Control.** Walk each privileged action from entry point to data access. Confirm authorization happens on the server, object ownership is checked before reads or writes, default-deny behavior exists for missing roles, and RBAC or ABAC boundaries prevent lateral movement.

**Error Handling.** Inspect error responses, exception handlers, retries, and fallback paths. Confirm end users never receive stack traces, tokens, or architecture details, and that failures in auth, policy, or validation controls deny by default rather than bypassing protection.

**Cryptography.** Identify every cryptographic use: hashing, encryption, signatures, token generation, and random number generation. Confirm approved algorithms only, established libraries instead of custom primitives, proper key storage and rotation, and no hardcoded keys or salts.

**Logging.** Review application logs, audit logs, and monitoring hooks. Confirm secrets, tokens, passwords, and unnecessary PII are excluded, audit records contain enough context for incident response, and security-relevant logs are tamper-resistant or centrally collected.

## Output Format

Structure the security review report as follows:

```

---

## Security Review Report
### Summary
- **Risk Tier:** Low | Medium | High
- **Frameworks Applied:** [list]
- **Total Findings:** [count] (Critical: [n], High: [n], Medium: [n], Low: [n])
- **Supply Chain Status:** Clean | Issues Found

### Findings
#### [SEC-001] [CWE-XXX] — [Brief Title]
- **Severity:** Critical | High | Medium | Low (CVSS v4.0 score: [X.X])
- **Location:** file:line
- **Description:** [Vulnerability description and exploit scenario]
- **Evidence:** [Code path, attack vector, proof of exploitability]
- **Remediation:** [Specific fix with secure alternative]
- **Framework Reference:** [OWASP Top 10 category, CWE ID, ASVS control]

### Threat Model Assessment
- [Threat model delta for this change, or "Not applicable — Low risk tier"]

### Supply Chain Assessment
- [Dependency changes, SBOM status, SCA results, provenance verification]

### Tooling Gaps
- [Missing automated security checks that should be added]

### Checklist Coverage
- [Which checklist categories were applied, which were not applicable]
```

Append the following structured summary block at the end of every report for
pipeline consumption:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 4
skill: security-review
status: COMPLETE
risk_assessment: [High / Medium / Low]
finding_count:
  critical: [n]
  high: [n]
  medium: [n]
  low: [n]
checklist_coverage: [percentage]
verdict: [High Risk / Medium Risk / Low Risk / Clean]
supply_chain_status: [Clean / Issues Found]
threat_model_delta: [Updated / Not Applicable / No Changes]
key_concerns: [top 3 findings by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

### Example Finding

#### [SEC-001] [CWE-79] — DOM-Based XSS in Search Results
- **Severity:** High (CVSS v4.0 score: 8.2)
- **Location:** src/components/SearchResults.tsx:37
- **Description:** User-controlled search text is inserted into the DOM through `innerHTML`, creating a script injection path.
- **Evidence:** `results.innerHTML = `<li>${query}</li>`;` renders unsanitized input directly into markup.
- **Remediation:** Replace `innerHTML` with text-safe rendering or sanitize through a vetted library such as DOMPurify before insertion.
- **Framework Reference:** OWASP Top 10:2025 Injection, CWE-79, OWASP ASVS 5.0 V5.3

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation with review target scope, Phase 1–3 context, and technology stack
- Execute the full security review workflow (risk assessment, automated gates, checklist, threat model, AI threats, supply chain)
- Submit the completed report to code-chief (not directly to gatekeeper-code)
- Include the structured pipeline summary block at the end of the report
- Code-chief owns the gatekeeper-code validation cycle in pipeline mode

**When invoked standalone:**
- Execute the full security review workflow independently
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` skill is available, self-validate by confirming each finding has a verifiable code path, correct CWE mapping, and justified CVSS score

In both modes, the gatekeeper-code applies especially rigorous scrutiny to security findings: Are CWE mappings accurate? Are CVSS scores justified by the actual exploit scenario? Were all relevant OWASP categories checked? Were AI-specific threats considered for code touching AI components? Were supply chain implications evaluated for dependency changes? For High-risk tier reviews, load the full checklist from `references/secure-coding-checklist.md`. For Low-risk tier reviews, the summary in this file is sufficient.

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No security-relevant code in change | Report "No security-relevant changes detected" with evidence of what was examined. Skip full checklist but note any pre-existing issues observed. |
| Embedded secrets in code | Classify as Critical immediately. Do not include the secret value in the report. Reference the file:line and state "secret detected — credential type: [API key/password/token]." Recommend rotation. |
| Third-party dependency with known CVE | Report the CVE, CVSS score, and exploitability status. Check if the vulnerable code path is reachable from the application. If not reachable, classify as Major (not Critical) with justification. |
| Automated security gates did not run or produced no artifacts | Record a tooling gap, identify the missing gate, and manually inspect the corresponding control area. Do not claim clean automated coverage when evidence is absent. |
| New dependency has no CVE but shows suspicious maintainer turnover or install scripts | Treat it as a supply-chain concern even without a published CVE. Review provenance, install scripts, ownership changes, and package reputation before approving. |
| AI/ML model code without standard security patterns | Apply AI-specific threat assessment even if the code appears safe. Check for prompt injection vectors, training data exposure, model manipulation surfaces, and output sanitization. |
| Cryptographic code | Never approve custom cryptographic implementations without explicit justification. Flag any code that implements crypto primitives rather than using established libraries. |
| Legacy code with known vulnerabilities | Distinguish between new vulnerabilities introduced by the change and pre-existing issues. Report both but classify differently: new = Critical/Major, pre-existing = INFO with recommendation. |
| Insufficient context for threat modeling | State what context is missing. Perform a partial threat model with assumptions documented. Flag the assumptions as requiring validation. |
| Pure library code with no direct user input | Focus on API surface safety: can callers pass malicious input that the library propagates unsanitized? Review default configurations for secure-by-default behavior and check for unsafe deserialization, path traversal, or command-injection vectors reachable through public API parameters. |

---

## Additional Resources

### Reference Files

For detailed frameworks, checklists, and supply chain procedures, consult:

- **`references/frameworks.md`** — NIST SSDF v1.1 (all four practice groups, PW.7 deep dive), OWASP ASVS 5.0.0 (levels and controls), OWASP SAMM v2 (maturity streams), OWASP Top 10:2025, CWE Top 25, Microsoft Continuous SDL, EU AI Act/RAD-AI, framework comparison tables, and compliance mapping anchors
- **`references/secure-coding-checklist.md`** — Complete secure coding review checklist covering input validation, output encoding, authentication, session management, access control, error handling, cryptography, logging, and AI-specific threats with detailed sub-items and verification procedures
- **`references/supply-chain.md`** — SBOM generation (CycloneDX v1.7, SPDX v3), SCA tools (Snyk, Dependency-Check, Dependabot), SLSA provenance levels and attestations, in-toto framework, Sigstore/cosign signing, secrets detection (TruffleHog v3, Gitleaks, GitHub Secret Scanning), and end-to-end supply chain gate implementation

---
*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the review report, write it to the designated save path as `deliverable_{report-name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 4
   skill: security-review
   name: Security Review Report
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
