# Severity Scoring — CVSS 4.0 Guide for Code-Level Findings

## CVSS 4.0 Overview

CVSS (Common Vulnerability Scoring System) version 4.0 provides a standardized
framework for rating vulnerability severity. For code-level findings in mr-robot,
the scoring process focuses on the **Base Score** metrics, adjusted by
**Threat** and **Environmental** context when available.

## Base Score Metrics

### Attack Vector (AV)

How can the attacker reach the vulnerable code?

| Value | Code-Level Interpretation | Score Impact |
|-------|--------------------------|-------------|
| **Network (N)** | Vulnerability reachable via HTTP/API endpoint, WebSocket, or any network protocol | Highest |
| **Adjacent (A)** | Reachable only from adjacent network (e.g., internal service mesh, VPN-only endpoint) | High |
| **Local (L)** | Requires local system access (CLI tools, local file processing, desktop apps) | Medium |
| **Physical (P)** | Requires physical device access (embedded systems, hardware interfaces) | Lowest |

### Attack Complexity (AC)

What conditions beyond the attacker's control must exist?

| Value | Code-Level Interpretation |
|-------|--------------------------|
| **Low (L)** | No special conditions. Vulnerability is always exploitable when the code path is reached. |
| **High (H)** | Exploit requires specific conditions: race condition timing, specific configuration, chained prerequisites, or particular data state. |

### Attack Requirements (AT) — New in CVSS 4.0

Are there deployment-specific conditions required?

| Value | Code-Level Interpretation |
|-------|--------------------------|
| **None (N)** | Exploitable in any deployment configuration. |
| **Present (P)** | Requires specific deployment conditions (e.g., debug mode enabled, specific OS, particular cloud provider). |

### Privileges Required (PR)

What authentication level does the attacker need?

| Value | Code-Level Interpretation |
|-------|--------------------------|
| **None (N)** | Unauthenticated. Public endpoint, no session required. |
| **Low (L)** | Authenticated user. Standard user session, API key. |
| **High (H)** | Privileged user. Admin, superuser, or service account. |

### User Interaction (UI) — Expanded in CVSS 4.0

Does exploitation require a victim to perform an action?

| Value | Code-Level Interpretation |
|-------|--------------------------|
| **None (N)** | No user interaction required. Fully automated exploitation. |
| **Passive (P)** | Victim must be using the system normally (e.g., viewing a page with stored XSS). |
| **Active (A)** | Victim must perform a specific action (e.g., clicking a crafted link, submitting a form). |

### Impact Metrics

Assess CIA impact on the **Vulnerable System** and **Subsequent Systems**:

| Metric | None (N) | Low (L) | High (H) |
|--------|---------|---------|----------|
| **Confidentiality** | No data exposure | Limited data exposure (non-sensitive or partial) | Full data breach (PII, credentials, financial data) |
| **Integrity** | No data modification | Limited data modification (non-critical) | Complete data manipulation, code execution |
| **Availability** | No service disruption | Degraded service, partial outage | Complete service outage, resource exhaustion |

---

## Scoring Examples for Common Code Vulnerabilities

### SQL Injection (Unauthenticated, Public Endpoint)

| Metric | Value | Justification |
|--------|-------|---------------|
| AV | Network | Reachable via HTTP |
| AC | Low | No special conditions |
| AT | None | Works in any deployment |
| PR | None | No authentication required |
| UI | None | Automated exploitation |
| VC | High | Full database access |
| VI | High | Can modify all data |
| VA | High | Can DROP tables |

**Score: 9.3 (Critical)**

### Stored XSS (Authenticated User Input)

| Metric | Value | Justification |
|--------|-------|---------------|
| AV | Network | Stored payload served via web |
| AC | Low | Payload always executes |
| AT | None | Any browser |
| PR | Low | Must be authenticated to inject |
| UI | Passive | Victim views the page normally |
| VC | Low | Session token theft |
| VI | Low | Can modify displayed content |
| VA | None | No availability impact |

**Score: 5.4 (Medium)**

### IDOR / BOLA (Authenticated Endpoint)

| Metric | Value | Justification |
|--------|-------|---------------|
| AV | Network | API endpoint |
| AC | Low | Simple ID manipulation |
| AT | None | Any deployment |
| PR | Low | Standard user session |
| UI | None | Automated |
| VC | High | Access to all user data |
| VI | Low | Can modify other users' data |
| VA | None | No availability impact |

**Score: 7.1 (High)**

### Race Condition in Payment Processing

| Metric | Value | Justification |
|--------|-------|---------------|
| AV | Network | API endpoint |
| AC | High | Requires precise timing |
| AT | None | Any deployment |
| PR | Low | Authenticated user |
| UI | None | Automated |
| VC | None | No data exposure |
| VI | High | Double-spend, financial manipulation |
| VA | None | No availability impact |

**Score: 5.3 (Medium)** — High AC reduces score despite High integrity impact

### Hardcoded API Key in Source Code

| Metric | Value | Justification |
|--------|-------|---------------|
| AV | Network | Key grants network access to services |
| AC | Low | Key is directly visible |
| AT | None | Key works in any deployment |
| PR | None | Anyone with code access |
| UI | None | Copy and use |
| VC | High | Full access to API resources |
| VI | High | Can perform actions as the service |
| VA | Low | Could potentially exhaust quotas |

**Score: 9.3 (Critical)** — if the code is in a public repository

---

## Exploit Chain Severity Aggregation

When multiple vulnerabilities combine into an exploit chain, score the **chain
as a whole**, not individual links:

1. **Attack Vector**: Use the vector of the initial entry point (usually the most accessible)
2. **Attack Complexity**: Use HIGH if any link in the chain requires specific conditions
3. **Privileges Required**: Use the privileges required for the first step
4. **User Interaction**: Use the most demanding interaction required across the chain
5. **Impact**: Use the final impact of the completed chain (often highest)

**Example:** XSS → Session Hijack → Admin Access → Data Exfiltration
- Individual XSS: Medium (5.4)
- Chain result: Critical (9.1) — because the final impact is full admin compromise

---

## Risk Tier Classification

For consistency with security-review, map CVSS scores to risk tiers:

| Risk Tier | CVSS Range | Action Required |
|-----------|-----------|-----------------|
| **Critical** | ≥ 9.0 | Block deployment. Immediate remediation. 72-hour SLA. |
| **High** | 7.0–8.9 | Block production deployment. 7-day remediation SLA. |
| **Medium** | 4.0–6.9 | Track and remediate. 30-day SLA. |
| **Low** | < 4.0 | Informational. 90-day SLA. |
| **Informational** | N/A | No CVSS score. Theoretical or hardening recommendation. |

---

## Key Rules for mr-robot Scoring

1. **Proven exploitability raises severity.** A vulnerability with a working exploit chain should score at least Medium, regardless of individual metric scores.
2. **Theoretical vulnerabilities get capped.** Without preconditions, steps, and impact demonstration, findings are classified as Informational.
3. **Context matters.** An IDOR in a social media profile is different from an IDOR in a healthcare records system. Adjust Environmental metrics when context is known.
4. **Chain over individual.** Always score exploit chains holistically, not by averaging individual link scores.
5. **Consistency with security-review.** When mr-robot and security-review score the same issue, severity must align. Discrepancies are flagged for gatekeeper-code consistency challenge.
