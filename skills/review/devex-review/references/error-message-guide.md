# Error Message Audit Guide

Use this guide when `devex-review` evaluates developer-facing errors in setup,
CLI, SDK, local environment, or upgrade flows.

## Three-Tier Severity Model

| Tier | Meaning | Example |
|------|---------|---------|
| **Blocking** | The developer cannot continue without outside help | Missing prerequisite with no recovery path |
| **Friction** | Progress is possible, but slow or confusing | Stack trace without a direct next action |
| **Polish** | The message works, but wastes time or confidence | Generic wording, inconsistent formatting |

## What Good Errors Include

Every high-quality developer-facing error should contain:

1. **What failed** — the failing command, config, or dependency
2. **Why it failed** — the actual cause, not just the symptom
3. **How to fix it** — a concrete next action or command
4. **Where to learn more** — link to docs, help command, or troubleshooting page

## Common Failure Patterns

- **Stack trace only**: technical detail with no human-actionable summary
- **Missing prerequisite, no guidance**: tells the user what is missing but not how to install or configure it
- **Contradictory recovery advice**: error suggests a path that the docs or CLI do not support
- **Silent exit**: non-zero exit code with no useful stderr output
- **Blame language**: wording that implies user fault instead of helping them recover

## Review Questions

When scoring an error message, ask:

1. Could a new developer recover without external help?
2. Is the next action specific enough to execute immediately?
3. Does the message point to the authoritative documentation when needed?
4. Is the wording consistent with the product's overall DX quality?

If the answer to any of these is no, record a finding with the missing element
and the expected remediation.