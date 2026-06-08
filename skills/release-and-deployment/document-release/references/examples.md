# Example Invocations

## Example 1

**User request:** document the release

**Output:**
- Shipped summary: new billing summary view, retry-safe invoice export, and one fixed permission bug are live in production.
- Known issue: CSV export still fails for accounts with archived line items and is owned by the payments team.
- Next move: publish the user-facing release note and a separate support brief for the export limitation.

## Example 2

**User request:** update the launch notes

**Output:**
- Rollout note: the feature is live in staging and half of production, so the launch notes explicitly call out the phased release state.
- Operator follow-up: support must watch one alert tied to the new queue processor for the first 24 hours.
- Boundary note: the documentation does not describe full global availability because that has not happened yet.

## Example 3

**User request:** write the release follow-up

**Output:**
- Post-release record: deployment succeeded, one migration ran longer than expected, and rollback was not required.
- Outstanding actions: update the admin guide, finish the customer email copy, and close the known issue once the queue fix lands.
- Owner map: each follow-up item is assigned so the release trail does not end at ship time.
