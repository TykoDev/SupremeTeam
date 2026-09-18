# Example Invocations

Five passes — four fresh and one REVISE delta — each rendered in the full packet
shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate (`../../../execution-contract.md`,
clause 6). The graded passes carry the shape too, not just the clean one — a pass
with findings is where the fields do the most work, and an example that drops
them there teaches the packet as decoration. Severities are the shared four tiers
— `Critical | Major | Minor | Info` — and nothing else.

## Example 1

**User request:** find the bugs in the order retry handler

**Output:**
- Outcome: bug-review, r4, 2 findings: 1 Critical, 0 Major, 0 Minor, 1 Info.
- Evidence: `orders/retry_handler.ts` traced end to end with the two call sites that drive it, and the persistence path that records completion followed from the emit to the marker write; the existing retry suite read for the interleaving it does not cover. The vendored queue client was excluded as third-party.
- Findings:
  - `BUG-01` | Critical | `orders/retry_handler.ts:142` | the handler writes the retry marker after emitting the success event, so a timeout between the two double-submits the same order | record the marker inside the same transaction as the emit.
  - `BUG-02` | Info | `orders/retry_handler.ts:142` | the same duplicate event may also open a replay exposure, which is a security judgment this lens does not make | handed to `review/security-review`; no correctness claim is attached to it here.
- Open risks: the queue's at-least-once redelivery guarantee is read from the client's documentation rather than observed, so the width of the collision window is reasoned about and not measured. One recorded redelivery would settle it.
- Next action: `review/code-chief` routes `BUG-01` to the change owner before the gate.
- Revision: r4.

## Example 2

**User request:** review correctness of the cache invalidation change

**Output:**
- Outcome: bug-review, r2, 2 findings: 0 Critical, 1 Major, 1 Minor, 0 Info.
- Evidence: the invalidation logic for product details and the read path that serves stale collections, traced across `catalog/cache.py` and the two readers the handoff names; the write-path tests read for the list-cache case they omit. The CDN layer was excluded as outside the supplied surface.
- Findings:
  - `BUG-03` | Major | `catalog/cache.py:88` | the write path invalidates the detail key but leaves the list cache untouched, so a reader sees a stale collection after a successful write | invalidate both layers, or move the read model onto a versioned cache key.
  - `BUG-04` | Minor | `catalog/cache.py:131` | the invalidation helper swallows a miss without logging, so the next report of this class starts with no trace to follow | log the miss with the key that was not found.
- Open risks: whether a reader outside `catalog/` also holds the list cache is unsettled — the handoff names two, and nothing in the supplied surface enumerates the rest. A third consumer would widen `BUG-03` rather than change it.
- Next action: `review/code-chief` routes `BUG-03` to the change owner; `BUG-04` rides in the same fix.
- Revision: r2.

## Example 3

**User request:** check failure paths in the import worker

**Output:**
- Outcome: bug-review, r1, 1 finding: 1 Critical, 0 Major, 0 Minor, 0 Info.
- Evidence: the CSV import worker, its retry queue, and the dead-letter branch, traced from `import/worker.py:180` through the compensating path to the completion transition; the parse-failure fixture read against the branch it drives. The queue's redelivery configuration was not supplied and so was not read.
- Findings:
  - `BUG-05` | Critical | `import/worker.py:203` | a parse failure marks the job complete without recording the dead-letter payload, dropping the evidence recovery depends on | write the dead-letter record before the completion transition, inside the same compensating branch.
- Open risks: the queue's redelivery window is absent from the supplied config, so the blast radius of a repeated failure stays unverified. The queue configuration, or one observed redelivery, would settle it.
- Next action: `review/code-chief` requests the queue configuration, then routes `BUG-05` to the change owner.
- Revision: r1.

## Example 4 — clean pass

**User request:** find the bugs in the currency-rounding patch

**Output:**
- Outcome: bug-review clean — 0 findings across `billing/rounding.py` and its three callers.
- Evidence: every branch of `round_half_even` walked against the added property tests; the two callers that pass unrounded totals traced to their sources; the vendored decimal shim excluded as third-party.
- Findings: (none).
- Open risks: no fixture covers a negative total, so behavior below zero is untested rather than proven correct.
- Next action: none from this lens.
- Revision: r3.

## Example 5 — a REVISE delta pass

The round after Example 1. `review/code-chief` sub-delegates the part of the
`review-to-delivery` REVISE group this lens owns; `changed_evidence` names
`orders/retry_handler.ts` and `orders/tests/test_retry.ts`.

**User request:** re-review the retry handler against the REVISE packet

**Output:**
- Outcome: bug-review delta, r5 <- r4, 1 finding carried, 1 verified, 1 new out-of-delta.
- Evidence: only the two paths in `changed_evidence`, plus `orders/persistence.ts` because `BUG-01`'s correctness depends on the transaction boundary it owns. Everything else keeps its r4 judgment and was not re-read.
- Findings:
  - `BUG-01` | Critical | `orders/retry_handler.ts:142` | **verified** — the marker write now sits inside the emit's transaction, and the added interleaving test fails against the r4 code and passes against r5. Same id, same severity, status `verified`.
  - `BUG-02` | Info | unchanged and still with `review/security-review`; nothing in `changed_evidence` touches it, so it is carried forward rather than re-judged.
  - `BUG-06` | Major | `orders/persistence.ts:88` | **out-of-delta** — the new transaction wrapper swallows a rollback error, so a failed marker write reports success. Found while reading a path `BUG-01` depends on, but outside `changed_evidence`: reported as out-of-delta rather than folded into the round. `review/code-chief` decides whether it enters this cycle or the next.
- Open risks: unchanged from r4 — the redelivery guarantee is still read rather than observed.
- Next action: `review/code-chief` rules on `BUG-06`'s cycle. Cycle 1 of a `cycle_cap` of 2 is now spent.
- Revision: r5 <- r4.
