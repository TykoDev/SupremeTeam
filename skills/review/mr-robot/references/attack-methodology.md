# Attack Methodology — OWASP Testing Guide, PTES & MITRE ATT&CK

## OWASP Testing Guide v4.2 — Code Review Adaptation

The OWASP Testing Guide is designed for black-box testing of running
applications. This reference adapts each category for **code-level analysis**
— examining source code to identify the same vulnerabilities without executing
the application.

### OTG-INFO: Information Gathering

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-INFO-001 | Search for search engine-indexable sensitive paths in routing configuration |
| OTG-INFO-002 | Check web server configuration files for information leakage (server headers, version strings) |
| OTG-INFO-003 | Search for metadata in committed files (.git, .svn, .env, backup files) |
| OTG-INFO-004 | Enumerate all API endpoints from routing files and OpenAPI specs |
| OTG-INFO-005 | Check for comments containing sensitive information (credentials, TODOs about security) |
| OTG-INFO-006 | Identify debug endpoints, admin panels, and diagnostic routes |
| OTG-INFO-007 | Map all entry points that accept user input |

### OTG-CONFIG: Configuration & Deployment

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-CONFIG-001 | Check for debug mode enabled in production configuration |
| OTG-CONFIG-002 | Verify security headers (CSP, HSTS, X-Frame-Options) in server configuration |
| OTG-CONFIG-003 | Search for hardcoded credentials (API keys, passwords, tokens, connection strings) |
| OTG-CONFIG-004 | Check for permissive CORS configuration (`Access-Control-Allow-Origin: *`) |
| OTG-CONFIG-005 | Verify TLS configuration (minimum version, cipher suites, certificate pinning) |
| OTG-CONFIG-006 | Check for default credentials in database seed files or configuration |
| OTG-CONFIG-007 | Verify file permissions and directory listing configuration |

### OTG-AUTHN: Authentication

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-AUTHN-001 | Verify password storage uses bcrypt, argon2, or scrypt (not MD5, SHA1, SHA256 unsalted) |
| OTG-AUTHN-002 | Check for user enumeration via timing differences or response content variation |
| OTG-AUTHN-003 | Verify brute force protection (account lockout, rate limiting, CAPTCHA) |
| OTG-AUTHN-004 | Check session fixation (session regeneration after authentication) |
| OTG-AUTHN-005 | Verify password reset flow (token entropy, expiration, one-time use) |
| OTG-AUTHN-006 | Check MFA implementation (bypass paths, recovery codes, fallback mechanisms) |
| OTG-AUTHN-007 | Verify OAuth/OIDC implementation (state parameter, PKCE, token validation) |

### OTG-AUTHZ: Authorization

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-AUTHZ-001 | Search for IDOR/BOLA patterns (user-supplied IDs used without ownership verification) |
| OTG-AUTHZ-002 | Verify authorization checks on every data-accessing endpoint (not just UI hiding) |
| OTG-AUTHZ-003 | Check for privilege escalation paths (role switching, admin function access) |
| OTG-AUTHZ-004 | Verify horizontal authorization (user A cannot access user B's data) |
| OTG-AUTHZ-005 | Check for path traversal in file access operations |
| OTG-AUTHZ-006 | Verify that authorization checks are server-side (not client-side only) |

### OTG-INPVAL: Input Validation

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-INPVAL-001 | Trace user input to SQL query construction (parameterized queries vs concatenation) |
| OTG-INPVAL-002 | Trace user input to HTML output (encoding, sanitization, template auto-escaping) |
| OTG-INPVAL-003 | Trace user input to OS command execution (subprocess, exec, system calls) |
| OTG-INPVAL-004 | Trace user input to file system operations (path traversal, symlink following) |
| OTG-INPVAL-005 | Trace user input to LDAP, XPath, or other query languages |
| OTG-INPVAL-006 | Check deserialization of untrusted data (pickle, Java serialization, YAML, XML) |
| OTG-INPVAL-007 | Check for template injection (Jinja2, Handlebars, EJS, Twig) |
| OTG-INPVAL-008 | Trace user-controlled URLs to server-side HTTP requests (SSRF) |

### OTG-ERR: Error Handling

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-ERR-001 | Check for stack trace exposure in error responses |
| OTG-ERR-002 | Verify custom error pages replace framework defaults |
| OTG-ERR-003 | Check for information leakage in error messages (database names, file paths, query details) |
| OTG-ERR-004 | Verify fail-closed behavior (errors default to deny, not allow) |

### OTG-CRYPST: Cryptography

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-CRYPST-001 | Check for weak algorithms (MD5 for security, DES, RC4, ECB mode) |
| OTG-CRYPST-002 | Verify key management (no hardcoded keys, proper rotation, secure storage) |
| OTG-CRYPST-003 | Check for proper IV/nonce handling (unique per encryption, not reused) |
| OTG-CRYPST-004 | Verify TLS certificate validation (not disabled, proper hostname verification) |
| OTG-CRYPST-005 | Check for use of authenticated encryption (AES-GCM vs AES-CBC without HMAC) |

### OTG-BUSLOGIC: Business Logic

| Test ID | Code-Level Check |
|---------|-----------------|
| OTG-BUSLOGIC-001 | Check for race conditions in financial or state-changing operations |
| OTG-BUSLOGIC-002 | Verify workflow sequence enforcement (can steps be skipped or replayed?) |
| OTG-BUSLOGIC-003 | Check for insufficient anti-automation (rate limiting, CAPTCHA) |
| OTG-BUSLOGIC-004 | Verify idempotency for critical operations (double-submit prevention) |
| OTG-BUSLOGIC-005 | Check for time-of-check/time-of-use (TOCTOU) vulnerabilities |

---

## PTES — Penetration Testing Execution Standard (Code-Level Adaptation)

### PTES Phases for Code Review

| PTES Phase | Code Review Adaptation |
|------------|----------------------|
| **Pre-engagement** | Define review scope, identify assets, agree on rules of engagement (what code is in scope) |
| **Intelligence Gathering** | Map attack surface from code: entry points, data flows, trust boundaries, dependency graph |
| **Threat Modeling** | Identify threats using STRIDE categories; classify by attacker type (unauthenticated, authenticated, admin, insider) |
| **Vulnerability Analysis** | Apply OWASP Testing Guide checklist above; identify vulnerability classes present in the code |
| **Exploitation** | Construct exploit chains with preconditions, steps, and impact for each identified vulnerability |
| **Post-Exploitation** | Assess lateral movement paths: can exploitation of one component lead to compromise of others? |
| **Reporting** | Produce structured report per mr-robot output format |

---

## MITRE ATT&CK — Application & CI/CD Technique Mapping

### Application-Layer Techniques

| ATT&CK ID | Technique | Code Review Check |
|------------|-----------|-------------------|
| T1190 | Exploit Public-Facing Application | Check input validation on all public endpoints |
| T1059 | Command and Scripting Interpreter | Trace user input to exec/eval/system calls |
| T1203 | Exploitation for Client Execution | Check for DOM-based XSS and unsafe dynamic content |
| T1078 | Valid Accounts | Check for default credentials, weak password policies |
| T1110 | Brute Force | Verify rate limiting and account lockout mechanisms |
| T1552 | Unsecured Credentials | Search for hardcoded secrets, credentials in config files |
| T1048 | Exfiltration Over Alternative Protocol | Check for SSRF vectors enabling data exfiltration |
| T1565 | Data Manipulation | Check for missing integrity validation on critical data |

### CI/CD Specific Techniques

| ATT&CK ID | Technique | CI/CD Check |
|------------|-----------|-------------|
| T1195.002 | Supply Chain Compromise — Software Supply Chain | Check dependency integrity, lock files, SRI |
| T1199 | Trusted Relationship | Check CI/CD service account permissions (least privilege) |
| T1136 | Create Account | Check for unauthorized account creation in CI/CD |
| T1098 | Account Manipulation | Check CI/CD pipeline permissions and bypass mechanisms |
| T1588.001 | Obtain Capabilities — Malware | Check for suspicious post-install scripts in dependencies |

---

## Attacker Profiles

When constructing exploit chains, consider the attacker's position:

| Profile | Access Level | Typical Goals |
|---------|-------------|---------------|
| **External Unauthenticated** | No access, public endpoints only | Data theft, system compromise, DoS |
| **Authenticated User** | Standard user session | Privilege escalation, IDOR, data of other users |
| **Privileged User** | Admin/staff access | Further escalation, lateral movement, data exfiltration |
| **Insider / Supply Chain** | Code or dependency access | Backdoor insertion, credential theft, data manipulation |
| **CI/CD Attacker** | Pipeline access | Build compromise, artifact tampering, secret extraction |
