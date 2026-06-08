# Example Invocations

## Example 1

**User request:** investigate this issue

**Output:**
- Symptom timeline: checkout latency spiked immediately after a cache-key change and a gateway timeout configuration update.
- Finding: the root cause is the cache-key mismatch because timeouts alone do not explain the duplicate database fan-out seen in traces.
- Next move: fix the cache-key format and rerun the narrowed reproduction.

## Example 2

**User request:** find the root cause

**Output:**
- Evidence: production error logs, last deployment diff, and a failing background job trace all point to one missing environment variable in the new worker pool.
- Confidence: high because the failure reproduces when the variable is removed in staging.
- Next move: restore the variable and verify the worker queue drains normally.

## Example 3

**User request:** explain why this broke

**Output:**
- Bounded conclusion: two suspects remain because the relevant managed-service audit logs are inaccessible.
- Surviving suspects: certificate rotation timing and DNS cache staleness.
- Required escalation: obtain the missing platform logs before claiming a single root cause.
