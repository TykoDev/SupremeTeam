# Example Invocations

## Example 1

**User request:** run QA without fixing on the signup flow

**Output:**
- Scope: account creation, email verification, and welcome-state transitions.
- Report-only boundary: capture the defects and repro steps, but do not edit the product surface.
- Delivery: QA report with one blocking defect, two moderate regressions, and the exact environments still untested.

## Example 2

**User request:** test and report only for the new dashboard filters

**Output:**
- Scope: filter panel, saved-filter state, and mobile drawer behavior.
- Finding set: one mobile-only blocker and one flaky desktop regression whose trigger is still being narrowed.
- Handoff: report goes straight to the implementation owner with no fixes mixed into the audit run.

## Example 3

**User request:** audit the workflow for partner onboarding

**Output:**
- Scope: invite acceptance, credential setup, and first API call.
- Evidence gap: partner sandbox credentials are missing, so the final API call remains untested and explicitly marked as such.
- Delivery: defect report that distinguishes confirmed failures from coverage gaps.
