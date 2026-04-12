# Security Frameworks — Detailed Reference

This reference provides comprehensive descriptions of each security framework applicable to secure code review, with comparison tables and compliance mapping anchors.

---

## NIST SSDF v1.1 (SP 800-218)

The National Institute of Standards and Technology Secure Software Development Framework is the definitive core framework for secure development. Mandatory for all US federal software suppliers under Executive Order 14028.

### Four Practice Groups

**1. Prepare the Organization (PO):**
- Ensure development environments, personnel, and tooling are equipped for secure development
- Define security requirements for software to be developed or acquired
- Train personnel on secure development practices

**2. Protect the Software (PS):**
- Protect all forms of code from unauthorized access and tampering
- Utilize zero-trust architectures for development endpoints
- Store source, binaries, and configuration-as-code with least-privilege access
- **PS.3.2:** Collect and safeguard provenance data for each release (explicitly includes SBOM)
- Reference commit signing as a code integrity mechanism

**3. Produce Well-Secured Software (PW):**
- Adhere to secure coding practices to minimize vulnerabilities
- Configure compilation, interpreter, and build processes to proactively eliminate vulnerabilities
- **PW.7: Review and/or Analyze Human-Readable Code** — the practice most directly relevant to code review:
  - Explicitly calls out both **people reviewing code** and **tools analyzing code**
  - Requires recording and triaging discovered issues
  - Recommends choosing review/analysis methods based on development stage
  - Supports static analysis tools combined with human review and checklists
  - References SP 800-53 controls SA-11 and SA-15 in compliance mappings

**4. Respond to Vulnerabilities (RV):**
- Identify, document, and structurally address root causes of discovered issues
- Use automated static analysis combined with human peer review
- Establish vulnerability disclosure and response processes

### SSDF v1.2 Draft (December 2025)
Added practices for secure delivery and AI-specific security considerations. Extends PW.7 with guidance for reviewing AI-generated code.

### Compliance Mapping
SSDF maps directly to NIST SP 800-53 controls, providing a bridge from engineering practice to control-family language:
- PW.7 → SA-11 (Developer Testing and Evaluation), SA-15 (Development Process)
- PS.3.2 → SA-10 (Developer Configuration Management), includes SBOM requirements

---

## OWASP ASVS 5.0.0

The OWASP Application Security Verification Standard provides granular, technical control requirements for web applications, microservices, and APIs.

### Three Compliance Levels

**Level 1 — Opportunistic:**
- Basic hygiene controls for low-risk applications
- Suitable for: brochure sites, internal tools handling non-sensitive data
- Verification method: Automated scanning + basic review

**Level 2 — Standard:**
- Recommended for the majority of business applications
- Suitable for: applications handling personal data, financial data, business-critical operations
- Verification method: Automated scanning + thorough manual review + security testing

**Level 3 — Advanced:**
- Extreme rigor for mission-critical infrastructure
- Suitable for: medical health data systems, autonomous safety controls, core financial infrastructure
- Verification method: All Level 2 methods + architecture review + formal threat modeling + penetration testing

### Using ASVS as Review Checklist

Convert ASVS controls into review checklist items:
- V2 (Authentication): Verify password policies, MFA implementation, credential storage
- V3 (Session Management): Verify session tokens, timeout, fixation prevention
- V4 (Access Control): Verify authorization checks, default deny, privilege escalation prevention
- V5 (Validation): Verify input validation, output encoding, injection prevention
- V6 (Cryptography): Verify algorithm selection, key management, random number generation
- V7 (Error Handling): Verify no information leakage, fail-secure behavior
- V8 (Data Protection): Verify data classification, encryption at rest/in transit
- V9 (Communication): Verify TLS configuration, certificate validation
- V10 (Malicious Code): Verify no backdoors, time bombs, or unauthorized data collection
- V13 (API): Verify API security controls, rate limiting, input validation

---

## OWASP SAMM v2

The Software Assurance Maturity Model provides a measurable maturity roadmap across the software lifecycle.

### Key Practices for Code Review

**Threat Assessment:**
- Risk profiling and risk-based threat modeling
- Begins with brainstorming and checklists, matures toward standardized tools
- Integration: Attach threat model deltas to PRs introducing new data flows or trust boundaries

**Secure Build:**
- Automated pipelines that include SAST/DAST and fail builds on security regressions
- Explicit "Software Dependencies" work tied to bills of materials
- Integration: CI gates with security scan results as required status checks

**Security Testing:**
- Structured security testing practices scaled by maturity level
- Integration: SAST in CI, DAST in staging, IAST during automated tests

**Defect Management:**
- Severity rating consistency across the organization
- SLAs for security defect remediation by severity class
- Integration: Unified defect tracking with severity-based response times

---

## OWASP Top 10:2025

The eighth installment, analyzing 2.8 million+ applications. Key changes relevant to code review:

| Rank | Category | Review Implication |
|------|----------|-------------------|
| #1 | Cross-Site Scripting (XSS) | Check all output encoding, template rendering, DOM manipulation |
| #2 | Cryptographic Failures | Verify algorithm choices, key management, data-at-rest encryption |
| #3 | Injection | Check all query construction, command execution, template rendering |
| #4 | Missing Authorization (↑5) | Verify every endpoint has authorization checks, default deny |
| #5 | Security Misconfiguration | Check default configurations, unnecessary features, error messages |
| — | Software Supply Chain Failures (NEW) | Verify dependency integrity, SBOM, provenance |
| — | AI-Generated Code Security (NEW) | First-ever guidance on reviewing AI-generated code risks |

### CWE Top 25 (2025 Edition)

Based on analysis of 39,080 CVEs. The most directly actionable weakness taxonomy for classifying findings.

**Top weakness classes:**
1. CWE-79: Cross-Site Scripting (score 60.38)
2. CWE-787: Out-of-Bounds Write
3. CWE-89: SQL Injection
4. CWE-862: Missing Authorization (↑5 places to #4)
5. CWE-22: Path Traversal
6. CWE-125: Out-of-Bounds Read
7. CWE-20: Improper Input Validation
8. CWE-78: OS Command Injection
9. CWE-416: Use After Free
10. CWE-476: NULL Pointer Dereference

Memory safety issues (buffer overflows, use-after-free) returned prominently, reinforcing the case for memory-safe languages (Rust, Go) in new projects.

---

## Microsoft Continuous SDL

Microsoft's Security Development Lifecycle evolved into "Continuous SDL" under the Secure Future Initiative. Expanded in February 2026.

### AI-Specific Threat Additions
- **Training data poisoning:** Corrupted training data producing biased or backdoored models
- **Prompt injection:** External inputs manipulating AI system instructions
- **Non-deterministic outputs:** Same input producing different outputs, complicating testing
- **Model extraction:** Adversaries reverse-engineering model behavior through API queries

### SDL in Code Review
- Threat modeling integral to design phase (not bolted on after implementation)
- Security requirements verified during review using checklists derived from SDL practices
- Continuous integration of security testing into development workflow

---

## EU AI Act / RAD-AI Framework

### EU AI Act (Regulation 2024/1689)
Enforcing strict compliance mandates for high-risk AI systems beginning August 2026. Requires comprehensive technical documentation for AI-augmented systems.

### RAD-AI Framework
Backward-compatible extension that augments standard documentation tools with AI-specific security concerns:

**Addresses:**
- Probabilistic behaviors (non-deterministic AI outputs)
- Data-dependent evolution (model behavior changing as training data changes)
- Dual machine-learning/software lifecycles
- Ecosystem-level threats (cascading data drift, compliance obligations)

**Impact:** Increases EU AI Act Annex IV addressability from approximately 36% to 93%.

**Applicable when:** Systems deploy AI in high-risk contexts — smart cities, autonomous vehicles, intelligent enterprise platforms, medical decision support.

---

## Framework Comparison Table

| Framework | Primary Focus | Best For | Implementation Complexity |
|-----------|--------------|----------|--------------------------|
| NIST SSDF v1.1 | SDLC security practices, root cause mitigation | Enterprise, government, procurement-driven | High: org-wide policy, zero-trust, training |
| OWASP ASVS 5.0.0 | Technical security controls for web/API | Web apps, SaaS, API developers, DevSecOps | Medium: CI integration, review checklists |
| OWASP SAMM v2 | Maturity model for software assurance | AppSec program building, maturity improvement | Medium: requires tailoring, ongoing assessment |
| Microsoft SDL | SDLC-integrated security approach | Enterprise, Microsoft ecosystem | Medium: lifecycle integration, threat modeling |
| OWASP Top 10 | Risk communication, awareness | Training, compliance justification | Low: awareness-focused, maps to controls |
| CWE Top 25 | Weakness taxonomy, finding classification | Security finding classification, prevention | Low: reference taxonomy, no process overhead |
| RAD-AI | AI-specific documentation and compliance | High-risk AI systems, EU AI Act compliance | High: ecosystem mapping, compliance reporting |

---

## Compliance Mapping Anchors

Use these mappings to connect code review findings to compliance requirements:

**NIST SSDF → NIST SP 800-53:**
- PW.7 → SA-11 (Developer Testing and Evaluation)
- PW.7 → SA-15 (Development Process, Standards, Tools)
- PS.3.2 → SA-10 (Developer Configuration Management)

**CWE / SANS Top 25:**
- Map each finding to its CWE ID for consistent classification
- SANS provides developer-focused prevention guidance aligned to CWE IDs

**MITRE ATT&CK:**
- Use as a threat-behavior reference to derive abuse cases
- Focus on CI/CD compromise (T1195), credential theft (T1078), supply-chain attacks
- Map realistic attacker behaviors to security test scenarios

**OWASP Top 10 + CI/CD Top 10:**
- Use as risk communication layer to justify security gates
- CI/CD Top 10 addresses: dependency chain abuse, poisoned pipeline execution, artifact integrity
