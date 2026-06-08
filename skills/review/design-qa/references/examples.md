# Example Invocations

## Example 1

**User request:** review the visual quality of the onboarding screens

**Output:**
- Scope: welcome, account setup, and first-success states across mobile and desktop captures.
- Major finding: the success state drops the heading scale and spacing rhythm defined in the earlier steps, which makes the flow feel like a separate product surface.
- Fix direction: restore the established typography and spacing tokens before release.

## Example 2

**User request:** audit the design implementation of the dashboard refresh

**Output:**
- Scope: dashboard hero, filter controls, and empty state screenshots.
- Finding set: empty-state illustration and copy card violate the token palette and break the vertical rhythm established elsewhere on the page.
- Handoff: ask `review/frontier` to inspect the filter keyboard behavior separately from the visual-fidelity issues.

## Example 3

**User request:** check the interface polish of the settings area

**Output:**
- Scope: settings sidebar, destructive-action modal, and confirmation toast.
- Visual regression: the modal alignment and CTA spacing collapse on narrow screens, which weakens hierarchy at the exact point where the action is highest risk.
- Delivery: visual QA packet with the affected breakpoint, screenshot anchors, and the design-system rule being violated.
