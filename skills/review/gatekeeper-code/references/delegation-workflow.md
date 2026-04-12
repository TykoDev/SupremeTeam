# Delegation Workflow — Request/Response Format and Escalation

This reference provides the complete delegation mechanism for sending reports back to originating skills for rework, including format specifications, batch strategies, round limits, and escalation procedures.

---

## Delegation Request Format

When the gatekeeper identifies an issue through its challenge protocol, construct a delegation request targeting the originating skill.

### Standard Format

```
═══════════════════════════════════════════════
DELEGATION REQUEST
═══════════════════════════════════════════════
Request ID:        [DEL-NNNN]
Target Skill:      [bug-review | code-review | quality-review | security-review]
Finding ID:        [ID from original report, e.g., BUG-003, SEC-007]
                   [Use "GAP-" prefix for missing findings, e.g., GAP-AUTH-001]
Challenge Type:    [existence | accuracy | completeness | proportionality | consistency]
Round:             [1 | 2]
Priority:          [P0 | P1 | P2 | P3 | P4 | P5]

Specific Question:
[A precise, answerable question that the skill must address. Not vague —
the skill should know exactly what evidence or correction is needed.]

Evidence Required:
[What the skill must provide to resolve this challenge. Be specific about
what would constitute a satisfactory response.]

Context:
[Any additional context from the gatekeeper's analysis that helps the skill
understand why this challenge was raised.]
═══════════════════════════════════════════════
```

### Example Delegation Requests

**Example 1: Existence Challenge**
```
Request ID:        DEL-0001
Target Skill:      bug-review
Finding ID:        BUG-003
Challenge Type:    existence
Round:             1
Priority:          P2

Specific Question:
BUG-003 references a concurrent map access at `cache/store.go:112`, but the
file has only 98 lines. Where is the actual location of this issue?

Evidence Required:
Correct file path and line number where the concurrent map access occurs,
with the specific code snippet showing unsynchronized access.

Context:
The cache module was recently refactored (per git log). The finding may
reference a pre-refactoring line number.
```

**Example 2: Completeness Challenge**
```
Request ID:        DEL-0005
Target Skill:      security-review
Finding ID:        GAP-AI-001
Challenge Type:    completeness
Round:             1
Priority:          P3

Specific Question:
The code change modifies `ai/completion.py` lines 34-67 (prompt template
construction), but the security report does not include AI-specific threat
assessment. Was the AI Security Threats checklist applied?

Evidence Required:
Either: (a) Assessment results from applying the AI-specific threats checklist
to the prompt template changes, OR (b) Specific justification for why the
checklist is not applicable.

Context:
The modified code concatenates user input into the system prompt template,
which is a pattern associated with prompt injection vulnerabilities.
```

**Example 3: Proportionality Challenge (Round 2)**
```
Request ID:        DEL-0012
Target Skill:      bug-review
Finding ID:        BUG-012
Challenge Type:    proportionality
Round:             2
Priority:          P4

Specific Question:
In Round 1, bug-review defended the Major classification of BUG-012 (missing
log context field) by citing "operational impact on incident response." However,
the field in question (`request_id`) is already present in the HTTP access logs,
making it available for correlation without the application log. Given this
redundancy, does Major severity remain justified?

Evidence Required:
Either: (a) Evidence that `request_id` is NOT available through other log
sources, justifying Major severity, OR (b) Reclassification to Minor with
acknowledgment of the alternative log source.

Context:
HTTP access logs at `nginx/access.log` format include `$request_id` field.
Application logs at `app/structured.log` are the ones missing the field.
```

---

## Delegation Response Format

The originating skill must respond with one of three resolutions.

### Standard Format

```
═══════════════════════════════════════════════
DELEGATION RESPONSE
═══════════════════════════════════════════════
Request ID:        [DEL-NNNN — matching the request]
Finding ID:        [matching ID]
Resolution:        [corrected | defended | withdrawn]

Evidence:
[Specific evidence addressing the challenge. Must directly answer the
"Specific Question" and provide the "Evidence Required" from the request.]

Amended Finding:
[If resolution is "corrected," provide the revised finding with updated
location, classification, severity, or description. If "defended" or
"withdrawn," this section is "N/A".]
═══════════════════════════════════════════════
```

### Response Examples

**Example 1: Corrected**
```
Request ID:        DEL-0001
Finding ID:        BUG-003
Resolution:        corrected

Evidence:
After the refactoring, the concurrent map access moved to `cache/store.go:87`.
The `globalCache` map is written by `SetItem()` at line 87 and read by
`GetItem()` at line 73, both called from HTTP handlers without synchronization.

Amended Finding:
BUG-003 | Concurrency | Critical | `cache/store.go:87` — `globalCache` map
is read by `GetItem()` (line 73) and written by `SetItem()` (line 87) across
goroutines without synchronization. Under concurrent access, this causes a
fatal `concurrent map writes` panic.
```

**Example 2: Defended**
```
Request ID:        DEL-0012
Finding ID:        BUG-012
Resolution:        defended

Evidence:
While `request_id` is present in nginx access logs, the application logs
contain structured error context (stack traces, variable state, user session)
that cannot be correlated without `request_id` in the same log stream. The
operations team confirmed they rely on application log correlation for
debugging, not nginx access logs. Losing this correlation capability during
incidents justifies Major severity.

Amended Finding: N/A
```

**Example 3: Withdrawn**
```
Request ID:        DEL-0005
Finding ID:        SEC-009
Resolution:        withdrawn

Evidence:
Upon re-examination, the finding SEC-009 (SQL injection in `reports/query.py:45`)
is incorrect. The code uses Django ORM's `filter()` method with keyword arguments,
which generates parameterized queries internally. The user input does not reach
raw SQL. This was a false positive.

Amended Finding: N/A (finding removed from report)
```

---

## Round Limits and Escalation

### The 2-Round Maximum

Each finding is limited to a maximum of 2 delegation rounds. This hard cap prevents infinite back-and-forth loops that waste time and delay report delivery.

**Round 1:** Initial challenge. The skill provides evidence, corrects the finding, or withdraws it.

**Round 2:** If the Round 1 response is unconvincing, the gatekeeper issues a follow-up challenge with:
- A specific rebuttal explaining why the Round 1 evidence is insufficient
- A narrower, more precise question that leaves less room for ambiguity
- Clear criteria for what would constitute an acceptable response

**After Round 2:** If the skill and gatekeeper still disagree, the finding is marked as **"Disputed"** with both positions documented for the user.

### Escalation to Disputed Status

When a finding reaches Disputed status:

```
═══════════════════════════════════════════════
DISPUTED FINDING
═══════════════════════════════════════════════
Finding ID:        [ID]
Originating Skill: [skill name]
Challenge Type:    [type]

Skill Position:
[The skill's defense of its finding, with evidence provided in Rounds 1-2]

Gatekeeper Position:
[The gatekeeper's challenge, with evidence for why the skill's position
is insufficient]

User Action Required:
[What the user needs to decide — e.g., "Determine whether this finding
warrants remediation based on the evidence from both positions"]
═══════════════════════════════════════════════
```

### When to Skip Round 2

Not every Round 1 response requires a follow-up. Skip Round 2 when:
- The skill provided a clear correction with verifiable evidence → Accept
- The skill provided strong defense with specific evidence that directly addresses the challenge → Accept
- The skill withdrew the finding → Accept
- The challenge was based on a misunderstanding that the skill's response clarified → Accept

Issue Round 2 only when:
- The Round 1 evidence is ambiguous or incomplete
- The skill's defense contradicts observable code behavior
- The correction introduced a new inaccuracy
- The skill's response did not address the specific question asked

---

## Batch Delegation

### When to Batch

Group related challenges targeting the same skill into a single delegation request when:
- Multiple challenges relate to the same file or function
- Multiple findings share the same classification issue (e.g., systematic severity inflation)
- The challenges are interdependent (resolving one may resolve others)

### Batch Format

```
═══════════════════════════════════════════════
BATCH DELEGATION REQUEST
═══════════════════════════════════════════════
Batch ID:          [BATCH-NNNN]
Target Skill:      [skill name]
Challenge Count:   [N]
Round:             [1 | 2]

Challenge 1:
  Finding ID:      [ID]
  Challenge Type:  [type]
  Question:        [question]
  Evidence Needed: [what to provide]

Challenge 2:
  Finding ID:      [ID]
  Challenge Type:  [type]
  Question:        [question]
  Evidence Needed: [what to provide]

[... additional challenges ...]

Shared Context:
[Any context that applies to multiple challenges in this batch]
═══════════════════════════════════════════════
```

### Batch Response

The skill responds to each challenge individually within a single batch response, using the standard response format for each.

---

## Resolution Tracking Ledger

Maintain a ledger of all challenges, responses, and outcomes for the final gatekeeper report.

```
| Request ID | Skill | Finding ID | Challenge Type | Round | Resolution | Status |
|------------|-------|------------|----------------|-------|------------|--------|
| DEL-0001 | bug-review | BUG-003 | existence | 1 | corrected | Closed |
| DEL-0005 | security-review | GAP-AI-001 | completeness | 1 | applied | Closed |
| DEL-0008 | code-review | CR-Design | consistency | 1 | defended | Closed |
| DEL-0012 | bug-review | BUG-012 | proportionality | 2 | defended | Closed |
| DEL-0015 | security-review | SEC-003 | proportionality | 2 | — | Disputed |
```

**Status values:**
- **Closed:** Challenge resolved through correction, defense, or withdrawal
- **Disputed:** 2 rounds exhausted without resolution; user judgment required
- **Open:** Awaiting response (only during active delegation)

---

## Delegation Metrics

Track these metrics to calibrate the gatekeeper's effectiveness:

**Challenge Acceptance Rate:** Percentage of challenges that result in corrections or withdrawals (vs defended/disputed). A healthy range is 30–60%. Below 30% suggests the gatekeeper is too aggressive. Above 60% suggests the review skills need quality improvement.

**Average Rounds to Resolution:** Should be close to 1.0. If most challenges require Round 2, the challenge questions may be too vague.

**Dispute Rate:** Percentage of challenges that escalate to Disputed. Target: below 10%. High dispute rate indicates fundamental disagreement on standards — may need calibration discussion.

**Turnaround Time:** Time from delegation request to response. Delegation should not add significant latency to the overall review process.
