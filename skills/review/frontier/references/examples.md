# Example Invocations

Five passes, each rendered in the full packet shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate (`../../../execution-contract.md`,
clause 6). The graded passes carry the shape too, not just the clean one — every
claim this lens makes rests on an observed run, so the Evidence line that names
the runs is load-bearing on a pass with findings exactly as it is on one without.
Severities are the shared four tiers — `Critical | Major | Minor | Info` — and
nothing else. Example 5 is a REVISE delta round rather than a fresh review,
because the rule that decides whether a re-review is worth anything here —
re-measure, never re-reason — only becomes visible on a round that verifies a
previous finding.

## Example 1

**User request:** review the frontend for the checkout flow

**Output:**
- Outcome: frontier, r2, 2 findings: 1 Critical, 0 Major, 1 Minor, 0 Info.
- Evidence: cart, address, payment, and confirmation states exercised on the preview deployment at `r2`, at the mobile and desktop tiers, with pointer and keyboard input; full keyboard traversal of every interactive control in each state; console watched across all four. The saved-card path was not reached — it needs a seeded account this pass did not have.
- Findings:
  - `FR-01` | Critical | address modal, mobile tier, keyboard | focus moves to the document root when the modal closes, stranding keyboard and screen-reader users mid-checkout | reproduction: open the address modal at 375 px, dismiss it, observe `document.activeElement` | likely cause: the trigger reference is dropped on unmount.
  - `FR-02` | Minor | confirmation state, all tiers, screen reader | the status region updates without an `aria-live` announcement, so the outcome is silent to assistive technology after a successful submit | reproduction: submit with NVDA active and observe that nothing is announced | likely cause: the region is rendered after the announcement hook runs.
- Open risks: no screen-reader pass was run on the address modal itself, so `FR-01`'s impact on assistive technology is inferred from the focus position rather than observed; an NVDA run over that modal would settle it.
- Next action: `review/code-chief` returns `FR-01` to the owning build skill; the Critical blocks the gate until it is resolved.
- Revision: r2.

## Example 2

**User request:** check accessibility and performance of the dashboard

**Output:**
- Outcome: frontier, r3, 2 findings: 0 Critical, 2 Major, 0 Minor, 0 Info.
- Evidence: dashboard landing page, filter panel, and chart-loading state exercised on the preview deployment at `r3` across all six tiers with pointer and keyboard input; a Lighthouse run and an interaction trace captured and hashed into the manifest, with the baseline captured before any recommendation was written; trace at `evidence/trace-filter-keystroke.json`.
- Findings:
  - `FR-03` | Major | chart region, all tiers, screen reader | updates announce no loading state to assistive technology, so the panel reads as static while data is in flight | reproduction: apply a filter with NVDA active and observe that nothing is announced until the chart settles | likely cause: the region has no `aria-busy` and no live announcement.
  - `FR-04` | Major | filter panel, desktop tier, keyboard | every keystroke rerenders the full chart grid; interaction latency measured at 480 ms against a 200 ms budget | reproduction: type six characters into the filter with the trace recorder running, see `evidence/trace-filter-keystroke.json` | likely cause: the filter value is lifted to a parent that owns the grid.
- Open risks: the measurement was taken against the seeded 200-row dataset; production accounts run an order of magnitude larger, so 480 ms is a floor rather than the worst case.
- Next action: `review/code-chief` routes both Majors to the owning build skill before the gate.
- Revision: r3.

## Example 3

**User request:** audit responsive behavior of the notifications tray

**Output:**
- Outcome: frontier, r1, 3 findings: 0 Critical, 2 Major, 0 Minor, 1 Info.
- Evidence: tray open/close behavior, infinite scroll, and the retry state for failed loads exercised on the preview deployment at `r1` across all six tiers, with pointer and keyboard input; each tier resized and reflow observed; the failure path driven by a stubbed error response rather than a real outage.
- Findings:
  - `FR-05` | Major | retry state, all tiers, pointer | stale error text stays visible after a successful retry, so the tray reports a failure that has already resolved | reproduction: force a load failure, retry successfully, observe the error text persists | likely cause: the error is cleared on request start but not on success.
  - `FR-06` | Major | tray, small mobile and mobile tiers, pointer and keyboard | the tray reopens behind the overlay, leaving it unreachable by either input mode until the page is reloaded | reproduction: open the tray at 375 px, dismiss it, reopen it, attempt to focus any item | likely cause: the overlay's stacking context is re-created on the second mount.
  - `FR-07` | Info | tray header, all tiers | spacing and token drift observed in the header | handed to `review/design-qa`; no runtime impact is claimed here.
- Open risks: infinite scroll was exercised to three pages against a stubbed feed; the real feed paginates differently past that point and was not reachable from this environment.
- Next action: `review/code-chief` routes `FR-05` and `FR-06` to the owning build skill and hands `FR-07` to `review/design-qa`.
- Revision: r1.

## Example 4 — clean pass

**User request:** the UI feels janky on the settings page — check it

**Output:**
- Outcome: frontier clean — 0 findings across 4 flows at 6 tiers, pointer, keyboard, and screen-reader input.
- Evidence: each tier resized and reflow observed; full keyboard traversal of every interactive control with focus visible throughout; NVDA pass over the form region; interaction latency measured at 84 ms against a 200 ms budget; no console errors across the four flows.
- Findings: (none).
- Open risks: the reported jank was not reproduced on any exercised device profile, so a device-specific cause outside this matrix stays possible; touch input on a physical low-end handset was not available to this pass.
- Next action: none from this lens.
- Revision: r3.

## Example 5 — REVISE delta round

**User request:** (routed, not asked) `review/code-chief` sub-delegates the
frontier portion of its `review-to-delivery` REVISE group; `changed_evidence`
names the filter panel and the chart region. Continues Example 2.

**Output:**
- Outcome: frontier delta, r4 <- r3, 2 findings carried: 1 verified, 1 unresolved.
- Evidence: only the two named surfaces were re-exercised, plus the chart-loading state, whose behavior depends on the filter. **Re-measured, not re-read**: a fresh interaction trace at `evidence/trace-filter-keystroke-r4.json` and a fresh NVDA pass, both taken at the same tier and input mode as the r3 observations — desktop tier, keyboard input, the same seeded 200-row dataset — because a fix to a runtime claim is verified by a new run under the original conditions, and a diff that plainly shows the state was moved is still not a measurement. The dashboard landing page keeps its r3 judgment and was not re-exercised. Both new captures are hashed into the manifest; the r3 trace stays as lineage rather than being overwritten.
- Findings:
  - `FR-04` | Major | filter panel, desktop tier, keyboard | **verified** — the filter value was moved out of the grid's parent; the new trace measures interaction latency at 96 ms against the same 200 ms budget, on the same dataset as the 480 ms baseline. Same id, same severity, status `verified`.
  - `FR-03` | Major | chart region, all tiers, screen reader | **unresolved** — `aria-busy` is now set on the region, but the NVDA re-run still announces nothing when a filter is applied, because no live region carries the transition. A partial fix that does not change what the assistive technology announces is not a fix of this finding; it returns under its original id and severity, not downgraded.
- Open risks: unchanged from r3 — 96 ms is measured on the seeded dataset and remains a floor for production-scale accounts, so the verified fix is verified at that scale and no further.
- Next action: `FR-03` still blocks from this lens; `review/code-chief` returns it to its fix owner with the re-run evidence attached. Cycle 1 of a `cycle_cap` of 2 is spent, and at the cap an unresolved Major returns unchanged with its blocking status intact.
- Revision: r4 <- r3.
