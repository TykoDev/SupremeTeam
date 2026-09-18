# Example Invocations

Five passes, each rendered in the full packet shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate (`../../../execution-contract.md`,
clause 6). The graded passes carry the shape too, not just the clean one — the
digest and the capture paths are what make a deviation attributable, and an
example that states them only when nothing was found teaches the packet as
decoration. Example 5 is a REVISE delta round rather than a fresh pass, because
the delta protocol — carried ids, re-hashed captures, the `r2 <- r1` line, the
baseline held from round one — is where a re-review most often goes wrong. Severities are the shared four tiers —
`Critical | Major | Minor | Info` — and nothing else.

## Example 1

**User request:** review the visual quality of the onboarding screens

**Output:**
- Outcome: design-qa, r2, digest `sha256:6f2a…`, 2 findings: 0 Critical, 1 Major, 1 Minor, 0 Info.
- Evidence: welcome, account setup, and first-success states captured at all six tiers in both themes — 36 captures under `review/evidence/`, each hashed into the manifest and bound to the rendered source; token usage checked against the approved `tokens.css` at digest `sha256:6f2a…`. The error states have no fixture and were not captured.
- Findings:
  - `DQ-01` | Major | first-success screen, all tiers, both themes | the heading scale and spacing rhythm drop to values used nowhere else in the flow, so the final step reads as a different product surface | restore the established typography and spacing tokens.
  - `DQ-02` | Minor | account setup, dark theme, all tiers | the helper text uses a raw hex value instead of the muted-foreground token | replace the literal with the token.
- Open risks: the validation and error states are uncaptured for want of a fixture, so a deviation there is neither found nor ruled out; a seeded error fixture would settle it.
- Next action: `review/code-chief` routes `DQ-01` to the owning build skill; the `rendered_verification` record travels with the packet.
- Revision: r2.

## Example 2

**User request:** audit the design implementation of the dashboard refresh

**Output:**
- Outcome: design-qa, r1, digest `sha256:c40d…`, 2 findings: 0 Critical, 1 Major, 0 Minor, 1 Info.
- Evidence: dashboard hero, filter controls, and empty state captured at all six tiers in both themes and hashed into the manifest; spacing and surface tokens compared against the approved `tokens.css` at digest `sha256:c40d…`. The populated data grid was excluded — it did not change in this revision.
- Findings:
  - `DQ-03` | Major | empty state, all tiers | the illustration card uses an off-palette background and breaks the vertical rhythm established on the rest of the page | move the card onto the surface token and the 8-point spacing scale.
  - `DQ-04` | Info | filter row, all tiers | the row's keyboard behavior is out of scope for a lens that judges appearance | handed to `review/frontier`, which judges interaction; no visual deviation is claimed.
- Open risks: the empty state was captured with a seeded fixture rather than a real empty account, so a real one could differ in copy length and change the rhythm again.
- Next action: `review/code-chief` routes `DQ-03` to the owning build skill and hands `DQ-04` to `review/frontier`.
- Revision: r1.

## Example 3

**User request:** check the interface polish of the settings area

**Output:**
- Outcome: design-qa, r4, digest `sha256:9ae1…`, 2 findings: 1 Critical, 0 Major, 1 Minor, 0 Info.
- Evidence: settings sidebar, destructive-action modal, and confirmation toast captured at all six tiers in both themes — `evidence/capture-375-dark.png`, `evidence/capture-1280-light.png`, and ten sibling captures, all hashed into the manifest and bound to the rendered source at digest `sha256:9ae1…`.
- Findings:
  - `DQ-05` | Critical | destructive-action modal, small mobile and mobile tiers, both themes | the CTA column collapses so the confirm and cancel actions render adjacent and mis-aligned, weakening the hierarchy at the highest-risk action in the product | apply the modal's declared stacked layout below the tablet tier.
  - `DQ-06` | Minor | confirmation toast, all tiers | corner radius is one step off the token scale | move it onto the declared radius token.
- Open risks: the modal was captured in its confirm state only; the pending and failed states share the same CTA column and were not rendered, so the same collapse may reach them.
- Next action: `review/code-chief` returns `DQ-05` to the owning build skill; the Critical blocks the gate until it is resolved.
- Revision: r4.

## Example 4 — clean pass

**User request:** validate the visual system for the profile page refresh

**Output:**
- Outcome: design-qa clean — 0 findings across 3 screens at 6 tiers in both themes, digest `sha256:1b9c…`.
- Evidence: 36 captures under `review/evidence/`, each hashed into the manifest and bound to the rendered source; token usage checked against the approved `tokens.css`.
- Findings: (none).
- Open risks: the permission-denied state has no fixture, so it was not captured and is not covered by this result.
- Next action: none from this lens. The `rendered_verification` record is attached for `review/code-chief` to carry into the gate manifest.
- Revision: r2.

## Example 5 — REVISE delta round

**User request:** (routed, not asked) `../../gates.yaml` `revise_policy.parallel_fix`
delegates the design-qa group of the `review-to-delivery` REVISE packet to this
lens; `changed_evidence` names the destructive-action modal at the small-mobile
and mobile tiers. Continues Example 3.

**Output:**
- Outcome: design-qa delta, r5 <- r4, digest `sha256:9ae1…` (unchanged — the baseline is the approved design, and a REVISE round re-checks the implementation, never the design), 2 findings carried: 1 verified, 1 unresolved.
- Evidence: only the four captures the packet named were re-taken — `evidence/capture-375-dark.png`, `evidence/capture-375-light.png`, `evidence/capture-414-dark.png`, `evidence/capture-414-light.png` — each re-hashed and the `rendered_verification` record updated to the new digests. The stale r4 hashes were replaced rather than left standing: a correct-looking capture under a prior hash fails the artifact-backing check exactly as a wrong capture would. The confirmation toast and the settings sidebar keep their r4 judgment and were not re-captured; no view's layout depends on the modal, so nothing else was pulled in.
- Findings:
  - `DQ-05` | Critical | destructive-action modal, small mobile and mobile tiers, both themes | **verified** — the declared stacked layout now applies below the tablet tier; confirm and cancel render on separate rows with the declared spacing, shown in the four re-taken captures. Same id, same severity, status `verified`.
  - `DQ-06` | Minor | confirmation toast, all tiers | **unresolved** — the corner radius is still one step off the token scale. Returns under its original id and severity, not renumbered and not downgraded because the round's Critical cleared.
- Open risks: unchanged from r4 — the modal's pending and failed states still have no fixture and were not captured, so the fix is verified only in the confirm state it was reported in.
- Next action: the Critical is cleared, so this group no longer blocks. `review/code-chief` rules on `DQ-06`; cycle 1 of a `cycle_cap` of 2 is spent, and at the cap an unresolved Minor does not convert into a blocker.
- Revision: r5 <- r4.
