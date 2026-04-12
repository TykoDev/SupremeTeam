# UI/UX Standards Reference

> **Purpose**: Authoritative reference for the designer skill's UX quality
> decisions. Covers usability heuristics, information architecture, interaction
> design, form design, navigation, content design, feedback patterns, data
> display, user flows, and error handling. The designer SKILL.md instructs the
> agent to validate its deliverable against this file.

---

## 1. Nielsen's 10 Usability Heuristics — Design Validation Checklist

Every design decision must be validated against these heuristics. Use as a
final checklist before declaring the frontend specification complete.

| # | Heuristic | Validation Question | Implementation Standard |
|---|-----------|--------------------|-----------------------|
| 1 | **Visibility of System Status** | Does every async operation show feedback? | Loading indicators on all fetches. Success within 100ms for clicks, 1s for forms. Error at point of failure. Progress for multi-step. |
| 2 | **Match Real World** | Does the UI use the user's language? | Plain language ("Save changes" not "Persist state"). Familiar icons (magnifying glass = search). Logical ordering. |
| 3 | **User Control & Freedom** | Can users undo, escape, and navigate back? | Undo for non-destructive actions. Confirmation for destructive. Cancel at every step. Draft auto-save. Close on every overlay. |
| 4 | **Consistency & Standards** | Same color/icon/term for same purpose everywhere? | Red = destructive, green = success. Consistent icon style. Same component behavior. 8-point grid throughout. |
| 5 | **Error Prevention** | Does the design prevent errors before they happen? | Constrained inputs (dropdowns over free-text). Input masks. Smart defaults. Inline validation on blur. Confirm before delete. |
| 6 | **Recognition Over Recall** | Is information visible rather than memorized? | Recent items in menus. Visual previews for selections. Validation requirements visible. Keyboard shortcuts in tooltips. Autofill attributes. |
| 7 | **Flexibility & Efficiency** | Can experts work faster? | Keyboard shortcuts (Ctrl+S, Ctrl+Z). Command palette (Cmd+K). Bulk operations. Advanced filters. Customizable density. |
| 8 | **Aesthetic & Minimalist Design** | Does every element earn its place? | Progressive disclosure. Clear visual hierarchy. Generous whitespace. Single purpose per page. Minimal form fields. |
| 9 | **Error Recovery** | Are error messages specific and actionable? | "Password must be 8+ characters" not "Invalid". Tell user how to fix. Preserve input on error. Associate error with field via `aria-describedby`. |
| 10 | **Help & Documentation** | Is contextual help available? | Inline tooltips. Searchable docs. Contextual hints on first encounter. |

---

## 2. Information Architecture

### 2.1 Visual Hierarchy Levels

Every page must establish clear hierarchy through size, color, contrast,
position, and spacing:

| Level | Visual Treatment | Purpose | Examples |
|-------|-----------------|---------|----------|
| **Level 1: Primary** | Largest, highest contrast, boldest | Page title, hero, primary CTA | `display/h1, bold, full foreground` |
| **Level 2: Secondary** | Medium-large, high contrast | Section headings, key data, nav | `h2, semibold, foreground` |
| **Level 3: Tertiary** | Medium, medium contrast | Subsection headings, card titles | `h3/h4, medium, foreground/80%` |
| **Level 4: Body** | Standard size, standard contrast | Body text, descriptions | `body, regular, foreground/70%` |
| **Level 5: Supplementary** | Small, lower contrast | Captions, timestamps, metadata | `body-sm/caption, muted-foreground` |

### 2.2 Navigation Architecture by Application Type

| Application Type | Primary Nav | Secondary Nav | Tertiary Nav |
|-----------------|------------|--------------|-------------|
| **Marketing Website** | Top navbar (Logo + 5–7 links + CTA) | Footer navigation | Breadcrumbs |
| **SaaS Dashboard** | Sidebar (collapsible) | Top tabs | In-page anchors |
| **E-commerce** | Top navbar + search | Category sidebar | Breadcrumbs + filters |
| **Documentation** | Sidebar (tree structure) | In-page TOC | Prev/Next links |
| **Social / Consumer** | Bottom tab bar (mobile) | Top tabs | Swipeable segments |
| **Admin Panel** | Sidebar with icons + labels | Top tabs + breadcrumbs | Context menus |

### 2.3 Content Organization Patterns

| Pattern | When to Use |
|---------|------------|
| **Alphabetical** | Lists with known names (contacts, countries) |
| **Chronological** | Time-based content (messages, events, articles) — most recent first |
| **Numerical** | Ordered data (rankings, scores, prices) |
| **Categorical** | Grouped by type or topic (products, docs) |
| **Task-based** | Action-oriented (settings, workflows) |
| **Priority-based** | Importance-driven (notifications, recommendations) |

---

## 3. Interaction Design Patterns

### 3.1 Touch/Click Target Standards

| Element | Minimum Size | Recommended | WCAG Reference |
|---------|-------------|-------------|----------------|
| **Primary buttons** | 44×44px | 48×48px | 2.5.8 (AA) |
| **Icon buttons** | 44×44px | 44×44px | Include padding around icon |
| **Inline links** | Full line height | Full text height | Entire height clickable |
| **Form inputs** | 44px height | 48px height | Includes label area |
| **Checkboxes/Radio** | 44×44px | 44×44px | Target extends beyond visual checkbox |
| **Toggle switches** | 44×44px | 48×24px | Full width is target |
| **Navigation items** | 44×44px | 48px height | Full row height |

### 3.2 Interactive State Design

Every interactive element must have these distinct visual states:

| State | Visual Treatment | Notes |
|-------|-----------------|-------|
| **Default** | Standard colors, no special indicators | Resting state |
| **Hover** | Subtle bg change or shadow increase | Pointer devices only |
| **Focus** | 2px ring, high contrast, 2px offset | `:focus-visible` only — required for a11y |
| **Active/Pressed** | Slightly darker or inset | Mouse down / touch |
| **Disabled** | Reduced opacity, `cursor: not-allowed` | No hover effects. Add tooltip explaining why |
| **Loading** | Spinner or skeleton, prevents interaction | Replace label text, preserve dimensions |
| **Error** | Red border/ring + error message below | Icon + descriptive text |
| **Success** | Brief green indicator → return to default | Temporary state (1–2s) |
| **Empty** | Placeholder message + action | Illustration + "No items yet" + CTA |
| **Selected/Active** | Highlighted border, checkmark, or bg | Distinguishable from focus |

### 3.3 Confirmation & Destructive Action Standards

| Severity | Examples | Confirmation | Undo? |
|----------|---------|-------------|-------|
| **Low** | Archive, close tab | No | Yes (toast with undo) |
| **Medium** | Remove from list, hide | Inline confirm | Yes |
| **High** | Delete item, cancel subscription | Explicit dialog | No (or short window) |
| **Critical** | Delete account, erase all data | Dialog + re-type confirmation | No |

**Dialog standards for destructive actions:**
- Clearly state what will happen and what is being affected
- Destructive button: red background, specific label ("Delete project" not "OK")
- Position destructive button away from cancel to prevent accidental clicks
- Cancel = safe option, should be visually prominent (outline/secondary style)

### 3.4 Keyboard Navigation Patterns

| Component | Keys | Behavior |
|-----------|------|----------|
| **Button** | `Enter`/`Space` | Activate |
| **Dialog/Modal** | `Escape` close, `Tab` trapped | Focus → dialog on open, return on close |
| **Dropdown Menu** | `Arrow ↑/↓` navigate, `Enter` select, `Esc` close | Wrap around items |
| **Tab Panel** | `Arrow ←/→` switch tabs | Arrow keys, not Tab |
| **Accordion** | `Enter`/`Space` expand/collapse | Toggle panel |
| **Combobox** | `Arrow ↓` open, `Esc` close, `Enter` select | Filter as user types |

---

## 4. Form Design Standards

### 4.1 Layout Rules

- **Single-column layout** by default — multi-column only for closely
  related short fields (first/last name, city/state)
- **Top-aligned labels** — above input, left-aligned (largest click target,
  always visible on narrow viewports)
- **Logical grouping** — related fields in fieldsets with clear legend/heading
- **Minimal fields** — each additional field reduces conversion by ~5–10%

### 4.2 Validation Strategy (Progressive)

| Phase | Trigger | Behavior |
|-------|---------|----------|
| **1. On focus** | Field receives focus | Show label and placeholder. No validation yet. |
| **2. On first blur** | User leaves field for first time | Validate. Show errors if invalid. |
| **3. On subsequent input** | After first blur, on each keystroke | Real-time validation (debounced). Update error state. |
| **4. On submit** | Form submission | Validate all. Focus first error field. Scroll into view. |

### 4.3 Error Message Standards

- **Be specific**: "Password must be at least 8 characters" not "Invalid input"
- **Be actionable**: Tell users how to fix the problem
- **Be human**: "We couldn't save your changes" not "ERR_NETWORK_FAILED"
- **Use visual indicators**: Error icon + red text + underline
- **Associate with element**: `aria-describedby` linking to error message
- **Preserve input**: NEVER clear form fields on validation error

### 4.4 Accessible Form Markup Pattern

```html
<form novalidate>
  <div class="form-field">
    <label for="email">Email address</label>
    <input
      id="email" type="email" name="email" required
      aria-required="true"
      aria-describedby="email-help email-error"
      aria-invalid="false"
      autocomplete="email"
    />
    <span id="email-help" class="text-muted">We'll never share your email.</span>
    <span id="email-error" class="text-error" role="alert">
      Please enter a valid email address.
    </span>
  </div>
</form>
```

---

## 5. Navigation Design

### 5.1 Navigation Hierarchy

- **Primary**: Top-level, every page. 5–7 items max. Most-used first. Desktop:
  horizontal bar. Mobile: hamburger or bottom tabs.
- **Secondary**: Within a section. Tabs, sidebar, or breadcrumbs.
- **Tertiary**: Contextual within a page. Pagination, filters, anchors.

### 5.2 Mobile Navigation Patterns

| Pattern | Best For | Pros | Cons |
|---------|---------|------|------|
| **Hamburger Menu** | Many nav items | Saves space, familiar | Hidden = less discoverable |
| **Bottom Tab Bar** | 3–5 core destinations | Always visible, thumb-reachable | Limited items |
| **Full-Screen Overlay** | Complex hierarchies | Rich content space | Breaks context |
| **Collapsible Sections** | Content-heavy sites | Progressive disclosure | Tedious for deep trees |

**Default recommendation**: Bottom tab bar (3–5 items) + hamburger for overflow.

### 5.3 Breadcrumb Markup

```html
<nav aria-label="Breadcrumb">
  <ol>
    <li><a href="/">Home</a></li>
    <li><a href="/products">Products</a></li>
    <li aria-current="page">Current Page</li>
  </ol>
</nav>
```

---

## 6. Feedback & Communication Patterns

### 6.1 Toast/Notification System

| Type | Duration | Dismissible? | Icon | Color |
|------|----------|-------------|------|-------|
| **Success** | 5s auto | Yes | Checkmark | Green |
| **Error** | Persistent | Yes | X-circle | Red |
| **Warning** | 8s auto | Yes | Alert-triangle | Amber |
| **Info** | 5s auto | Yes | Info-circle | Blue |

**Positioning**: Bottom-right on desktop, bottom-center on mobile. Stack
vertically, newest at bottom. Max 3 visible.

### 6.2 Modal/Dialog Standards

- **Open**: Only on explicit user action (never auto-open)
- **Focus**: Move to first interactive element inside
- **Trap**: Tab cycles within modal, does not leave
- **Close**: X button + Escape key + backdrop click
- **Return**: Focus returns to trigger element on close
- **Scroll**: Lock background scrolling while open
- **Size**: Max 90vw/85vh desktop. Full-screen or bottom-sheet on mobile
- **Content**: Single task or message per modal

### 6.3 Skeleton Loading Standards

Skeletons must match final content layout to prevent layout shift:

- **Text**: Height of 1em, random width variations (70%, 90%, 100%)
- **Images**: Actual image aspect ratio
- **Cards**: Include shapes for all elements (avatar, title, description)
- **Animation**: Shimmer pulse, 1.5s ease-in-out infinite

### 6.4 Empty State Design

Empty states are critical onboarding opportunities:

**Structure**: Illustration + Heading + Description + Primary CTA

- Explain what this section is for
- Show a preview of what it looks like with data
- Provide prominent action to add the first item
- Be visually appealing, not just blank + text

---

## 7. Data Display Standards

### 7.1 Table Design

- **Header**: Sticky row, clear labels, sortable indicators
- **Rows**: Optional alternating background, hover state
- **Alignment**: Left-align text, right-align numbers, center booleans
- **Responsive**: Mobile → card layout or horizontal scroll with sticky first
  column
- **Empty**: "No data available" + [Add Data] button
- **Loading**: Skeleton rows matching structure
- **Actions**: Row actions in kebab menu (⋮), not always visible
- **Pagination**: Items per page + page numbers + total count + prev/next

### 7.2 Number & Date Formatting

- **Large numbers**: Locale-appropriate ("1,234" US, "1.234" EU).
  Abbreviate very large ("1.2K", "3.5M")
- **Currency**: Always symbol + appropriate decimals ("$1,234.56")
- **Dates**: Relative for recent ("2 hours ago"), absolute for older
  ("Jan 15, 2025"). Include timezone for cross-timezone apps
- **Percentages**: Number + "%". Show direction ("+12%" green, "−3%" red)
- **File sizes**: Appropriate units with ≤1 decimal ("2.5 MB")

---

## 8. User Flow Patterns

### 8.1 Authentication Flows

**Sign-Up** (optimized for conversion):
1. Email input (single field, no password yet)
2. Check for existing account → prompt sign-in if found
3. Password creation with real-time strength indicator
4. Optional profile setup (name, avatar) — skippable
5. Welcome screen with primary action

**Sign-In** (minimized friction):
1. Email + password on one screen (not split)
2. "Forgot password?" visible but not prominent
3. Social sign-in options (Google, GitHub)
4. Redirect to last page or dashboard after sign-in

### 8.2 Search Flow

1. **Query**: Show recent searches and popular suggestions
2. **Autocomplete**: After 2+ chars with 300ms debounce, highlighted matches
3. **Results**: Scannable list with title, snippet, metadata
4. **No results**: Helpful suggestions + popular content
5. **Back**: Preserve query so user can return to results

### 8.3 Multi-Step Form Standards

- Always show progress indicator (step counter or bar)
- Allow navigation between completed steps
- Save data at each step (not just at the end)
- Show review/summary step before final submission
- Allow save-as-draft and return later
- Validate inline, not at top

---

## 9. Cross-Platform Responsive Behavior Matrix

| Element | Mobile (<768px) | Tablet (768–1024px) | Desktop (>1024px) |
|---------|-----------------|--------------------|--------------------|
| **Navigation** | Bottom tabs or hamburger | Top navbar or sidebar | Navbar + sidebar |
| **Tables** | Card layout or stacked | Scroll + sticky first col | Full table |
| **Modals** | Bottom sheet (full width) | Centered, max 90vw | Centered, max 600px |
| **Forms** | Single column, full width | 2-column for short fields | 2–3 columns |
| **Card grids** | 1 column | 2 columns | 3–4 columns |
| **Hero** | Stacked: text then image | Side-by-side or stacked | Side-by-side, generous spacing |
| **Sidebar** | Hidden (drawer) | Collapsible overlay | Fixed visible |

---

## 10. Anti-Patterns to Avoid

### Visual Anti-Patterns

| Anti-Pattern | Do This Instead |
|-------------|----------------|
| Emoji as icons | SVG icon libraries (Lucide, Heroicons) |
| Low-contrast text | Minimum 4.5:1 contrast ratio |
| Auto-playing carousels | Static hero or scrollable cards |
| Infinite scroll without escape | Pagination with "Load More" |
| Placeholder text as labels | Always `<label>` elements |
| Fixed-width layouts | Fluid widths + max-width + responsive grids |
| Disabled buttons with no explanation | Disabled + tooltip explaining what's needed |

### Code Anti-Patterns

| Anti-Pattern | Do This Instead |
|-------------|----------------|
| Magic numbers in CSS | Design tokens for all values |
| Overriding component library styles | Use props/variants or extend through tokens |
| Inline styles everywhere | Utility classes or CSS modules |
| Giant monolithic components | Compose from small, single-responsibility components |
| No loading states | Always design skeleton/spinner states |
| Missing error boundaries | Error boundaries per feature section |
