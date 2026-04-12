# Security Checklist Reference

## OWASP Top 10:2025 Mapping

### A01: Broken Access Control

| Check | Verification Procedure |
|-------|----------------------|
| Authorization on every endpoint | Trace each route handler — verify middleware or inline auth check before business logic |
| No IDOR (Insecure Direct Object Reference) | Verify all resource access checks ownership — `findById(id)` alone is insufficient; must be `findByIdAndUserId(id, userId)` |
| CORS configuration | Verify `Access-Control-Allow-Origin` is not `*` for authenticated endpoints |
| Method restriction | Verify routes only accept intended HTTP methods |
| Directory listing disabled | Verify static file serving does not expose directory listings |
| Rate limiting on sensitive endpoints | Verify login, registration, password reset have rate limits |

### A02: Cryptographic Failures

| Check | Verification Procedure |
|-------|----------------------|
| Password hashing | Verify bcrypt (cost ≥ 10), scrypt, or argon2id — never MD5, SHA-1, or SHA-256 alone |
| TLS configuration | Verify TLS 1.2+ enforced, no fallback to older protocols |
| Sensitive data at rest | Verify PII and credentials are encrypted in database |
| Key management | Verify encryption keys are not hardcoded, are rotatable, and stored in secret management |
| Random number generation | Verify cryptographic randomness for tokens, IDs, and secrets — not `Math.random()` |

### A03: Injection

| Check | Verification Procedure |
|-------|----------------------|
| SQL injection | Verify ALL database queries use parameterized statements — search for string concatenation in SQL |
| NoSQL injection | Verify query operators are not user-controllable (MongoDB `$gt`, `$regex`) |
| Command injection | Verify no user input reaches `exec()`, `system()`, `os.popen()` — use allowlists |
| XSS (reflected/stored) | Verify all user input is encoded before HTML/DOM rendering |
| LDAP injection | Verify LDAP queries escape special characters |
| Template injection | Verify server-side templates do not evaluate user input as expressions |

### A04: Insecure Design

| Check | Verification Procedure |
|-------|----------------------|
| Business logic flaws | Verify price calculations, discount logic, and quantity limits cannot be manipulated |
| Rate limiting | Verify brute-force-susceptible operations have progressive rate limits |
| Abuse scenarios | Verify bulk operations have limits (mass email, mass deletion) |

### A05: Security Misconfiguration

| Check | Verification Procedure |
|-------|----------------------|
| Default credentials | Verify no default admin passwords, API keys, or database credentials |
| Verbose errors | Verify production error responses do not leak stack traces, SQL queries, or internal paths |
| Unnecessary features | Verify debug endpoints, admin panels, and test routes are disabled in production |
| Security headers | Verify: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy |

### A06: Vulnerable and Outdated Components

| Check | Verification Procedure |
|-------|----------------------|
| Known CVEs | Run `npm audit` / `pip audit` / `go vuln check` — zero critical or high |
| Outdated dependencies | Flag packages > 2 major versions behind |
| Unmaintained packages | Flag packages with no activity in 12+ months |
| Lockfile committed | Verify lockfile exists in version control |

### A07: Identification and Authentication Failures

| Check | Verification Procedure |
|-------|----------------------|
| Credential stuffing protection | Verify account lockout or progressive delay after failed attempts |
| Session fixation | Verify session ID regeneration after login |
| Token security | Verify JWT uses strong algorithm (RS256/ES256, not HS256 with weak secret) |
| Session expiration | Verify sessions expire after inactivity and have absolute maximum lifetime |

### A08: Software and Data Integrity Failures

| Check | Verification Procedure |
|-------|----------------------|
| Deserialization safety | Verify no unsafe deserialization of user-supplied data (pickle, Java ObjectInputStream) |
| CI/CD integrity | Verify pipeline configurations are protected from unauthorized modification |
| Update mechanism | Verify software updates use signed packages |

### A09: Security Logging and Monitoring Failures

| Check | Verification Procedure |
|-------|----------------------|
| Authentication events logged | Verify login success/failure, logout, password change events are logged |
| Sensitive data excluded | Verify passwords, tokens, PII are NOT in logs |
| Log injection | Verify user input is sanitized before logging (newlines, control characters) |
| Tamper protection | Verify logs are write-once or integrity-protected |

### A10: Server-Side Request Forgery (SSRF)

| Check | Verification Procedure |
|-------|----------------------|
| URL validation | Verify user-supplied URLs are validated against allowlist |
| Internal network blocking | Verify requests cannot reach internal IPs (127.0.0.1, 10.x, 169.254.x, metadata endpoints) |
| Redirect following | Verify HTTP client does not follow redirects to internal resources |

---

## CWE Top 25 Weakness Patterns

High-priority weaknesses to scan for in implementation code:

| CWE ID | Weakness | Detection Pattern |
|--------|----------|------------------|
| CWE-79 | Cross-site Scripting | User input in HTML without encoding |
| CWE-89 | SQL Injection | String concatenation in SQL queries |
| CWE-78 | OS Command Injection | User input in exec/system calls |
| CWE-20 | Improper Input Validation | Missing or inadequate input validation |
| CWE-125 | Out-of-bounds Read | Array access without bounds check |
| CWE-787 | Out-of-bounds Write | Buffer operations without size check |
| CWE-862 | Missing Authorization | Endpoints without permission checks |
| CWE-798 | Hardcoded Credentials | Credentials in source code |
| CWE-306 | Missing Authentication | Sensitive operations without auth |
| CWE-502 | Deserialization of Untrusted Data | Unsafe deserialization |
| CWE-77 | Command Injection | User input reaching command execution |
| CWE-119 | Buffer Overflow | Unbounded memory operations |
| CWE-287 | Improper Authentication | Weak authentication mechanisms |
| CWE-269 | Improper Privilege Management | Privilege escalation paths |
| CWE-352 | Cross-Site Request Forgery | Missing CSRF tokens on state-changing operations |

---

## AI-Specific Threat Assessment

For applications that interact with AI/LLM systems:

| Threat | Check | Mitigation |
|--------|-------|------------|
| **Prompt Injection** | Can user inputs manipulate system instructions? | Separate system and user prompts, validate and sanitize inputs |
| **Data Poisoning** | Is training/fine-tuning data integrity validated? | Hash verification, trusted sources only |
| **Excessive Agency** | Are AI agent permissions scoped? | RBAC for tool access, human-in-the-loop for destructive actions |
| **PII Leakage** | Can sensitive data leak through prompts or responses? | PII detection and redaction in inputs and outputs |
| **Model Theft** | Are model weights and parameters protected? | Access controls, rate limiting on inference endpoints |

---

## Supply Chain Verification

| Check | Tool | Purpose |
|-------|------|---------|
| SBOM generation | syft, trivy | Generate Software Bill of Materials |
| Vulnerability scanning | grype, npm audit, pip audit | Detect known CVEs |
| License scanning | scancode, fossa | Detect license compliance issues |
| Secrets scanning | gitleaks, truffleHog | Detect committed secrets |
| Dependency pinning | Lockfile review | Verify reproducible builds |
