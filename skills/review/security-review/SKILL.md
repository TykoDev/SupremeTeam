---
name: security-review
description: >-
  This skill should be used when the user asks to "review security",
  "check for vulnerabilities", "do a security audit", "review for OWASP
  issues", "check authentication code", "assess supply chain security",
  "review cryptography usage", "check for injection vulnerabilities",
  "assess AI security", or "check compliance with NIST SSDF". It performs
  systematic security analysis using NIST SSDF, OWASP ASVS, CWE Top 25,
    and threat modeling with risk-tiered review depth. Distinct from
    security-builder (build pipeline): security-review operates during the
    review phase, analyzing shipped code with STRIDE threat modeling and
    supply chain evaluation.
version: 1.0.0
---

# Security Review Specialist

## Purpose

This skill performs dedicated security analysis focused exclusively on exploitability, security requirements compliance, and threat mitigation. It is distinct from bug-review (which targets correctness defects) and code-review (which applies a holistic assessment). The sole objective is to identify code that can be exploited by adversaries, violates security requirements, or introduces vulnerabilities into the software supply chain. All findings are mapped to established security frameworks and weakness taxonomies.

## Frameworks Alignment

Anchor every security review to the applicable frameworks. Select the frameworks relevant to the project's regulatory and risk context.

**NIST SSDF v1.1 (SP 800-218).** The definitive secure development practice framework. Practice PW.7 specifically mandates reviewing and analyzing human-readable code to identify vulnerabilities and verify compliance with security requirements, calling out both human review and automated analysis tools. Mandatory for all US federal software suppliers under Executive Order 14028.

**OWASP ASVS 5.0.0.** Granular technical control requirements for web applications, microservices, and APIs. Three compliance levels: Level 1 (basic hygiene for low-risk apps), Level 2 (standard for most business applications handling personal/financial data), Level 3 (extreme rigor for mission-critical infrastructure). Use ASVS controls as the review checklist baseline.

**OWASP Top 10:2025.** The eighth installment, analyzing 2.8 million+ applications. Includes Software Supply Chain Failures as a standalone category and first-ever guidance on AI-generated code security risks. Cross-Site Scripting holds #1 (score 60.38), Missing Authorization surged to #4.

**CWE Top 25 (2025).** Based on analysis of 39,080 CVEs. Use as the weakness taxonomy for classifying findings. Memory safety issues (buffer overflows) returned prominently, reinforcing the case for memory-safe languages.

**Microsoft Continuous SDL.** Expanded under the Secure Future Initiative to address AI-specific threats: training data poisoning, prompt injection, and non-deterministic outputs.

**EU AI Act / RAD-AI.** For systems deploying AI in high-risk contexts, RAD-AI extends standard documentation to capture probabilistic behaviors, data-dependent evolution, and dual ML/software lifecycles. Increases EU AI Act Annex IV addressability from ~36% to 93%.

Consult `references/frameworks.md` for detailed framework descriptions, comparison tables, and compliance mapping anchors (SSDF to SP 800-53, CWE/SANS, MITRE ATT&CK).

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

**Input Validation.** All inputs validated for type, length, format on the server side. Character sets specified (UTF-8). Validation failures result in immediate rejection. Data sources classified as trusted or untrusted.

**Output Encoding.** Context-specific encoding applied: HTML entity encoding for web output, parameterized queries for SQL, command escaping for OS commands. No raw user input rendered in templates.

**Authentication.** MFA enforced. OAuth2/OIDC for inter-service communication. No embedded passwords. Password storage uses bcrypt or Argon2. Proper token rotation and secure cookie handling.

**Session Management.** Secure session identifiers, proper expiration, session fixation prevention, secure cookie attributes (Secure, HttpOnly, SameSite).

**Access Control.** Default deny policies. Least privilege enforcement. No direct object references without authorization checks. Prevent lateral movement through strict RBAC.

**Error Handling.** No sensitive information in error responses (no stack traces, session IDs, architecture details to end users). Generic custom error pages. Security controls fail securely (deny by default on error).

**Cryptography.** Approved algorithms only (no MD5, no SHA-1 for security purposes, no custom crypto). Proper key management. Keys never hardcoded.

**Logging.** No sensitive data in logs (no passwords, tokens, PII). Tamper-resistant logging on isolated systems. Sufficient context for incident investigation.

## Output Format

Structure the security review report as follows:

```
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

## Additional Resources

### Reference Files

For detailed frameworks, checklists, and supply chain procedures, consult:

- **`references/frameworks.md`** — NIST SSDF v1.1 (all four practice groups, PW.7 deep dive), OWASP ASVS 5.0.0 (levels and controls), OWASP SAMM v2 (maturity streams), OWASP Top 10:2025, CWE Top 25, Microsoft Continuous SDL, EU AI Act/RAD-AI, framework comparison tables, and compliance mapping anchors
- **`references/secure-coding-checklist.md`** — Complete secure coding review checklist covering input validation, output encoding, authentication, session management, access control, error handling, cryptography, logging, and AI-specific threats with detailed sub-items and verification procedures
- **`references/supply-chain.md`** — SBOM generation (CycloneDX v1.7, SPDX v3), SCA tools (Snyk, Dependency-Check, Dependabot), SLSA provenance levels and attestations, in-toto framework, Sigstore/cosign signing, secrets detection (TruffleHog v3, Gitleaks, GitHub Secret Scanning), and end-to-end supply chain gate implementation

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

See `save-protocol.md` (project root) for complete format specifications.
