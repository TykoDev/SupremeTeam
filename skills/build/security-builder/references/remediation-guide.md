# Remediation Guide Reference

## Remediation Priority Matrix

Prioritize fixes based on severity and exploitability:

| | Easy to Exploit | Moderate to Exploit | Hard to Exploit |
|---|---|---|---|
| **Critical Impact** | Fix immediately (P0) | Fix within hours (P0) | Fix within 1 day (P1) |
| **High Impact** | Fix within hours (P0) | Fix within 1 day (P1) | Fix within 3 days (P2) |
| **Medium Impact** | Fix within 1 day (P1) | Fix within 3 days (P2) | Fix within sprint (P3) |
| **Low Impact** | Fix within 3 days (P2) | Fix within sprint (P3) | Backlog (P4) |

Within the build pipeline, all Critical and High findings must be resolved before delivery. Medium findings should be resolved. Low findings may be documented as accepted risk with justification.

---

## Fix Patterns by Vulnerability Category

### Injection Fixes

**SQL Injection (CWE-89):**
1. Replace all string concatenation in SQL with parameterized queries
2. Use ORM/query builder methods that auto-parameterize
3. Verify fix by searching for remaining string interpolation in SQL context
4. Add input validation as defense-in-depth (not as primary fix)

**XSS (CWE-79):**
1. Enable framework auto-escaping (enabled by default in React, Angular, Vue)
2. Replace `innerHTML` with `textContent` for user data
3. Implement Content-Security-Policy header
4. For rich text: use a sanitization library (DOMPurify) with strict allowlist

**Command Injection (CWE-78):**
1. Replace shell execution with library functions (use `sharp` instead of `imagemagick` CLI)
2. If shell execution is unavoidable: use array form (`subprocess.run([...], shell=False)`)
3. Validate input against strict allowlist (alphanumeric only for filenames)
4. Never pass user input to `eval()`, `exec()`, `system()`, or equivalents

### Authentication Fixes

**Weak Password Storage (CWE-916):**
1. Migrate to bcrypt (cost ≥ 10), scrypt, or argon2id
2. Implement migration: on next login, re-hash with strong algorithm
3. Force password reset for accounts with legacy hashes after migration period

**Broken Session Management (CWE-613):**
1. Regenerate session ID after login
2. Set session cookies: `httpOnly`, `secure`, `SameSite=Strict`
3. Implement absolute session timeout (e.g., 24 hours) and idle timeout (e.g., 30 minutes)
4. Invalidate session on logout (server-side, not just client-side cookie deletion)

### Access Control Fixes

**Missing Authorization (CWE-862):**
1. Add authorization middleware to all protected routes
2. Implement ownership checks on resource access endpoints
3. Apply principle of least privilege: default deny, explicit allow
4. Verify both horizontal (cross-user) and vertical (cross-role) access

**IDOR (CWE-639):**
1. Always include user/tenant context in database queries
2. Use indirect references (UUIDs) instead of sequential IDs where possible
3. Add ownership verification in the data access layer, not just the route handler

### Cryptographic Fixes

**Weak Algorithms (CWE-327):**
1. Replace MD5/SHA-1 with SHA-256 minimum for checksums
2. Replace custom encryption with AES-256-GCM
3. Replace weak JWT algorithms: use RS256 or ES256 instead of HS256 with weak secret
4. Update TLS configuration to require TLS 1.2+

**Hardcoded Credentials (CWE-798):**
1. Move all secrets to environment variables
2. Create `.env.example` with placeholder values
3. Add `.env` to `.gitignore`
4. Rotate any credentials that were previously committed (they must be considered compromised)

---

## Verification Procedures

After applying each fix, verify it resolves the finding:

### Verification Checklist

| Fix Category | Verification Method |
|-------------|-------------------|
| SQL Injection | Confirm parameterized query syntax; attempt injection string in input |
| XSS | Confirm output encoding; attempt script tag in stored/reflected input |
| Command Injection | Confirm no shell execution with user input; attempt command separator characters |
| Auth bypass | Confirm middleware applied; test unauthenticated request returns 401 |
| IDOR | Confirm ownership check; test accessing another user's resource returns 403/404 |
| Hardcoded secrets | Confirm no credentials in source; grep for common patterns (password=, key=, token=) |
| Weak crypto | Confirm strong algorithm in use; verify key length and configuration |

### Regression Check

After applying fixes, verify:
1. Existing functionality still works (no broken behavior from security fixes)
2. No new security issues introduced by the fix
3. Tests still pass (unit and integration)
4. Fix addresses root cause, not just the specific exploit

---

## Remediation Report Format

Use this format when submitting remediation results back to build-management:

```markdown
# SECURITY REMEDIATION REPORT

## Summary
- Findings addressed: [count] Critical, [count] High, [count] Medium, [count] Low
- Findings deferred: [count] with justification
- Files modified: [count]

## Remediation Details

### [SEC-001]: [Finding Title]
- **Original Severity**: [Critical]
- **CWE**: [CWE-89 SQL Injection]
- **Fix Applied**: Replaced string concatenation with parameterized query
- **Files Modified**: src/user/user.repository.ts:42
- **Verification**: Confirmed parameterized syntax; tested with injection payload — query returns empty result instead of all records
- **Regression Check**: Existing user search tests pass; no behavior change for valid inputs

### [SEC-002]: [Finding Title]
...

## Deferred Findings
| ID | Severity | Reason for Deferral | Accepted Risk |
|----|----------|--------------------|--------------|
| SEC-005 | Low | Information disclosure in non-sensitive context | Minimal impact, no PII exposed |

## Updated Dependency List
[If dependencies were updated as part of remediation]

## Remaining Risk Assessment
[Summary of residual risk after remediation]
```

---

## Common Remediation Mistakes

### Mistake: Fixing Symptom, Not Root Cause

```
# BAD: Block specific attack string
if "DROP TABLE" in user_input:
    reject()
# Bypassed by: "drop/**/table", Unicode tricks, etc.

# GOOD: Fix root cause — parameterize the query
db.query("SELECT * FROM users WHERE name = $1", [user_input])
```

### Mistake: Adding Validation Without Encoding

Input validation and output encoding serve different purposes. Both are needed:
- **Input validation**: Reject malformed data (wrong type, length, format)
- **Output encoding**: Neutralize special characters before rendering in specific context (HTML, SQL, shell)

Validation alone does not prevent injection if the query is still concatenated.

### Mistake: Client-Side Only Fix

```
# BAD: Only disable button in frontend
<button disabled={!isAdmin}>Delete All</button>

# GOOD: Server-side enforcement
app.delete("/api/admin/clear", requireRole("admin"), handler)
```

Always enforce security server-side. Client-side controls are UX, not security.
