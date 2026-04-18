# Frontend Design Patterns

## Component Archetypes

### Layout Components

| Component | Purpose | CSS Pattern |
|-----------|---------|-------------|
| **Page Shell** | Top-level layout with header, main, footer | CSS Grid with `grid-template-rows: auto 1fr auto` |
| **Container** | Max-width content wrapper | `max-width: var(--max-width); margin-inline: auto; padding-inline: var(--space-4)` |
| **Grid** | Multi-column layout | CSS Grid with `grid-template-columns: repeat(auto-fit, minmax(min, 1fr))` |
| **Stack** | Vertical stacking with consistent gaps | Flexbox column with `gap: var(--space-N)` |
| **Cluster** | Horizontal wrapping elements | Flexbox row with `flex-wrap: wrap; gap: var(--space-N)` |
| **Sidebar** | Content with fixed/flexible sidebar | CSS Grid with `grid-template-columns: minmax(0, 1fr) var(--sidebar-width)` |

### Common UI Components

| Component | Key States | Accessibility Requirements |
|-----------|-----------|--------------------------|
| **Button** | default, hover, focus, active, disabled, loading | `role="button"`, keyboard enter/space |
| **Input** | default, focus, filled, error, disabled | `label` association, `aria-describedby` for errors |
| **Card** | default, hover (if interactive), selected | If interactive: `role="article"` or button semantics |
| **Modal** | opening, open, closing, closed | Focus trap, `role="dialog"`, `aria-modal="true"` |
| **Toast** | entering, visible, exiting | `role="status"` or `role="alert"`, `aria-live` |
| **Dropdown** | closed, open, item-hover, item-selected | `role="listbox"`, keyboard arrow navigation |
| **Tab** | default, active, hover, focus | `role="tablist"`, `role="tab"`, `aria-selected` |

---

## CSS Best Practices

### Custom Property Architecture

```css
:root {
  /* Spacing scale (4px base) */
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */

  /* Typography scale */
  --text-xs: 0.75rem;   /* 12px */
  --text-sm: 0.875rem;  /* 14px */
  --text-base: 1rem;    /* 16px */
  --text-lg: 1.125rem;  /* 18px */
  --text-xl: 1.25rem;   /* 20px */
  --text-2xl: 1.5rem;   /* 24px */
  --text-3xl: 1.875rem; /* 30px */
  --text-4xl: 2.25rem;  /* 36px */

  /* Colors (semantic) */
  --color-primary: hsl(220, 90%, 56%);
  --color-surface: hsl(0, 0%, 100%);
  --color-text: hsl(220, 15%, 15%);
  --color-text-muted: hsl(220, 10%, 50%);
  --color-border: hsl(220, 10%, 88%);
  --color-error: hsl(0, 72%, 51%);
  --color-success: hsl(142, 72%, 35%);
  --color-warning: hsl(38, 92%, 50%);
}
```

### Responsive Breakpoint Pattern

```css
/* Mobile first: base styles are mobile */
.component { /* mobile styles */ }

@media (min-width: 768px) {
  .component { /* tablet overrides */ }
}

@media (min-width: 1024px) {
  .component { /* desktop overrides */ }
}
```

### Animation Best Practices

```css
/* Use compositor-friendly properties */
.animate-enter {
  transform: translateY(8px);
  opacity: 0;
  transition: transform 200ms ease, opacity 200ms ease;
}

.animate-enter.active {
  transform: translateY(0);
  opacity: 1;
}

/* Respect motion preferences */
@media (prefers-reduced-motion: reduce) {
  .animate-enter {
    transition: none;
  }
}
```

### Common Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| `!important` abuse | Specificity war | Reduce selector specificity, use custom properties |
| Pixel-based font size | Not scalable | Use `rem` units |
| Fixed widths on text containers | Breaks on different screen sizes | Use `max-width` with percentage/rem |
| Animating `width`/`height` | Triggers layout recalculation | Use `transform: scale()` |
| `z-index: 9999` | Z-index stacking chaos | Use a Z-index scale (custom properties) |
| Inline styles for theming | Not maintainable | Use CSS custom properties |
| Margin on components | Creates inconsistent spacing | Use gap on parent, not margin on children |

---

## Design Token Extraction

When no `DESIGN.md` or design token file exists, extract tokens from existing CSS:

1. **Collect all unique values** for: font-size, font-weight, line-height, color, background-color, margin, padding, gap, border-radius, box-shadow
2. **Cluster values** into scales (e.g., spacing values of 4, 8, 12, 16, 24 → 4px base scale)
3. **Identify outliers** — values that do not fit any scale are candidates for normalization
4. **Present the extracted scale** as a proposed design token system
5. **Write the tokens** to `DESIGN.md` or CSS custom properties file
