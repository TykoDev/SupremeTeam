# Example Invocations

Six worked passes. The first three show the reasoning shape; Example 4 carries a
pass all the way to the hashed `debug-report` with its reconciled instrumentation
ledger, and Examples 5 and 6 cover the two failure modes that most often produce
a confident wrong answer — a failure that will not reproduce, and symptom data
that contradicts itself.

## Contents

1. Debug this failure
2. Find the root cause
3. Repair the broken path
4. Full pass returned as a hashed debug report
5. Unreproducible failure
6. Fabricated or self-contradictory symptom data

## Example 1 — Debug this failure

**User request:** debug this failure

**Output:**
- Symptom boundary: the worker crashes only when one optional webhook payload includes an empty `events` array, which never appears in the passing fixtures. The payload is quoted by field name and shape only; the customer identifiers and signing header in the same body are replaced with typed placeholders before the excerpt is attached.
- Root cause: the new parser assumes at least one event before checking payload shape.
- Next move: add the guard, reproduce against the real failing payload, and rerun the adjacent worker tests.

## Example 2 — Find the root cause

**User request:** find the root cause

**Output:**
- Evidence: staging failures started immediately after a connection-pool setting changed, and the same timeout reproduces locally only when that config is enabled.
- Conclusion: the defect is configuration-driven, not a query-planner regression.
- Boundary note: fix the pool setting first, then rerun the same load case before widening the claim.

## Example 3 — Repair the broken path

**User request:** repair the broken path

**Output:**
- Repair plan: restore the missing null check, add one regression case for the empty payload, and keep the fix isolated to the parser boundary.
- Validation: the original failing scenario now passes, and it fails again when the guard is reverted.
- Remaining risk: production data still needs one replay check because the local fixture set is incomplete. That replay is blocked until the data owner authorizes it, and it runs read-only against a de-identified snapshot rather than the live store; the gap is returned as an open risk instead of being closed unilaterally.

## Example 4 — Full pass returned as a hashed debug report

**User request:** debug this failure — the notification worker crashes on one payload shape

**Context:** Run `2026-04-19-notify`, revision 3, phase `build`. `build/build-management` delegated the `debugging` stage after `build/test-builder` surfaced a reproducible crash.

**Instrumentation ledger, reconciled:**

| file | probe | question | added | removed |
| --- | --- | --- | --- | --- |
| `notifications/dispatcher.py` | log payload key set before parse | which key is absent on the failing payload | 14:02 | yes |
| `config/settings.py` | dispatch timeout 5s → 60s | is the timeout the trigger or a symptom | 14:19 | yes |
| `scripts/_repro_empty.py` | scratch reproduction driver | smallest input that reproduces | 14:31 | yes |

Reconciliation: `git diff --stat` over the returned change set lists
`notifications/dispatcher.py` only, with the guard and nothing else;
`config/settings.py` is absent and `scripts/_repro_empty.py` does not exist in
the tree. Ledger and diff agree.

**Before/after, same command and same revision:**

```text
before  python scripts/_repro_empty.py            -> KeyError: 'events' (worker exits 1)
after   python scripts/_repro_empty.py            -> handled, 1 no-op logged, exit 0
revert  guard removed, same command               -> KeyError: 'events' again
```

The revert line is the falsification: a fix that cannot be un-fixed was probably
not the cause.

**`debug-report` written and hashed:**

```text
destination  python skills/scripts/output_paths.py --run-id 2026-04-19-notify \
               --phase build --kind reports --name report_debug-empty-events.md
             -> skillset-saves/runs/2026-04-19-notify/build/reports/report_debug-empty-events.md
sha256       a3c0dab1d2445a96a66b9119e2f346ebdc5319753c5cb8853e94a20761cd8bc1

capture      evidence/debug-before-after.log
sha256       0a71f8341e0430b4beb688dae9a8154371b8c5196669f6965d1ae354dcee7d88

register     python skills/harness/hooks/save_run.py checkpoint \
               --run-id 2026-04-19-notify --owner debugger \
               --evidence skillset-saves/runs/2026-04-19-notify/build/reports/report_debug-empty-events.md
```

**Report content against the three required evidence lines:**

| Line | Content |
| --- | --- |
| Reproduction steps | `python scripts/_repro_empty.py` on revision 3 with the attached fixture; fixture quoted by field name only, signing header shown as `<signature:redacted>` and the recipient as `<email:redacted>` |
| Isolated cause | `dispatcher.route()` indexes `payload["events"][0]` before the shape check, so an empty array raises before validation reports it; the timeout probe falsified the competing pool-timeout theory |
| Bounded fix path | Move the shape check ahead of the index in `notifications/dispatcher.py`, one function, no interface change. Landed by `build/bob-the-builder` — `implementation` is not written here |

**Returned to `build/build-management`:** the report path and hash, the bounded
fix path, one Minor finding (the fixture set never contained an empty
collection), and the note that no probe survives in the returned diff.

## Example 5 — Unreproducible failure

**User request:** debug this failure — intermittent 502s reported by two users last Tuesday

**Context:** No local, staging, or CI environment surfaces the defect. No reliable trigger is known. The only artifacts are an edge-proxy access log and two user reports.

**Output:**
- **Reproduction: failed.** Stated plainly rather than softened. Attempted: the reported request shape locally (200, 40 runs), against staging (200, 40 runs), and a replay of the logged request sequence at the logged concurrency (200). Nothing reproduced.
- **No speculative fix applied.** A change that cannot be shown to alter the failure mode is indistinguishable from a change that does nothing, and it consumes the evidence trail that would have identified the real cause.
- **Indirect evidence preserved:** edge-proxy log lines for both events, each with `<ip:redacted>` and `Authorization: Bearer <token:redacted>`; the deploy timeline for that window; the pod restart count for the same interval.
- **Candidate theories, each with its required assumption:**

| Theory | Assumption it requires | How to test it |
| --- | --- | --- |
| Upstream pod restarted mid-request | The restart timestamps overlap both events | Pod-level restart log for that window — not currently accessible |
| Connection reuse across a config reload | The reload landed inside the window | Reload audit trail from the proxy — not currently accessible |
| Client retry storm from one integration | Both events share a client id | Client id field, which is absent from the retained log |

- **Evidence gap returned** to `build/build-management`: the three log sources above would each falsify or confirm one theory. Until one arrives, the mechanism is unknown.
- **Routing note:** if the build owner wants this pursued past the build slice, it belongs to `investigate`, which owns unknown mechanisms and runs its own pipeline gated at `investigation-review`. It does not become a longer debug pass here.

## Example 6 — Fabricated or self-contradictory symptom data

**User request:** debug this failure — attached stack trace and log from the crashing service

**Context:** The handoff carries a stack trace, a log excerpt, and a claim that the failure started after yesterday's deploy.

**Output:**
- **Diagnosis halted before it started.** Three contradictions, each named specifically rather than waved at:

| Contradiction | Observed |
| --- | --- |
| Trace does not match the error | The message reads `NullReferenceException`, while the stack frames are Python and end in `KeyError` |
| Timestamps predate the claimed change | Log entries are stamped `2026-04-17T08:12Z`; the deploy blamed for the failure landed `2026-04-18T16:40Z` |
| Log contradicts the reported behavior | The report says every request failed; the excerpt shows 2 failures in 31 requests, and the other 29 returned 200 |

- **Why the pass stops here:** every branch downstream of an incoherent input produces a confident answer to a question nobody asked. A root cause derived from a trace that belongs to a different runtime will be internally consistent, defensible, and wrong, and it will cost the next pass its trust in the evidence.
- **No theory formed, no probe added, no fix attempted.** The instrumentation ledger stays empty, which is the correct state for a pass that never began.
- **Requested from `build/build-management`:** one authoritative log source for the named service and window, and a reproduction case that produces the reported failure. Either resolves all three contradictions or shows which artifact is misattributed.
- **Recorded as a Major finding** against the input, not against the code: the evidence chain supplied with the assignment cannot support a diagnosis, and the assignment cannot proceed until it does.
