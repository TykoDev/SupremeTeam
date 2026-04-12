# Accessibility Checklist — WCAG 2.2 Level AA Review Guide

## How to Use This Checklist

Apply each criterion to the frontend code under review. Mark each item as:
- **PASS** — Implementation correctly satisfies the criterion
- **FAIL** — Implementation violates the criterion (finding required)
- **N/A** — Criterion is not applicable to this codebase
- **PARTIAL** — Some instances pass, others fail (finding required for failures)

---

## Principle 1: Perceivable

### 1.1 Text Alternatives

- [ ] **1.1.1 Non-text Content (A):** All `<img>` elements have `alt` attributes. Informational images have descriptive alt text. Decorative images use `alt=""` or `role="presentation"`
- [ ] **Custom icons** use `aria-label` or visually hidden text for screen readers
- [ ] **SVG graphics** include `<title>` and/or `aria-label` for accessibility
- [ ] **Canvas elements** have fallback text content

### 1.2 Time-Based Media

- [ ] **1.2.1 Audio-only/Video-only (A):** Pre-recorded media has text alternatives or audio descriptions
- [ ] **1.2.2 Captions (A):** Pre-recorded video has synchronized captions
- [ ] **1.2.5 Audio Description (AA):** Pre-recorded video has audio descriptions for visual content

### 1.3 Adaptable

- [ ] **1.3.1 Info and Relationships (A):** Semantic HTML conveys structure (headings, lists, tables, landmarks)
- [ ] **Heading hierarchy** is logical and sequential (no skipped levels: `h1` → `h2` → `h3`)
- [ ] **Form groups** use `<fieldset>` and `<legend>` for related controls
- [ ] **Data tables** use `<th>` elements with `scope` attributes
- [ ] **1.3.2 Meaningful Sequence (A):** DOM order matches visual order
- [ ] **1.3.3 Sensory Characteristics (A):** Instructions don't rely solely on shape, size, position, or sound

### 1.4 Distinguishable

- [ ] **1.4.1 Use of Color (A):** Color is not the only means of conveying information (status, errors, required fields)
- [ ] **1.4.3 Contrast (Minimum) (AA):** Text has at least 4.5:1 contrast ratio (3:1 for large text ≥18pt or ≥14pt bold)
- [ ] **1.4.4 Resize Text (AA):** Text can be resized to 200% without loss of content or function
- [ ] **1.4.5 Images of Text (AA):** Text is rendered as text (not as images), except for logos
- [ ] **1.4.10 Reflow (AA):** Content reflows at 320px width without horizontal scrolling
- [ ] **1.4.11 Non-text Contrast (AA):** UI components and graphic elements have at least 3:1 contrast
- [ ] **1.4.12 Text Spacing (AA):** No loss of content when text spacing is increased (line height 1.5, letter spacing 0.12em, word spacing 0.16em, paragraph spacing 2x)
- [ ] **1.4.13 Content on Hover or Focus (AA):** Tooltips/popovers are dismissible, hoverable, and persistent

---

## Principle 2: Operable

### 2.1 Keyboard Accessible

- [ ] **2.1.1 Keyboard (A):** All functionality is operable via keyboard
- [ ] **Interactive elements** use native HTML (`<button>`, `<a>`, `<input>`) or have `tabindex="0"` and keyboard event handlers
- [ ] **Custom widgets** implement expected keyboard patterns (arrow keys, Enter, Escape, Space)
- [ ] **2.1.2 No Keyboard Trap (A):** User can Tab into and out of all components (including modals, dropdowns, date pickers)
- [ ] **Modal dialogs** trap focus within the modal and return focus on close

### 2.4 Navigable

- [ ] **2.4.1 Bypass Blocks (A):** Skip navigation link present (skip to main content)
- [ ] **2.4.2 Page Titled (A):** Each page has a descriptive `<title>` element
- [ ] **2.4.3 Focus Order (A):** Focus order follows a logical sequence matching visual layout
- [ ] **2.4.6 Headings and Labels (AA):** Headings and labels are descriptive
- [ ] **2.4.7 Focus Visible (AA):** Keyboard focus indicator is clearly visible on all interactive elements
- [ ] **Custom focus styles** are visible and have sufficient contrast (not just browser default)
- [ ] **2.4.11 Focus Not Obscured (Minimum) (AA) — WCAG 2.2:** Focused element is not entirely hidden by sticky headers, footers, or overlays
- [ ] **2.4.13 Focus Appearance (AA) — WCAG 2.2:** Focus indicator has minimum 2px solid outline or equivalent area

### 2.5 Input Modalities

- [ ] **2.5.1 Pointer Gestures (A):** Multi-point or path-based gestures have single-pointer alternatives
- [ ] **2.5.2 Pointer Cancellation (A):** Up-event used for activation (not down-event), allowing cancellation
- [ ] **2.5.7 Dragging Movements (AA) — WCAG 2.2:** Drag-and-drop has alternative input (buttons, menus)
- [ ] **2.5.8 Target Size (Minimum) (AA) — WCAG 2.2:** Interactive targets are at least 24×24px (except inline links in text)

---

## Principle 3: Understandable

### 3.1 Readable

- [ ] **3.1.1 Language of Page (A):** `<html>` element has `lang` attribute set to correct language
- [ ] **3.1.2 Language of Parts (AA):** Content in different languages has `lang` attribute on containing element

### 3.2 Predictable

- [ ] **3.2.1 On Focus (A):** Receiving focus does not cause unexpected context change
- [ ] **3.2.2 On Input (A):** Changing input does not cause unexpected context change (unless user is advised)
- [ ] **3.2.3 Consistent Navigation (AA):** Navigation patterns are consistent across pages
- [ ] **3.2.4 Consistent Identification (AA):** Components with same function are identified consistently

### 3.3 Input Assistance

- [ ] **3.3.1 Error Identification (A):** Form errors are clearly described in text
- [ ] **Error messages** are associated with their fields via `aria-describedby` or `aria-errormessage`
- [ ] **3.3.2 Labels or Instructions (A):** All form inputs have visible labels
- [ ] **Labels** are programmatically associated: `<label for="id">` or `aria-labelledby`
- [ ] **3.3.3 Error Suggestion (AA):** When errors are detected, suggestions for correction are provided
- [ ] **3.3.4 Error Prevention (AA):** For legal/financial/data-deletion actions: confirmation, review, or reversibility
- [ ] **3.3.7 Redundant Entry (A) — WCAG 2.2:** Previously entered info auto-populates in multi-step forms
- [ ] **3.3.8 Accessible Authentication (Minimum) (AA) — WCAG 2.2:** Authentication does not require cognitive function tests (CAPTCHAs have alternatives)

---

## Principle 4: Robust

### 4.1 Compatible

- [ ] **4.1.2 Name, Role, Value (A):** Custom UI components expose correct name, role, and state to assistive technology
- [ ] **ARIA roles** match component behavior (e.g., `role="dialog"` for modals, `role="tablist"` for tabs)
- [ ] **ARIA states** are dynamically updated (`aria-expanded`, `aria-selected`, `aria-checked`, `aria-hidden`)
- [ ] **4.1.3 Status Messages (AA):** Dynamic content changes are announced via `aria-live` regions
- [ ] **Toast notifications** use `role="alert"` or `aria-live="assertive"`
- [ ] **Loading states** are announced: `aria-busy="true"` on loading containers
- [ ] **Dynamic content** updates use `aria-live="polite"` for non-urgent updates

---

## ARIA Usage Correctness

### Common ARIA Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| `<div role="button">` without keyboard support | Use native `<button>` or add `tabindex="0"`, `keydown` handler |
| `aria-label` on non-interactive element | Use on interactive elements or landmarks only |
| `role="presentation"` on element with children | Children inherit presentation — verify intent |
| Redundant ARIA on semantic HTML | `<button role="button">` — remove redundant role |
| `aria-hidden="true"` on focusable element | Remove from focus order first or use `inert` attribute |

---

## Testing Methodology

### Layer 1: Automated Scanning

Run axe-core or Pa11y against all pages/routes. Expected automated detection rate: ~30-40% of all WCAG issues.

```bash
# axe-core via CLI
npx @axe-core/cli http://localhost:3000

# Pa11y
npx pa11y http://localhost:3000 --standard WCAG2AA
```

### Layer 2: Keyboard Testing

1. Unplug mouse / disable trackpad
2. Navigate entire application using only Tab, Shift+Tab, Enter, Space, Escape, Arrow keys
3. Verify all interactive elements can be reached and activated
4. Verify focus is never trapped or lost

### Layer 3: Screen Reader Testing

1. Test with NVDA (Windows) or VoiceOver (macOS)
2. Navigate by headings, landmarks, and links
3. Verify form labels are announced correctly
4. Verify dynamic content changes are announced
5. Verify error messages are associated with fields

### Layer 4: Visual Inspection

1. Check color contrast (browser DevTools or contrast checker)
2. Zoom to 200% and verify no content is lost
3. Check text spacing override (CSS override test)
4. Verify focus indicators are visible
