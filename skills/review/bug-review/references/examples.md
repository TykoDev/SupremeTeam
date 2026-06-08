# Example Invocations

## Example 1

**User request:** find the bugs in the order retry handler

**Output:**
- Scope: retry logic in `orders/retry_handler.ts` plus the persistence path that records completion.
- Major finding: the handler writes the retry marker after emitting the success event, so a timeout can double-submit the same order.
- Handoff: ask `review/security-review` to confirm whether the duplicate event also creates a replay exposure.

## Example 2

**User request:** review correctness of the cache invalidation change

**Output:**
- Scope: invalidation logic for product details and the read path that serves stale cache entries.
- Finding set: stale reads remain possible because the write path invalidates one key but leaves the list cache untouched.
- Fix direction: invalidate both cache layers or move the read model to a versioned cache key.

## Example 3

**User request:** check failure paths in the import worker

**Output:**
- Scope: CSV import worker, retry queue, and dead-letter behavior.
- Blocking defect: a parse failure marks the job complete without recording the dead-letter payload, which drops the evidence needed for recovery.
- Delivery: correctness packet with the trigger, observed impact, and the exact branch that needs a compensating write.
