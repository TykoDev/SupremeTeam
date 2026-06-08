# Example Invocations

## Example 1

**User request:** review the frontend for the checkout flow

**Output:**
- Scope: cart, address, payment, and confirmation states across mobile and desktop breakpoints.
- Blocking issue: keyboard focus is lost when the address modal closes, which traps screen-reader and keyboard users on mobile checkout.
- Reproduction: open the address modal on a narrow viewport, dismiss it, and observe focus move to the document root instead of the triggering control.

## Example 2

**User request:** check accessibility and performance of the dashboard

**Output:**
- Scope: dashboard landing page, filter panel, and chart-loading state.
- Major findings: chart updates announce no loading state to assistive tech, and the filter panel rerenders the full chart grid on every keystroke.
- Delivery: frontend packet with one accessibility blocker, one performance regression, and the affected components.

## Example 3

**User request:** audit the interface behavior of the notifications tray

**Output:**
- Scope: tray open/close behavior, infinite scroll, and retry state for failed loads.
- Finding set: retry keeps stale error text visible after success and the tray can reopen behind the overlay on narrow screens.
- Handoff: ask `review/design-qa` to inspect the spacing and token drift separately from the runtime behavior issues.
