# Example Invocations

Each example shows the stage path, the `investigation-review` evidence it
produces, and where the fix path goes. Investigate writes no implementation in
any of them: `../../ownership.yaml` records `implementation` among the artifacts
it never writes, so every example ends with a handoff rather than a change.

## Contents

1. Latency spike after two simultaneous changes
2. Failing worker pool with a reproducible cause
3. Two surviving suspects behind an access boundary
4. A mitigation that removes the symptom without proving the chain
5. REVISE on the evidence chain

## Example 0 — Contrast collapse traced to a token layer (DESIGN-owned)

**User request:** find the root cause (secondary buttons became unreadable in dark mode after a design-system sync)

**Output:**
- `scope`: the secondary button's foreground/background pair in dark mode across the six responsive tiers, from the token sync commit onward; component-level overrides elsewhere in the surface are excluded, and the owning phase is DESIGN.
- `reproduction`: the dark-theme render of the button catalog at the two tiers where it fails, captured through `design-qa` and written to the destination `output_paths.py --kind evidence --name reproduction-contrast.json` resolves, hashed into `artifact_hashes`, with the measured ratio (2.9:1) recorded beside the required floor.
- `evidence_chain`: four observed links — the computed pair in the rendered capture, the resolved value of `--color-fg-muted` in the built stylesheet, the sync commit's diff against the upstream token set, and the upstream release note narrowing that token's lightness range in dark mode.
- `mechanism`: the sync adopted an upstream lightness change for one semantic token without re-deriving the pairs that consume it, so a pair that was compliant before the sync no longer clears AA. Confidence: high.
- `fix_path` and `residual_uncertainty`: re-derive the muted-foreground pair against the dark surface token and re-verify the ratio at both failing tiers — owned by DESIGN (`architect` holds the token system, `design-qa` re-captures), not by BUILD, since nothing in the application code is implicated. Whether other pairs consuming the same token sit close to the floor is not covered; a full pair sweep would settle it.

## Example 1 — Latency spike after two simultaneous changes

**User request:** investigate this issue (checkout latency spiked after a deploy)

**Output:**
- `scope`: checkout request latency above the p95 budget from the deploy timestamp onward, on the checkout service only; the payment provider integration is excluded, and the owning phase is BUILD.
- `reproduction`: the cache-key change replayed against a staging copy of the production traffic sample, executed rather than described, written to the destination `output_paths.py --kind evidence --name reproduction.log` resolves and hashed into `artifact_hashes`.
- `evidence_chain`: six observed links from the latency histogram to the duplicate database fan-out, each naming its source, timestamp, and capture. The gateway timeout change is carried as a labelled inference and excluded from the link count, because nothing observed connects it to the fan-out.
- `mechanism`: the cache-key format mismatch, which displaced the timeout hypothesis — timeouts alone do not explain duplicate fan-out on a warm cache. Confidence: high.
- `fix_path` and `residual_uncertainty`: restore the previous cache-key format for the affected namespace, owned by BUILD, with the fan-out count returning to baseline as the acceptance signal; the conclusion does not cover whether the timeout change independently affects the retry path, which a separate load run would show.
- Return: the manifest passes the self-check, is submitted at `investigation-review`, and admiral routes the approved package back to BUILD, which schedules the change through its own pipeline and gates it at `build-to-review`. Investigate edits nothing.

## Example 2 — Failing worker pool with a reproducible cause

**User request:** find the root cause of the background jobs that stopped draining

**Output:**
- `scope`: the new worker pool only; the scheduler and the queue broker are excluded after both were observed healthy. Owning phase: BUILD.
- `reproduction`: the variable removed in staging, the pool restarted, and the failure observed — that executed log is the artifact, hashed into the manifest. A described reproduction would not have satisfied the key.
- `evidence_chain`: production error logs, the last deployment diff, and the failing job trace, each link observed and hashed as one trace file.
- `mechanism`: a missing environment variable in the new pool's configuration; the failure appears when it is removed and disappears when restored, so the alternative of a broker permission change is displaced. Confidence: high.
- `fix_path` and `residual_uncertainty`: add the variable to the pool's configuration template, owned by BUILD, with the queue draining to zero as the acceptance signal; the conclusion does not cover why the template diverged, which the configuration history would show.
- Return: admiral routes the package back to BUILD. Investigate does not restore the variable itself, because the change belongs to the phase that owns the code and needs that phase's gate.

## Example 3 — Two surviving suspects behind an access boundary

**User request:** explain why this broke (intermittent TLS handshake failures)

**Output:**
- `scope`: outbound calls to one managed service, in one region, during a four-hour window; other regions observed unaffected. Owning phase: BUILD, with a REVIEW dependency on the certificate policy.
- `reproduction`: the handshake failure reproduced against the managed endpoint with the recorded client configuration, hashed as the artifact. The key accepts no fallback, so this had to be executed before anything else was claimed.
- `evidence_chain`: four observed links; the fifth would require the provider's audit log, which is inaccessible. That link is labelled as a boundary rather than inferred, so it is not counted.
- `mechanism`: two suspects survive — certificate rotation timing and DNS cache staleness — and the package says so rather than choosing the more familiar one. Confidence: bounded.
- `fix_path`: no cure is named, because two suspects survive and a fix aimed at one would leave the other in place. What is owned is the step that separates them: BUILD requests the provider's audit log for the window through the account owner, and in the meantime pins the client's certificate-refresh interval and DNS TTL to explicit values so the next occurrence implicates one suspect rather than both. Acceptance signal: either the audit log resolves the window, or one recurrence under the pinned configuration eliminates a suspect. `../../gates.yaml` lists no fallback at this boundary, so an unresolved mechanism still owes this key — it names the owner and the next step, not a repair.
- `residual_uncertainty`: the provider audit log is the observation that separates the suspects; without it neither can be confirmed, and the conclusion is scoped to what was observed.
- Verdict: `ESCALATE`. The missing evidence source, the access boundary, its owner, and the observation that would close the gap go back through admiral as the escalation packet.

## Example 4 — A mitigation that removes the symptom without proving the chain

**User request:** trace the failure (a memory ceiling that stopped recurring after a config change)

**Output:**
- `reproduction`: the pre-change condition reproduced under the original configuration and hashed, so the symptom is anchored to an executed run rather than to a memory of one.
- `evidence_chain`: the allocation growth is observed; the link from growth to the ceiling is observed; the link from the config change to the absence of growth is *not* — the change was applied before the growth was instrumented. That gap stays visible in the chain instead of being smoothed over.
- `mechanism`: unresolved. A symptom that disappeared is not a mechanism that was proven, and the package says which link is missing.
- `fix_path`: the config change is reported as a provisional mitigation, owned by BUILD, with instrumented allocation growth across one full traffic cycle as the acceptance signal that would promote it from mitigation to fix.
- `residual_uncertainty`: root-cause confidence is not claimed; the observation that would change the conclusion is a heap profile captured under the original configuration.

## Example 5 — REVISE on the evidence chain

**User request:** (continuation) the gate returned REVISE naming `evidence_chain`

**Output:**
- Packet contents: one mechanical failure — the chain artifact's hash no longer matches the manifest after the trace was extended — and one judgment finding, that two links are labelled observations but cite the same capture.
- Resolution in one pass: all six keys have the same owner, so there is no fan-out. The trace is re-captured, the second link is relabelled as inference and removed from the link count, the artifact is re-hashed, and the manifest is updated.
- Resubmission: once, with `--prior <verdict.json>`, so `changed_evidence` names `evidence_chain` and the gatekeeper carries its prior judgment on the five unchanged keys.
- Cap: `revise_policy.cycle_cap` is 2. If the second cycle also returns `REVISE`, the packet escalates with both verdicts rather than being resubmitted a third time.
