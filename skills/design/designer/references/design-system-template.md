# Design System Specification Template

> **Purpose**: Template for specifying a project's design system. The designer
> skill uses this template structure when producing the design system section
> of its deliverable. This defines how components, tokens, and patterns are
> documented.

---

## 1. Component Specification Format

### Component Definition Template

```markdown
## Component: [ComponentName]

### Classification
- **Level**: Atom | Molecule | Organism | Template | Page
- **Category**: UI primitive | Form | Navigation | Data display | Feedback | Layout

### Description
[What this component does and when to use it]

### Props / API
| Prop | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| variant | 'primary' \| 'secondary' \| 'ghost' | 'primary' | No | Visual style |
| size | 'sm' \| 'md' \| 'lg' | 'md' | No | Size variant |
| disabled | boolean | false | No | Disabled state |
| children | ReactNode | — | Yes | Content |

### States (10-State Model)
| State | Visual Description | Trigger |
|-------|-------------------|---------|
| Default | Standard appearance | Initial render |
| Hover | Subtle bg change, cursor pointer | Mouse over |
| Active | Slightly darker / inset | Mouse down / touch |
| Focus | 2px ring, high contrast | `:focus-visible` |
| Disabled | Reduced opacity, `not-allowed` cursor | disabled=true |
| Loading | Spinner, preserved dimensions | Async operation |
| Error | Red border/ring + message | Validation failure |
| Success | Brief green indicator | Operation complete |
| Empty | Placeholder + CTA | No data |
| Selected | Highlighted border / checkmark | User selection |

### Accessibility Contract
- **Role**: [ARIA role if not semantic default]
- **Keyboard**: [Key interactions — Enter, Space, Escape, Tab, Arrows]
- **Screen reader**: [Announcement behavior]
- **Focus management**: [Focus trap, focus restore, skip links]
- **Target size**: Minimum 44×44px interactive area

### Composition Patterns
- **Slots/Children approach**: Prefer composition over configuration
- **Compound components**: Component.Header, Component.Body, Component.Footer
- **Render props / slots**: For customizable sections

### Usage Guidelines
**Do**: [Correct usage patterns]
**Don't**: [Anti-patterns to avoid]
```

---

## 2. Three-Tier Design Token Architecture

Design tokens follow the W3C Design Tokens Community Group format direction.
All values are defined as CSS custom properties organized in three tiers:

### Tier 1: Primitive Tokens (Raw Values)

These are the absolute values. Never referenced directly by components.

```css
@layer tokens {
  :root {
    /* =========================== */
    /* COLORS — OKLCH Color Space  */
    /* =========================== */

    /* Brand scale */
    --brand-50:  oklch(0.97 0.02 250);
    --brand-100: oklch(0.93 0.04 250);
    --brand-200: oklch(0.86 0.08 250);
    --brand-300: oklch(0.75 0.12 250);
    --brand-400: oklch(0.65 0.16 250);
    --brand-500: oklch(0.55 0.20 250);  /* Primary */
    --brand-600: oklch(0.48 0.18 250);
    --brand-700: oklch(0.40 0.16 250);
    --brand-800: oklch(0.32 0.12 250);
    --brand-900: oklch(0.25 0.08 250);
    --brand-950: oklch(0.18 0.05 250);

    /* Neutral scale */
    --gray-50:  oklch(0.98 0.003 250);
    --gray-100: oklch(0.93 0.005 250);
    --gray-200: oklch(0.87 0.008 250);
    --gray-300: oklch(0.78 0.010 250);
    --gray-400: oklch(0.66 0.012 250);
    --gray-500: oklch(0.55 0.014 250);
    --gray-600: oklch(0.44 0.012 250);
    --gray-700: oklch(0.37 0.010 250);
    --gray-800: oklch(0.27 0.008 250);
    --gray-900: oklch(0.21 0.006 250);
    --gray-950: oklch(0.14 0.004 250);

    /* Feedback colors */
    --red-500:    oklch(0.55 0.20 25);
    --green-500:  oklch(0.55 0.16 145);
    --yellow-500: oklch(0.75 0.16 85);
    --blue-500:   oklch(0.55 0.18 250);

    /* =========================== */
    /* SPACING — 8-Point Grid      */
    /* =========================== */
    --space-0:  0;
    --space-px: 1px;
    --space-0.5: 0.125rem;  /* 2px */
    --space-1:   0.25rem;   /* 4px */
    --space-2:   0.5rem;    /* 8px */
    --space-3:   0.75rem;   /* 12px */
    --space-4:   1rem;      /* 16px */
    --space-5:   1.25rem;   /* 20px */
    --space-6:   1.5rem;    /* 24px */
    --space-8:   2rem;      /* 32px */
    --space-10:  2.5rem;    /* 40px */
    --space-12:  3rem;      /* 48px */
    --space-16:  4rem;      /* 64px */
    --space-20:  5rem;      /* 80px */
    --space-24:  6rem;      /* 96px */

    /* =========================== */
    /* TYPOGRAPHY                   */
    /* =========================== */

    /* Font families (replace with project-specific choices) */
    --font-display: 'Clash Display', sans-serif;
    --font-sans:    'Satoshi', system-ui, sans-serif;
    --font-mono:    'JetBrains Mono', ui-monospace, monospace;

    /* Type scale (Perfect Fourth — 1.333 ratio) */
    --text-xs:      0.75rem;    /* 12px */
    --text-sm:      0.875rem;   /* 14px */
    --text-base:    1rem;       /* 16px */
    --text-lg:      1.125rem;   /* 18px */
    --text-xl:      1.25rem;    /* 20px */
    --text-2xl:     1.5rem;     /* 24px */
    --text-3xl:     1.875rem;   /* 30px */
    --text-4xl:     2.25rem;    /* 36px */
    --text-5xl:     3rem;       /* 48px */
    --text-display: clamp(2.5rem, 1rem + 4vw, 4.5rem);

    /* Line heights */
    --leading-none:    1;
    --leading-tight:   1.15;
    --leading-snug:    1.3;
    --leading-normal:  1.5;
    --leading-relaxed: 1.625;

    /* Font weights */
    --font-normal:   400;
    --font-medium:   500;
    --font-semibold: 600;
    --font-bold:     700;

    /* =========================== */
    /* BORDERS & RADIUS            */
    /* =========================== */
    --radius-sm:   0.25rem;   /* 4px */
    --radius-md:   0.375rem;  /* 6px */
    --radius-lg:   0.5rem;    /* 8px */
    --radius-xl:   0.75rem;   /* 12px */
    --radius-2xl:  1rem;      /* 16px */
    --radius-full: 9999px;

    /* =========================== */
    /* SHADOWS & ELEVATION         */
    /* =========================== */
    --shadow-xs:  0 1px 2px oklch(0 0 0 / 0.05);
    --shadow-sm:  0 1px 3px oklch(0 0 0 / 0.1);
    --shadow-md:  0 4px 6px -1px oklch(0 0 0 / 0.1);
    --shadow-lg:  0 10px 15px -3px oklch(0 0 0 / 0.1);
    --shadow-xl:  0 20px 25px -5px oklch(0 0 0 / 0.1);

    /* =========================== */
    /* MOTION & ANIMATION          */
    /* =========================== */
    --duration-instant:  0ms;
    --duration-fast:     100ms;
    --duration-normal:   200ms;
    --duration-moderate: 300ms;
    --duration-slow:     500ms;

    --ease-default:    cubic-bezier(0.4, 0, 0.2, 1);
    --ease-in:         cubic-bezier(0.4, 0, 1, 1);
    --ease-out:        cubic-bezier(0, 0, 0.2, 1);
    --ease-spring:     cubic-bezier(0.34, 1.56, 0.64, 1);
    --ease-decelerate: cubic-bezier(0, 0, 0.2, 1);

    /* =========================== */
    /* Z-INDEX SCALE               */
    /* =========================== */
    --z-base:     0;
    --z-above:    10;
    --z-dropdown: 100;
    --z-sticky:   200;
    --z-overlay:  300;
    --z-modal:    400;
    --z-popover:  500;
    --z-toast:    600;
    --z-tooltip:  700;
  }
}
```

### Tier 2: Semantic Tokens (Contextual Meaning)

```css
@layer tokens {
  :root {
    /* Surface & text */
    --background:          var(--gray-50);
    --foreground:          var(--gray-900);
    --card:                var(--gray-50);
    --card-foreground:     var(--gray-900);
    --popover:             var(--gray-50);
    --popover-foreground:  var(--gray-900);

    /* Brand */
    --primary:             var(--brand-600);
    --primary-foreground:  white;
    --primary-hover:       var(--brand-700);

    /* Secondary */
    --secondary:           var(--gray-100);
    --secondary-foreground: var(--gray-900);

    /* Muted */
    --muted:               var(--gray-100);
    --muted-foreground:    var(--gray-500);

    /* Feedback */
    --destructive:         var(--red-500);
    --success:             var(--green-500);
    --warning:             var(--yellow-500);
    --info:                var(--blue-500);

    /* Borders */
    --border:              var(--gray-200);
    --input:               var(--gray-200);
    --ring:                var(--brand-500);

    /* Layout */
    --radius:              var(--radius-md);
  }

  .dark {
    --background:          var(--gray-950);
    --foreground:          var(--gray-100);
    --card:                var(--gray-900);
    --card-foreground:     var(--gray-100);
    --border:              var(--gray-800);
    --muted:               var(--gray-800);
    --muted-foreground:    var(--gray-400);
    --primary:             var(--brand-400);
    --primary-hover:       var(--brand-300);
  }
}
```

### Tier 3: Component Tokens (Scoped to Components)

```css
@layer tokens {
  :root {
    /* Button */
    --button-bg:      var(--primary);
    --button-text:    var(--primary-foreground);
    --button-radius:  var(--radius);
    --button-height:  2.5rem;

    /* Input */
    --input-bg:       var(--background);
    --input-border:   var(--border);
    --input-radius:   var(--radius);
    --input-height:   2.5rem;

    /* Card */
    --card-bg:        var(--card);
    --card-border:    var(--border);
    --card-radius:    var(--radius-lg);
    --card-shadow:    var(--shadow-sm);
    --card-padding:   var(--space-6);
  }
}
```

---

## 3. Token Naming Convention

```
{category}-{property}-{variant}-{state}-{scale}

Examples:
  --color-primary-hover
  --color-text-secondary
  --spacing-section-horizontal
  --radius-card
  --shadow-elevation-2
  --font-size-display
  --duration-transition-fast
  --z-index-modal
```

---

## 4. Responsive Breakpoints

| Name | Min Width | Target Devices |
|------|----------|----------------|
| `sm` | 640px | Large phones (landscape) |
| `md` | 768px | Tablets |
| `lg` | 1024px | Small laptops |
| `xl` | 1280px | Desktops |
| `2xl` | 1536px | Large desktops |

---

## 5. Accessibility Compliance Checklist (WCAG 2.2 Level AA)

### Perceivable
- [ ] All images have descriptive alt text (1.1.1)
- [ ] Video has captions and audio descriptions (1.2.x)
- [ ] Content is structured with semantic HTML (1.3.1)
- [ ] Color is not the only means of conveying information (1.4.1)
- [ ] Text contrast ratio meets 4.5:1 (normal) / 3:1 (large) (1.4.3)
- [ ] Text can be resized to 200% without loss of content (1.4.4)

### Operable
- [ ] All functionality is keyboard accessible (2.1.1)
- [ ] No keyboard traps (2.1.2)
- [ ] Skip navigation link provided (2.4.1)
- [ ] Pages have descriptive titles (2.4.2)
- [ ] Focus order is logical (2.4.3)
- [ ] Link purpose is clear from text (2.4.4)
- [ ] Focus indicator is visible and not obscured (2.4.7 + 2.4.11/12)
- [ ] Touch/pointer targets are at least 24×24px (2.5.8)
- [ ] Drag operations have alternatives (2.5.7)

### Understandable
- [ ] Page language is declared (3.1.1)
- [ ] Form inputs have visible labels (3.3.2)
- [ ] Error messages are descriptive and suggest corrections (3.3.3)
- [ ] Consistent help is available (3.3.5)
- [ ] Redundant entry is minimized (3.3.7)
- [ ] Accessible authentication — no cognitive function tests (3.3.8)

### Robust
- [ ] HTML validates (4.1.1)
- [ ] ARIA roles, states, and properties are correct (4.1.2)
- [ ] Status messages are announced without focus change (4.1.3)

---

## 6. Anti-Patterns Reference

### Visual Anti-Patterns

| Anti-Pattern | Correct Approach |
|-------------|-----------------|
| Emoji as icons | SVG icon library (Lucide, Heroicons) |
| Low-contrast text | Min 4.5:1 contrast ratio |
| Auto-playing carousels | Static hero or scrollable cards |
| Magic numbers in CSS | Design tokens for all values |
| Inconsistent spacing | 8-point grid, token-only spacing |
| Static-only design | Both light and dark themes |
| Placeholder as label | Always visible `<label>` elements |

### Code Anti-Patterns

| Anti-Pattern | Correct Approach |
|-------------|-----------------|
| Monolithic components (500+ lines) | Compose from single-responsibility parts |
| Props explosion (>10 props) | Compound component pattern |
| Inline styles everywhere | Utility classes or CSS modules |
| Missing loading/error states | Design all 10 component states |
| Overriding library styles | Extend through tokens and CVA variants |
| No error boundaries | Error boundary per feature section |
