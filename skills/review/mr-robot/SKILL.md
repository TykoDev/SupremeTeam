---
name: mr-robot
description: >-
  This skill should be used when the user asks to "hack this code",
  "penetration test this codebase", "find exploitable vulnerabilities",
  "red team this application", "test attack scenarios", "run
  mr-robot", "simulate an attacker", "try to break this", "exploit
   this", "find attack chains", or "can an attacker abuse this
   flow?", "are there security holes here?", or "can this code be hacked?". Adversarial penetration testing
  using OWASP Testing Guide, PTES, and MITRE ATT&CK with
  proof-of-concept exploit chains. Produces exploit narratives
  with reproduction steps, not just vulnerability lists.
  DO NOT USE for defensive security review (use security-review).
  DO NOT USE for general code review (use code-review). DO NOT USE
  for build-phase security auditing (use security-builder).
version: 1.0.0
---

# mr-robot — Adversarial Penetration Testing Specialist

## Purpose

Perform systematic adversarial exploitation analysis of codebases. Where `security-review` asks "does this code follow secure coding practices?" (defensive), ask instead "can I exploit this code, and can I prove it?" (offensive). Construct realistic attack chains, validate that security controls actually hold under adversarial conditions, and identify exploitation paths that defensive scanning misses.

Every finding must include a proof-of-concept-level description: the attack preconditions, the exploitation steps, the resulting impact, and the specific code paths involved. Theoretical vulnerabilities without a plausible exploitation path are downgraded or excluded.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

## Differentiation from security-review

| Aspect | security-review | mr-robot |
|--------|----------------|----------|
| **Perspective** | Defender: "Is this secure?" | Attacker: "Can I break this?" |
| **Methodology** | Compliance checklists (NIST, OWASP ASVS) | Attack methodologies (PTES, OWASP Testing Guide) |
| **Output** | Finding + framework mapping | Exploit chain + proof-of-concept |
| **Depth** | Broad coverage, standards-based | Deep exploitation of specific attack surfaces |
| **Supply chain** | Dependency vulnerability scanning | Supply chain attack simulation (confusion, typosquat) |
| **AI threats** | Framework compliance (EU AI Act) | Prompt injection PoC, jailbreak testing |

Both skills are complementary in the pipeline: security-review establishes the compliance baseline, mr-robot validates it under attack conditions.

## Adversarial Analysis Workflow

Use `references/attack-methodology.md` as the primary checklist source before
starting reconnaissance. It is the canonical mapping between OWASP Testing
Guide v4.2, PTES phases, and the exploit-chain workflow used here.

### Phase 1: Reconnaissance — Map the Attack Surface

Before hunting for vulnerabilities, build a complete map of what can be attacked.

**Entry point inventory:**
- HTTP routes, API endpoints, GraphQL resolvers, WebSocket handlers
- CLI argument parsers, environment variable readers, configuration file loaders
- Message queue consumers, cron job triggers, webhook receivers
- File upload handlers, form processors, search endpoints

**Trust boundary mapping:**
- Where does untrusted input enter the system? (user input, external APIs, file uploads, database reads of user-controlled data)
- Where do privilege transitions occur? (authentication checkpoints, authorization gates, role switches)
- What data crosses trust boundaries without validation?

**Dependency graph analysis:**
- Direct and transitive dependency count
- Dependencies with known CVEs (cross-reference with security-review's SCA findings)
- Dependencies with recent maintainer changes or anomalous release patterns
- Abandoned dependencies (no commits in >12 months)

**Technology fingerprinting:**
- Framework versions and known framework-specific attack vectors
- Database types and query patterns (ORM vs raw queries)
- Authentication mechanisms (JWT, session cookies, OAuth, API keys)
- Serialization formats (JSON, XML, YAML, Protocol Buffers, MessagePack)

### Phase 2: Vulnerability Identification — Systematic Hunting

Apply structured vulnerability detection methodologies to the mapped attack surface.

**OWASP Testing Guide v4.2 categories (adapted for code review):**

| Category | Code-Level Focus |
|----------|-----------------|
| **Information Gathering** | Debug endpoints, verbose error responses, stack trace exposure, version headers |
| **Configuration & Deployment** | Hardcoded secrets, debug mode flags, permissive CORS, missing security headers |
| **Identity Management** | User enumeration via timing/response differences, weak username policies |
| **Authentication** | Password storage (bcrypt/argon2 vs MD5/SHA1), session fixation, brute force absence |
| **Authorization** | IDOR/BOLA patterns, missing authorization checks, privilege escalation paths |
| **Session Management** | Session token entropy, cookie attributes, session invalidation on auth changes |
| **Input Validation** | Injection points (SQL, NoSQL, command, LDAP, XPath, template), traversal |
| **Error Handling** | Information leakage via errors, fail-open patterns, unhandled exceptions |
| **Cryptography** | Weak algorithms, hardcoded keys, missing key rotation, improper IV/nonce |
| **Business Logic** | Race conditions in financial operations, workflow bypass, state manipulation |
| **Client-Side** | DOM-based XSS, prototype pollution, postMessage abuse, client-side auth |

**CWE Top 25 (2025) exploitation focus:**
- CWE-79 (XSS): Trace user input to unencoded output sinks
- CWE-89 (SQLi): Find string concatenation in query construction
- CWE-78 (OS Command Injection): Trace user input to exec/spawn/system calls
- CWE-862 (Missing Authorization): Find data-accessing operations without auth checks
- CWE-434 (Unrestricted Upload): Check file upload validation and storage
- CWE-502 (Deserialization): Find deserialization of untrusted data
- CWE-918 (SSRF): Trace user-controlled URLs to server-side HTTP requests

### Phase 3: Exploit Chain Construction — Prove Exploitability

For each identified vulnerability, construct a multi-step attack chain that demonstrates real-world exploitability.

**Exploit chain template:**

```markdown

---

## Exploit Chain: [Chain ID] — [Title]

### Classification
- **Primary CWE:** [CWE-ID]
- **CVSS 4.0 Score:** [score]
- **Severity:** [Critical / High / Medium / Low]
- **MITRE ATT&CK:** [Technique ID(s)]

### Preconditions
- [What must be true for this attack to work]
- [Required attacker position: unauthenticated / authenticated user / privileged user / network position]

### Attack Steps
1. [Step 1: entry point and initial action]
   - Code path: `[file:line]` → `[file:line]`
2. [Step 2: exploitation of vulnerability]
   - Code path: `[file:line]`
   - Payload: `[example payload or pattern]`
3. [Step 3: impact realization]
   - Result: [data exfiltration / privilege escalation / RCE / etc.]

### Impact
- **Confidentiality:** [None / Low / High]
- **Integrity:** [None / Low / High]
- **Availability:** [None / Low / High]

### Evidence
- [File path, line number, code snippet demonstrating the vulnerability]

### Remediation
- **Immediate:** [Quick fix]
- **Comprehensive:** [Proper architectural fix]
```

**Worked exploit chain:**

**Chain:** SSRF → Internal API Access → Credential Theft → Privilege Escalation

**Step 1 — Entry (SSRF):** `POST /api/preview` accepts a `url` parameter to generate link previews. No URL validation. Attacker submits `url=http://169.254.169.254/latest/meta-data/iam/security-credentials/`.

**Step 2 — Exploitation:** The server fetches the AWS metadata endpoint and returns the IAM role's temporary credentials (AccessKeyId, SecretAccessKey, Token) in the preview response body.

**Step 3 — Lateral Movement:** Attacker uses the stolen IAM credentials to call `sts:AssumeRole` and assume a higher-privilege role that has S3 read access.

**Step 4 — Exfiltration:** Attacker lists S3 buckets, downloads `backups/users-export.csv` containing 50k user records with email addresses and hashed passwords.

**CVSS v4.0:** 9.3 (Critical) — Network/Low/None/None → High confidentiality + high integrity impact
**CWE:** CWE-918 (SSRF) → CWE-522 (Insufficiently Protected Credentials) → CWE-269 (Improper Privilege Management)
**Remediation:** (1) Validate and allowlist URL schemes and destinations in `/api/preview`. (2) Block RFC 1918 and link-local addresses. (3) Run the preview service with minimal IAM permissions (no `sts:AssumeRole`). (4) Enable IMDSv2 (require PUT token) to block SSRF-based metadata access.

### Phase 4: Supply Chain Attack Simulation

Assess the codebase's resilience to software supply chain attacks.

**Dependency confusion / typosquatting check:**
- Scan package names for similarity to popular packages (character transposition, homoglyphs)
- Check for internal package names that could be shadowed by public registry packages
- Verify lock files are committed and integrity hashes are present

**Transitive vulnerability mapping:**
- Map the full transitive dependency tree
- Identify vulnerabilities in transitive dependencies that are reachable from application code
- Flag dependencies with a history of compromised releases

**Build pipeline integrity:**
- Check for unpinned actions/steps in CI/CD configuration
- Verify artifact integrity verification (checksums, signatures)
- Assess permissions scope in CI/CD runners

**Malicious code indicators:**
- Post-install scripts in dependencies that execute arbitrary code
- Obfuscated code in dependencies
- Network calls during package installation
- Dependencies with sole maintainers and recent ownership transfers

### Phase 5: API & Infrastructure Probing

For API-heavy applications, simulate API-specific attack patterns.

**OWASP API Security Top 10 (2023) exploitation:**
- **BOLA (API1):** Test for object-level authorization bypass by manipulating IDs
- **Broken Authentication (API2):** Test token handling, session management, credential stuffing resilience
- **BOPLA (API3):** Test property-level authorization (mass assignment, excessive data exposure)
- **Unrestricted Resource Consumption (API4):** Test rate limiting, pagination abuse, resource exhaustion
- **BFLA (API5):** Test function-level authorization (admin endpoints accessible to regular users)
- **SSRF (API7):** Test server-side request forgery via URL parameters
- **Security Misconfiguration (API8):** Test CORS, security headers, error verbosity

**JWT/session attack vectors:**
- Algorithm confusion (RS256 → HS256)
- None algorithm acceptance
- Weak signing key brute force
- Token expiration bypass
- Claim manipulation

### Phase 6: AI/LLM Threat Assessment

For applications integrating AI/LLM components (if applicable):

**Prompt injection testing:**
- Direct injection: Can user input override system prompts?
- Indirect injection: Can external data sources (web pages, documents, emails) inject instructions?
- Instruction extraction: Can the system prompt be leaked?

**Agent abuse testing:**
- Excessive agency: Are AI agent permissions scoped with RBAC?
- Tool abuse: Can the AI be tricked into calling dangerous tools?
- Data exfiltration: Can the AI be manipulated to expose training data or user data?

**Model security:**
- Training data poisoning vectors
- Model inversion / membership inference risks
- Output manipulation through adversarial inputs

---

## Severity Model

Uses CVSS 4.0 scoring anchored to exploitability proof:

| Severity | CVSS Range | Criteria |
|----------|-----------|---------|
| **Critical** | ≥ 9.0 | Proven exploitable with high impact. Unauthenticated remote exploitation possible. Data breach, RCE, or full system compromise. |
| **High** | 7.0–8.9 | Exploitable with moderate-to-high impact. May require authentication or specific conditions. Significant data exposure or privilege escalation. |
| **Medium** | 4.0–6.9 | Exploitable but with limited impact or high complexity. Requires chained exploitation or unusual conditions. |
| **Low** | < 4.0 | Theoretical vulnerability or requires highly unlikely preconditions. Minimal real-world impact. |

**Key rule:** A vulnerability without a plausible exploitation path (preconditions, steps, impact) is classified as **Informational**, not Low. mr-robot does not report theoretical issues without exploitation evidence.

Consult `references/severity-scoring.md` for the full CVSS 4.0 scoring guide.

---

## Output Format

```markdown
# ADVERSARIAL ANALYSIS REPORT

## Attack Surface Summary
- Entry points: [count]
- Trust boundaries: [count]
- Dependencies (direct/transitive): [n/n]
- Attack surface classification: [Minimal / Moderate / Extensive]

## Exploit Chains
[Ordered by severity, each following the Exploit Chain Template above]

## Supply Chain Assessment
- Lock file integrity: [PASS / FAIL]
- Dependency health: [n dependencies with concerns]
- Build pipeline security: [assessment]

## API Security Assessment (if applicable)
[OWASP API Top 10 coverage with findings]

## AI/LLM Threat Assessment (if applicable)
[Prompt injection, agent abuse, model security findings]

## Finding Summary
| ID | Title | Severity | CVSS | CWE | Exploitable | Remediation Priority |
|----|-------|----------|------|-----|-------------|---------------------|
| MR-001 | [title] | Critical | 9.2 | CWE-89 | Proven | Immediate |
| ... | ... | ... | ... | ... | ... | ... |

## Tool Recommendations
[Specific tools to run for automated validation of findings]
```

Append the following structured summary block at the end of every report for
pipeline consumption:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 5
skill: mr-robot
status: COMPLETE
risk_assessment: [High / Medium / Low]
finding_count:
  critical: [n]
  high: [n]
  medium: [n]
  low: [n]
  informational: [n]
exploit_chain_count: [n]
supply_chain_status: [Clean / Issues Found]
verdict: [High Risk / Medium Risk / Low Risk / Clean]
key_concerns: [top 3 exploit chains by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

---

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation with Phase 4 security-review findings as input
- Use security-review findings to guide targeted exploitation
- Submit completed report to code-chief (not directly to gatekeeper-code)
- Include the structured pipeline summary block at report end

**When invoked standalone:**
- Execute the full 6-phase adversarial analysis independently
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` skill is available, self-validate by confirming each exploit chain has verifiable code paths, correct CWE mapping, and justified CVSS score

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No exploitable vulnerabilities found | Document the attack surface analysis, techniques attempted, and why they did not succeed. A clean report is valid — do not manufacture findings. State confidence level. |
| Exploit chain requires runtime execution (cannot prove statically) | Document the theoretical chain with code references. Classify as "Likely" (not "Proven"). Recommend dynamic testing to confirm. |
| Supply chain attack surface is massive (100+ dependencies) | Focus on direct dependencies and those with known CVEs first. Use dependency tree analysis to prioritize transitive dependencies in the critical path. State scope limitations. |
| AI/LLM component detected but not directly in scope | Still assess AI-specific threats (prompt injection, model manipulation) if the code interacts with AI components even indirectly. Document the interaction boundary. |
| Proof-of-concept would require destructive actions | Document the exploit chain without executing destructive steps. Describe the proof-of-concept that WOULD confirm the vulnerability. Classify as "Likely" with the PoC plan documented. |
| Code is heavily obfuscated or minified | Note the limitation. Focus on API boundaries, input/output analysis, and dependency chain. Recommend deobfuscation before a thorough security review. |
| Target is accessible only behind VPN or private network | Limit reconnaissance to code-level analysis and document which network-dependent checks (SSRF callback, DNS rebinding, external dependency fetch) could not be validated. Classify network-dependent findings as "Likely" and recommend on-network testing. |
| Codebase contains only compiled artifacts (DLLs, JARs, binaries) without source | Focus on API surface, configuration, dependency manifest, and any decompilable metadata. State the source-unavailability limitation explicitly and recommend source-level review before signing off on security posture. |

---

## Additional Resources

### Reference Files

- **`references/attack-methodology.md`** — The primary attack-playbook reference covering OWASP Testing Guide v4.2 checks, PTES phases, and MITRE ATT&CK mapping for exploit-chain construction
- **`references/exploit-patterns.md`** — Language- and framework-specific exploit patterns, injection techniques, abuse primitives, and supply-chain indicators to match against the target stack
- **`references/severity-scoring.md`** — CVSS 4.0 scoring guide used to justify severity and exploitability ratings for code-level findings

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
   phase: 5
   skill: mr-robot
   name: Adversarial Analysis Report
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
