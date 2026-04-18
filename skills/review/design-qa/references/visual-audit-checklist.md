# Visual Audit Checklist

## Typography Checklist

### Font Scale Validation
- [ ] All font-size values map to the design token scale
- [ ] No arbitrary pixel values outside the scale (12, 14, 16, 18, 20, 24, 30, 36, 48, 60, 72)
- [ ] Headings follow a consistent modular scale ratio (1.2× – 1.333×)
- [ ] Body text is between 14px and 18px
- [ ] Caption/small text is at least 12px

### Line Height
- [ ] Body text line-height is 1.4–1.6× font size
- [ ] Headings line-height is 1.1–1.3× font size
- [ ] Tight line-height only used intentionally (hero text, display headings)

### Font Weight
- [ ] Weights used: Regular (400), Medium (500), Semi-bold (600), Bold (700)
- [ ] No more than 3 weights across the entire UI
- [ ] Weight contrast between heading and body is at least 2 steps (e.g., 700 vs 400)

### Text Alignment
- [ ] Body text is left-aligned (LTR) or right-aligned (RTL)
- [ ] Center alignment used only for short text (headings, CTAs, captions)
- [ ] No justified text (causes uneven word spacing)

---

## Spacing Checklist

### Spacing Scale
- [ ] All spacing values use design token multiples (4px base: 4, 8, 12, 16, 24, 32, 48, 64)
- [ ] No arbitrary spacing values (13px, 17px, 23px)
- [ ] Consistent gutters within grid layouts

### Vertical Rhythm
- [ ] Section spacing > Component spacing > Element spacing
- [ ] Recommended ratio: Section 48-64px, Component 24-32px, Element 8-16px
- [ ] Consistent spacing between repeated elements (list items, cards)

### Container Padding
- [ ] Page-level containers have consistent horizontal padding
- [ ] Mobile padding: 16-24px
- [ ] Desktop padding: 24-64px
- [ ] No zero-padding on content containers

---

## Color Checklist

### Palette
- [ ] All colors map to the design token palette
- [ ] No inline hex/rgb values outside the palette
- [ ] Semantic colors are used consistently (error, success, warning, info)

### Contrast
- [ ] Normal text: 4.5:1 contrast ratio minimum
- [ ] Large text (18px+ or 14px bold): 3:1 minimum
- [ ] UI components: 3:1 against adjacent colors
- [ ] Focus indicators: 3:1 against the focused element's background

### Dark Mode (if applicable)
- [ ] All text colors have dark mode equivalents
- [ ] Background colors invert appropriately
- [ ] Borders and dividers remain visible
- [ ] No hard-coded colors that break in dark mode

---

## Interactive States Checklist

### Hover
- [ ] All clickable elements have hover feedback
- [ ] Hover transition is smooth (150-200ms ease)
- [ ] Hover does not cause layout shift
- [ ] Hover state is visually distinct from default

### Focus
- [ ] Focus ring is visible on all interactive elements
- [ ] Focus ring meets WCAG 2.2 minimum area (2px outline or equivalent)
- [ ] Focus ring color contrasts with the background (3:1)
- [ ] Custom focus styles do not remove the default outline without replacement

### Disabled
- [ ] Disabled elements have reduced opacity (0.4-0.6) or grayed appearance
- [ ] Disabled elements have `cursor: not-allowed`
- [ ] Disabled elements are not hidden — they indicate unavailability

### Loading
- [ ] Loading states use skeletons for known content layouts
- [ ] Loading states use spinners only for unknown-duration operations
- [ ] Loading indicators are appropriately sized (not too small, not too large)
- [ ] Loading text provides context ("Loading orders..." not just "Loading...")

---

## Responsive Checklist

### Mobile (320-767px)
- [ ] No horizontal scrollbar
- [ ] Text is readable without zooming
- [ ] Touch targets are at least 44×44px
- [ ] Navigation collapses to hamburger or bottom tab bar
- [ ] Images scale appropriately

### Tablet (768-1023px)
- [ ] Layout uses 2-column grid where appropriate
- [ ] Sidebar collapses or becomes collapsible
- [ ] Tables become scrollable or stack on mobile

### Desktop (1024px+)
- [ ] Content area has a max-width (1200-1440px)
- [ ] Full layout is utilized (no excessive empty space)
- [ ] Multi-column layouts are used where data density warrants

---

## AI Slop Detection Checklist

- [ ] No "Lorem ipsum" or "placeholder" text in production views
- [ ] No generic stock images with `unsplash` in the URL
- [ ] No gratuitous gradients that do not serve the design
- [ ] All interactive elements have all states implemented (not just default)
- [ ] CSS has no orphaned rules (selectors that match nothing)
- [ ] No hardcoded pixel values where design tokens should be used
- [ ] No copy-pasted identical components (should be a shared component)
- [ ] No `!important` overrides that indicate specificity problems
