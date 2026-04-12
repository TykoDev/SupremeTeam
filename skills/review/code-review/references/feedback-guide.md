# Constructive Feedback Guide

This reference provides detailed guidance on writing effective code review feedback, with examples, anti-patterns, and practical conventions.

---

## Core Principles

### The 15% Insight

Microsoft's study of 900+ developers found that only ~15% of code review comments address real defects. The bulk target style and formatting — issues that automated linters should handle. This insight should shape where human reviewers invest their energy:

- **Automate:** Style, formatting, naming conventions, import ordering, known vulnerability patterns
- **Human review:** Design decisions, business logic correctness, architecture alignment, security reasoning, test adequacy, edge cases

If a human reviewer is commenting on formatting, the team's automation pipeline has a gap.

### Constructive Framing

Review feedback is about improving the code, not evaluating the person. The goal is collaboration toward a shared outcome: code that the team is confident merging.

**Use "we" instead of "you":**
- Instead of: "You forgot to handle the error case"
- Use: "We should handle the error case here to prevent silent failures"

**Use "this" instead of "your":**
- Instead of: "Your implementation is inefficient"
- Use: "This implementation could be more efficient with a hash map lookup"

**Frame as improvement, not criticism:**
- Instead of: "This is wrong"
- Use: "This approach may produce incorrect results when X. Consider Y instead."

---

## Severity Prefix System

Mark every comment with its blocking level. This eliminates ambiguity about what must be fixed before merge.

### Blocking
Must be addressed before merge. Reserved for correctness, security, and design issues that would harm the codebase.

```
Blocking: This SQL query concatenates user input directly. Use parameterized queries to prevent injection.
```

### Nit
Non-blocking polish suggestion. The author may address or ignore without further discussion. These improve quality but are not required.

```
Nit: This variable name `d` could be more descriptive — something like `daysSinceLastLogin`?
```

### Optional
Explicit improvement suggestion that the author should consider but is not required to implement. Signals "I think this would be better, but I won't block on it."

```
Optional: We could extract this validation into a shared `validateEmail()` utility since it appears in three other places. Happy to leave it for a follow-up PR too.
```

### Question
Seeking understanding, not requesting a change. Signals "I need clarification to continue reviewing" or "I'm curious about the reasoning."

```
Question: Is there a reason we're using `setTimeout` instead of `requestAnimationFrame` here? Is it for compatibility?
```

### Praise
Positive feedback on well-crafted code. Important for morale and for reinforcing good patterns. Do not fabricate praise — genuine compliments on real quality.

```
Praise: The error handling in this retry logic is really clean. The exponential backoff with jitter is well-implemented.
```

---

## Feedback Transformations: Bad to Good

### Transformation 1: Vague to Specific

**Bad:** "This doesn't look right."
**Good:** "Blocking: `calculateDiscount()` at line 47 returns a negative value when `orderTotal` is zero, which causes a negative charge in `processPayment()`. We need a guard clause: `if (orderTotal <= 0) return 0`."

**Why:** Specific feedback is actionable. Vague feedback requires a follow-up conversation.

### Transformation 2: Personal to Code-Focused

**Bad:** "You don't understand how caching works."
**Good:** "This cache implementation stores the full response body in memory without a size limit or TTL. For our traffic volume (~10k req/s), we'd need to add eviction to prevent memory pressure."

**Why:** Focus on observable code behavior, not on the author's understanding.

### Transformation 3: Prescriptive to Collaborative

**Bad:** "Change this to use a factory pattern."
**Good:** "Optional: The three constructors here have overlapping initialization logic. A factory method could centralize this and reduce the surface for bugs. What do you think — worth the complexity here?"

**Why:** Invite discussion. The author may have context the reviewer lacks.

### Transformation 4: Tone-Deaf to Empathetic

**Bad:** "Why would you do it this way?"
**Good:** "Question: I notice this takes a different approach from our usual pattern in `services/`. Was there a specific constraint that led to this design?"

**Why:** Assume the author had a reason. Ask about it before criticizing.

### Transformation 5: Nitpick Overload to Prioritized

**Bad:** (15 comments, all about formatting and naming)
**Good:** "Nit: I have a few style suggestions — see inline. The main thing to address before merge is the missing error handling in `processOrder()` (line 89). The rest is optional polish."

**Why:** Prioritize blocking issues. Bundle non-blocking feedback as clearly secondary.

---

## The Sandwich Method (For New Developers)

When reviewing code from junior developers, new team members, or first-time contributors, use the sandwich method to maintain psychological safety:

1. **Genuine compliment:** Start with something the author did well
2. **Constructive suggestion:** Provide the improvement feedback
3. **Encouragement:** End with a forward-looking positive statement

**Example:**
> "The overall structure of this handler is clean and follows our patterns well. One thing to adjust: the database transaction should be committed only after both the order insert and inventory update succeed (see lines 34–42) — right now a failure on the inventory update leaves a dangling order. Once that's fixed, this is ready to merge. Nice work on the input validation!"

**When NOT to use the sandwich:**
- With experienced developers who prefer direct feedback
- When the compliment would be obviously forced
- In automated review contexts

---

## Handling Disagreements

### Author vs Reviewer Authority

For **non-blocking issues** (style preferences, optional improvements, alternative approaches): the author's judgment prevails. The reviewer has made their suggestion; the author chooses whether to adopt it.

For **blocking issues** (correctness, security, design): the reviewer's concern must be resolved before merge. If the author disagrees, escalate.

### Escalation Path

1. **Discuss in the PR:** Author explains reasoning, reviewer responds with evidence
2. **Time-box:** If no resolution after 2 exchanges, don't continue in the PR
3. **Third opinion:** Bring in a third reviewer or team lead
4. **Team decision:** If it represents a policy question, take it to the team for a broader decision
5. **Document:** If a new convention is established, add it to the style guide or team docs

### Anti-Patterns in Disagreements

- **Seniority as argument:** "I've been doing this for 10 years" is not evidence
- **Bikeshedding:** Spending 30 minutes debating a variable name while ignoring a design flaw
- **Endless ping-pong:** More than 3 exchanges on the same comment = time for synchronous discussion
- **Silent non-compliance:** Author resolves the comment but doesn't make the change = address directly

---

## Time-Boxing Reviews

### Session Limits

- **Maximum:** 60–90 minutes per review session
- **Optimal:** 30–60 minutes
- **After 90 minutes:** Effectiveness drops sharply. Take a break, return later.
- **If the PR requires more than 90 minutes:** It's too large. Request splitting.

### Response Time SLA

- **First response:** Within 1 business day (Google's guidance)
- **Ideal:** Within 4 hours during working hours
- **Follow-up responses:** Within same or next business day

Review delays compound: a 2-day delay per review cycle on a 3-cycle review adds 6 days of developer wait time. This causes context-switching, frustration, and throughput collapse.

### Batch vs Continuous

- **Morning review block:** Dedicate 30–60 minutes each morning to clearing the review queue
- **Do not interrupt deep work:** If in a flow state on your own code, finish the unit of work first, then review
- **Priority order:** Block by severity (security/correctness first), then by age (oldest first)

---

## Review Checklist Quick Reference

Use this as a quick scan during every review:

- [ ] PR size under 400 LOC?
- [ ] PR description explains what and why?
- [ ] CI gates all passing?
- [ ] Design: approach is sound and fits the architecture?
- [ ] Functionality: handles edge cases and error conditions?
- [ ] Complexity: understandable in one reading?
- [ ] Tests: meaningful assertions that would catch regressions?
- [ ] Naming: clear and consistent with project conventions?
- [ ] Comments: explain why, not what?
- [ ] Style: follows project style guide? (Defer to linter)
- [ ] Documentation: updated for user-facing changes?
- [ ] No obvious security issues? (Defer to security-review for thorough analysis)
