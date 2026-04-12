# Secure Coding Review Checklist

This checklist provides the complete secure coding review items for systematic security analysis. Derived from OWASP Secure Coding Practices, CERT Secure Coding Standards, OWASP ASVS 5.0.0, and CWE Top 25 analysis.

---

## 1. Input Validation and Canonicalization

### Core Requirements
- All user and system inputs are validated on a trusted server-side system, never relying on client-side validation
- Data sources are explicitly classified as trusted or untrusted
- Character sets (UTF-8) are specified for all inputs
- Input is encoded to a common character set before validation occurs
- All validation failures result in immediate input rejection (not sanitization/correction)

### Detailed Checks
- [ ] Input data types, lengths, and formats are strictly validated
- [ ] Whitelisting (allow-lists) is used over blacklisting (deny-lists)
- [ ] Structured data is validated against a schema (JSON Schema, XML Schema)
- [ ] File uploads validate: file type (magic bytes, not just extension), size limits, and content scanning
- [ ] URL inputs are validated against allow-listed domains and protocols
- [ ] Path inputs are canonicalized and validated against allowed directories (prevent traversal)
- [ ] Numeric inputs are range-checked (min/max bounds)
- [ ] Array/collection inputs have size limits to prevent resource exhaustion
- [ ] Multipart form data boundaries are handled correctly
- [ ] Unicode normalization is applied before validation (NFC/NFKC)

### Common Vulnerabilities Prevented
- CWE-20: Improper Input Validation
- CWE-22: Path Traversal
- CWE-89: SQL Injection (via input)
- CWE-78: OS Command Injection (via input)

---

## 2. Output Encoding

### Core Requirements
- Context-specific output encoding applied at the point of output, not at input
- Encoding strategy matches the output context (HTML, SQL, OS command, URL, LDAP, XML)
- No raw user input rendered in templates or responses

### Detailed Checks
- [ ] HTML output: entity encoding applied to all dynamic content (`<`, `>`, `&`, `"`, `'`)
- [ ] JavaScript context: JavaScript encoding for dynamic values in script blocks
- [ ] SQL context: parameterized queries / prepared statements used exclusively (no string concatenation)
- [ ] OS command context: parameterized APIs used instead of shell command construction; if unavoidable, command arguments are escaped
- [ ] URL context: URL encoding applied to dynamic path/query components
- [ ] CSS context: CSS encoding for dynamic style values
- [ ] HTTP header context: header values are validated/encoded to prevent header injection
- [ ] Template engines: auto-escaping is enabled and not bypassed (no `|safe`, `{!! !!}`, `dangerouslySetInnerHTML` without review)
- [ ] Content-Type headers: explicitly set on all responses (prevent MIME sniffing)
- [ ] Content-Security-Policy headers: configured to restrict inline scripts and unauthorized sources

### Common Vulnerabilities Prevented
- CWE-79: Cross-Site Scripting (XSS)
- CWE-89: SQL Injection (at output)
- CWE-78: OS Command Injection (at output)
- CWE-113: HTTP Response Splitting

---

## 3. Authentication

### Core Requirements
- Multi-factor authentication (MFA) enforced for user-facing applications
- Modern token-based authentication (OAuth2, OIDC) used for inter-service communication
- Passwords never embedded in source code
- Password storage uses slow, salted hashing algorithms (bcrypt or Argon2)

### Detailed Checks
- [ ] Authentication is enforced on all private resources and API endpoints
- [ ] Authentication logic is centralized (single authentication module, not per-endpoint)
- [ ] Failed authentication responses do not reveal which credential was incorrect ("Invalid username or password" not "Invalid password")
- [ ] Account lockout or rate limiting prevents brute-force attacks
- [ ] Password complexity requirements enforce minimum length (≥12 characters) and check against breach databases
- [ ] "Remember me" functionality uses secure, separate long-lived tokens (not session cookies)
- [ ] Password reset mechanisms use time-limited tokens and do not reveal whether an account exists
- [ ] API keys are treated as secrets: rotatable, revocable, scoped to minimum permissions
- [ ] Service-to-service authentication uses mutual TLS or JWT with proper audience/issuer validation
- [ ] Authentication tokens include anti-replay protections (nonce, timestamp)

### Common Vulnerabilities Prevented
- CWE-287: Improper Authentication
- CWE-798: Use of Hard-Coded Credentials
- CWE-307: Improper Restriction of Excessive Authentication Attempts

---

## 4. Session Management

### Core Requirements
- Session identifiers are generated using cryptographically secure random number generators
- Sessions have defined timeouts (idle and absolute)
- Session fixation attacks are prevented

### Detailed Checks
- [ ] Session IDs are regenerated after successful authentication (prevent fixation)
- [ ] Session IDs are regenerated after privilege level changes
- [ ] Session cookies set: `Secure` (HTTPS only), `HttpOnly` (no JavaScript access), `SameSite=Strict` or `Lax`
- [ ] Session timeout enforced: idle timeout (15-30 min for sensitive apps) and absolute timeout
- [ ] Logout functionality invalidates the server-side session (not just client cookie)
- [ ] Concurrent session limits enforced where appropriate
- [ ] Session data stored server-side (not in client-accessible cookies)
- [ ] CSRF tokens validated for state-changing requests (or SameSite cookies provide equivalent protection)

### Common Vulnerabilities Prevented
- CWE-384: Session Fixation
- CWE-613: Insufficient Session Expiration
- CWE-352: Cross-Site Request Forgery

---

## 5. Access Control

### Core Requirements
- Default deny policy: access is denied unless explicitly granted
- Principle of least privilege enforced at all levels
- Authorization checked on every request, not just UI visibility

### Detailed Checks
- [ ] Every API endpoint and resource access performs server-side authorization check
- [ ] Presentation-layer access control (hiding UI elements) is backed by server-side enforcement
- [ ] Direct object references (IDs in URLs/params) are validated against the authenticated user's permissions
- [ ] Administrative functions have separate, stricter authorization controls
- [ ] Access control policies are centralized and consistently enforced
- [ ] Privilege escalation paths are identified and protected (horizontal and vertical)
- [ ] Multi-tenant data isolation is enforced at the query/data access layer
- [ ] File access permissions are restrictive (no world-readable sensitive files)
- [ ] API rate limiting prevents abuse of authorized access
- [ ] Batch operations validate authorization for each item in the batch (not just the batch request)

### Common Vulnerabilities Prevented
- CWE-862: Missing Authorization
- CWE-863: Incorrect Authorization
- CWE-639: Authorization Bypass Through User-Controlled Key (IDOR)

---

## 6. Error Handling and Logging

### Core Requirements
- Error responses do not leak sensitive information to end users
- Security controls fail securely (deny access by default on error)
- Logging captures security-relevant events without logging sensitive data

### Detailed Checks — Error Handling
- [ ] Generic custom error pages are displayed to users (no stack traces, no database errors, no internal paths)
- [ ] Error handlers do not reveal system architecture, technology stack, or session identifiers
- [ ] Memory allocation failures or system errors in security controls result in access denial
- [ ] Application errors are logged with sufficient detail for investigation but sanitized for user display
- [ ] Error handling logic does not introduce new vulnerabilities (e.g., error path skipping authorization)
- [ ] Third-party error messages are wrapped before display to users

### Detailed Checks — Logging
- [ ] Logging controls are implemented on trusted, isolated systems
- [ ] Authentication events (success and failure) are logged
- [ ] Authorization failures are logged with user identity and requested resource
- [ ] Input validation failures are logged with sanitized input context
- [ ] No passwords, API keys, session tokens, or PII are included in log entries
- [ ] Log entries include: timestamp, severity, event type, user identity, source IP, outcome
- [ ] Log injection is prevented (user input in log messages is sanitized or parameterized)
- [ ] Audit logs are tamper-resistant (append-only, centralized, or cryptographically chained)
- [ ] Log retention policies comply with applicable regulations

### Common Vulnerabilities Prevented
- CWE-209: Generation of Error Message Containing Sensitive Information
- CWE-532: Insertion of Sensitive Information into Log File
- CWE-117: Improper Output Neutralization for Logs

---

## 7. Cryptography

### Core Requirements
- Only approved, well-reviewed cryptographic algorithms are used
- No custom cryptographic implementations
- Proper key management throughout the key lifecycle

### Detailed Checks
- [ ] Symmetric encryption: AES-256 in GCM mode (or ChaCha20-Poly1305)
- [ ] Hashing: SHA-256 or SHA-3 for integrity; bcrypt/Argon2id for passwords
- [ ] Deprecated algorithms not used: MD5, SHA-1, DES, 3DES, RC4
- [ ] No custom cryptography implementations (use well-established libraries: libsodium, OpenSSL, BoringSSL)
- [ ] Random number generation: cryptographically secure PRNG (`/dev/urandom`, `crypto.getRandomValues`, `secrets` module)
- [ ] Keys are never hardcoded in source code
- [ ] Key storage: use dedicated key management services (AWS KMS, HashiCorp Vault, Azure Key Vault)
- [ ] Key rotation: defined rotation schedule and procedures
- [ ] TLS 1.2+ enforced for all network communication; TLS 1.3 preferred
- [ ] Certificate validation is strict (no disabled checks, no self-signed in production)
- [ ] Initialization vectors (IVs) and nonces are never reused with the same key
- [ ] Sensitive data is encrypted at rest and in transit

### Common Vulnerabilities Prevented
- CWE-327: Use of a Broken or Risky Cryptographic Algorithm
- CWE-330: Use of Insufficiently Random Values
- CWE-321: Use of Hard-Coded Cryptographic Key

---

## 8. AI-Specific Security Threats

### Applicable When
Apply this section when the code change involves AI/ML components: model inference, training pipeline, prompt engineering, agent orchestration, or AI-powered features.

### Detailed Checks

**Prompt Injection:**
- [ ] User inputs are separated from system instructions (no concatenation of user input into system prompts)
- [ ] Output from AI models is treated as untrusted (validated/sanitized before use)
- [ ] Prompt templates use parameterization or structured formats
- [ ] Multi-turn conversations sanitize history to prevent injected instructions

**Data and Model Poisoning:**
- [ ] Training data sources are validated for integrity
- [ ] Data pipelines include anomaly detection for poisoned inputs
- [ ] Model checksums are verified before deployment
- [ ] Fine-tuning data is reviewed for adversarial content

**Excessive Agency:**
- [ ] AI agent permissions are scoped with strict RBAC (least privilege)
- [ ] Agents cannot execute unauthorized actions or escalate privileges
- [ ] Human-in-the-loop approval required for high-impact agent actions
- [ ] Agent action audit trails are maintained
- [ ] Output handling prevents agents from indirectly executing privileged operations

**Shadow AI:**
- [ ] No ungoverned data flows to unauthorized AI services
- [ ] All AI tool usage is registered and approved
- [ ] No sensitive PII or proprietary data leaked through system prompts or telemetry
- [ ] AI model API keys are managed as secrets with appropriate access controls

**Non-Deterministic Outputs:**
- [ ] AI outputs are validated against expected formats and ranges before use in critical paths
- [ ] Fallback behavior is defined for when AI outputs are unexpected or invalid
- [ ] Critical decisions do not rely solely on AI output without human verification

### Common Vulnerabilities
- Prompt injection (no CWE yet; OWASP LLM Top 10 addresses this)
- Data poisoning leading to corrupted outputs
- Excessive agency enabling privilege escalation through AI
- PII leakage through AI context windows
