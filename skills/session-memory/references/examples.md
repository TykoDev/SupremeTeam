# Example Invocations

Five worked runs covering the four request kinds in `workflow.md`, plus the
degraded-write branch. Each shows the deliverable this skill actually produces:
the `save_run.py` call, the result read back from it, and the record or report
that call published. Learning entries use the tagged form `../SKILL.md` mandates;
the layer and failure-category vocabularies come from `../../harness-doctrine.md`
§1–§2 and are two separate axes: the layer names where the fix is enforceable,
the category names the failure that routes it there. They are never the same
string — a block whose two tags read alike has collapsed one axis into the other.

## Contents

1. Checkpoint before a delegation
2. Checkpoint plus a tagged learning
3. Resume with drift
4. Lookup against prior learnings
5. Degraded write

## Example 1 — checkpoint before a delegation

**User request:** save progress

**Command:**

```bash
python skills/harness/hooks/save_run.py checkpoint --run-id 2026-04-23_dashboard-redesign_a3f9k2 --expect-revision 6 --evidence skillset-saves/runs/2026-04-23_dashboard-redesign_a3f9k2/review/reports/review-packet.md --next-action "regenerate the adversarial review packet for revision 7, then resubmit at review-to-delivery"
```

**Result:** `result: ok`, revision 7 published, pointer rewritten.

**Output:**
- Revision: 7 (parent 6). Active boundary: `review-to-delivery`, status GATE pending.
- Registered evidence: `review/reports/review-packet.md` — `sha256:4f1c…a209`.
- Approved lineage carried forward: `design/artifacts/tokens.css` rev 3, `build/packages/app.zip` rev 5.
- Open blocker: adversarial findings for revision 7 are missing, so the gate cannot be judged.
- Next action: regenerate the review packet for revision 7, then resubmit at the same boundary.

## Example 2 — checkpoint plus a tagged learning

**User request:** checkpoint this run and record what we learned

**Command:** `save_run.py checkpoint --run-id 2026-04-19_workflow-engine_b8d3 --owner session-memory --expect-revision 11 --evidence build/reports/report_learnings.md` against the destination `output_paths.py --run-id 2026-04-19_workflow-engine_b8d3 --phase build --kind reports --name report_learnings.md` resolved.

**Result:** `result: ok`, revision 12 published.

**Output:**
- Run state: build pipeline paused after test failures confined to the staging-only integration suite.
- Learning recorded in `build/reports/report_learnings.md`, bound to revision 12 by evidence hash:

```markdown
- **Learning**: staging fixtures drift between runs, so a failing staging-only integration suite is a fixture gap until the seed step is re-run
  - layer: Environment Contract (`../../harness-doctrine.md` §1, layer 1)
  - failure-category: Environment-contract mismatch (§2, category 2)
  - evidence: `tests/integration/conftest.py` line 42 — seed step skipped when `CI_STAGING` is unset
  - confidence: high
```

- Reuse trigger: any skill about to treat a staging-only suite failure as an application regression queries this learning first.
- Next action: rerun seed setup, then retest before triaging the failures as defects.

## Example 3 — resume with drift

**User request:** resume from saved state

**Command:** `save_run.py status --run-id 2026-04-23_dashboard-redesign_a3f9k2` (read-only; no revision published).

**Result:** `result: ok`, classification `active`, lock held and pinned, revision 7.

**Output:**
- Restored and verified: `design/artifacts/tokens.css` rev 3 and `build/packages/app.zip` rev 5, both matching their registered digests.
- Drift: `review/reports/review-packet.md` is registered at revision 7 but absent on disk, so the boundary it backs cannot be re-judged from evidence.
- Resume path narrowed to the last fully verified checkpoint, revision 6, with the review boundary reopened.
- Recommendation: regenerate the missing packet before the downstream stage advances; nothing was rewritten, because the record is the evidence of what broke.

## Example 4 — lookup against prior learnings

**User request:** what did we learn about auth token handling

**Command:** read-only grep across the run's learning reports; no `save_run.py` write is issued.

**Output:**
- One match, from `build/reports/report_learnings.md`, returned verbatim:

```markdown
- **Learning**: auth token refresh must be triggered before any downstream API call in the pipeline; skipping it causes silent 401s that the retry logic misidentifies as network errors
  - layer: Environment Contract (`../../harness-doctrine.md` §1, layer 1)
  - failure-category: Environment-contract mismatch (§2, category 2)
  - evidence: `src/api/client.ts` line 84 — token expiry not checked before request dispatch
  - confidence: high
```

- Reuse trigger: any skill that performs authenticated API calls queries this before issuing requests.
- No second match. The token-rotation question the caller also asked has no recorded learning, and is reported as unanswered rather than inferred from the entry above.

## Example 5 — degraded write

**User request:** save where we are

**Command:** `save_run.py checkpoint --run-id 2026-05-02_invoice-import_77c1b4 --expect-revision 2 --evidence design/reports/report_plan.md`

**Result:** `result: degraded` (exit 2) — the publish failed and revision 2 is intact.

**Output:**
- Persistence reported as **degraded**, not active. Revision 2 remains the latest published state; nothing was partially written.
- Warned once, and no retry by direct file write: the six `core-run-record` paths are written only through `save_run.py`.
- Continuity held inline for the remainder of the turn, with the same four checkpoint fields the write would have carried, so the orchestrator can re-attempt the save once the cause is cleared.
- Next action: resolve the save-root failure, then reissue the checkpoint against revision 2; treat the run as unresumable across sessions until a write returns `ok`.
