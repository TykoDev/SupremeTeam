# Visual Design Guide

> **Purpose**: Authoritative reference for the designer skill's visual design
> decisions. Covers typography, color, spacing, theming, animation, and visual
> identity. The designer SKILL.md instructs the agent to consult this file when
> defining the project's Visual Design Language.

---

## 1. Design Philosophy: Bold, Intentional, Unforgettable

Every interface must commit to a **clear aesthetic direction** and execute it
with precision. Generic AI-generated aesthetics — overused font families (Inter,
Roboto, Arial), clichéd color schemes (purple gradients on white), and
predictable layouts — are explicitly prohibited. The goal is interfaces that
feel *genuinely designed* for their specific context.

### Aesthetic Direction Framework

Before selecting any visual token, the designer must choose an aesthetic
direction that aligns with the project's purpose and audience:

| Direction | Characteristics | When to Use |
|-----------|----------------|-------------|
| **Brutally Minimal** | Maximum whitespace, single accent color, strict grid, hidden complexity | Luxury brands, premium SaaS, developer tools |
| **Maximalist / Dense** | Controlled density, layered elements, rich interaction, information-forward | Financial platforms, analytics dashboards, power-user tools |
| **Retro-Futuristic** | Neon accents, dark backgrounds, monospace type, CRT/scan-line effects | AI/ML products, gaming, creative tools |
| **Organic / Natural** | Warm palettes, rounded shapes, soft gradients, nature-inspired textures | Health, wellness, sustainability, education |
| **Luxury / Refined** | Serif display fonts, muted palettes, generous spacing, subtle motion | Fashion, architecture, premium services |
| **Playful / Toy-like** | Bright saturated colors, rounded corners, bouncy animations, large type | Consumer apps, children's products, social platforms |
| **Editorial / Magazine** | Strong typographic hierarchy, mixed media, editorial grid, dramatic scale contrast | Content platforms, blogs, portfolios, media sites |
| **Brutalist / Raw** | System fonts at extreme sizes, visible grid, harsh contrasts, no decoration | Art, activism, experimental personal sites |
| **Industrial / Utilitarian** | Monospace type, minimal color, dense layouts, functional aesthetics | Dev tools, terminal interfaces, internal tools |

**CRITICAL**: No two projects should converge on the same visual choices. Vary
themes, fonts, color palettes, and compositional approaches across projects.
The aesthetic direction must be documented in the deliverable and every
subsequent visual decision must trace back to it.

---

## 2. Typography

### 2.1 Font Selection Strategy

Typography is the single most impactful visual design decision. Choose fonts
that are **distinctive, characterful, and context-appropriate** — not safe
defaults.

**Selection Criteria:**

| Criterion | Requirement |
|-----------|------------|
| **Font count** | Maximum 2 families: 1 display/heading + 1 body (or 1 variable font for both) |
| **Weight count** | 2–3 weights per family (Regular 400, Medium 500, Bold 700) |
| **Format** | Variable fonts (`.woff2`) preferred — single file, continuous weight/width axes |
| **Loading** | `font-display: swap` to prevent invisible text during load |
| **Fallback** | Always provide a complete system fallback stack |
| **License** | Verify commercial license (Google Fonts = free for commercial use) |

**Recommended Font Pairings (2025-2026):**

| Aesthetic | Display / Heading | Body | Avoid |
|-----------|------------------|------|-------|
| **Modern/Professional** | Space Grotesk, Outfit | IBM Plex Sans, Source Sans 3 | Inter (overused) |
| **Geometric/Clean** | Plus Jakarta Sans, Sora | DM Sans, Figtree | Poppins (generic) |
| **Friendly/Warm** | Nunito, Quicksand | Manrope, Albert Sans | Open Sans (dated) |
| **Elegant/Editorial** | Fraunces, Playfair Display | Lora, Source Serif 4 | Georgia (default) |
| **Technical/Code** | JetBrains Mono, Fira Code | IBM Plex Mono | Courier (ugly) |
| **Bold/Experimental** | Clash Display, Cabinet Grotesk | Satoshi, General Sans | Montserrat (overused) |

> **Anti-pattern**: Never default to Inter, Roboto, Arial, or system fonts.
> These produce interfaces indistinguishable from every other AI-generated UI.
> Seek distinctiveness.

### 2.2 Type Scale (Modular Ratio)

Use the **perfect fourth ratio (1.333)** as the base modular ratio. All font
sizes derive from this ratio to create natural visual harmony:

| Token | Size | Weight | Line Height | Use Case |
|-------|------|--------|-------------|----------|
| `display` | 3rem+ (48px+) | Bold 700 | 1.0–1.1 | Hero headings, marketing |
| `h1` | 2.25rem (36px) | Bold 700 | 1.1–1.2 | Page titles |
| `h2` | 1.875rem (30px) | Semibold 600 | 1.2–1.3 | Section headings |
| `h3` | 1.5rem (24px) | Semibold 600 | 1.3 | Subsection headings |
| `h4` | 1.25rem (20px) | Medium 500 | 1.4 | Card titles, labels |
| `body` | 1rem (16px) | Regular 400 | 1.5–1.6 | Body text |
| `body-sm` | 0.875rem (14px) | Regular 400 | 1.5 | Secondary text, captions |
| `caption` | 0.75rem (12px) | Medium 500 | 1.4 | Labels, timestamps, badges |

### 2.3 Fluid Typography

Use CSS `clamp()` for smooth scaling across viewport sizes instead of
breakpoint-based jumps:

```css
h1 { font-size: clamp(1.75rem, 1rem + 3vw, 3rem); }     /* 28px → 48px */
h2 { font-size: clamp(1.5rem, 1rem + 2vw, 2.25rem); }    /* 24px → 36px */
h3 { font-size: clamp(1.25rem, 0.5rem + 1.5vw, 1.75rem); } /* 20px → 28px */

.section { padding: clamp(2rem, 5vw, 6rem); }
```

### 2.4 Readability Rules

- **Max line width**: 65–75 characters (`max-width: 65ch`)
- **Paragraph spacing**: 1.5× the font size between paragraphs
- **Line height**: 1.5 for body, 1.1–1.3 for headings
- **Alignment**: Left-aligned for body text (never justify on the web)
- **Wrapping**: `text-wrap: balance` for headings, `text-wrap: pretty` for paragraphs

---

## 3. Color System

### 3.1 OKLCH Color Space (2025-2026 Standard)

Use **OKLCH** (Lightness, Chroma, Hue) for all color work. OKLCH provides
perceptually uniform color manipulation — changing lightness by a fixed amount
produces consistent perceived brightness regardless of hue. This makes
programmatic color generation (dark mode, hover states, accessibility checks)
reliable.

### 3.2 Three-Tier Token Architecture

Colors must follow a strict three-tier hierarchy:

**Tier 1 — Primitive Colors** (raw values, never referenced directly by
components):

```css
:root {
  /* Generate scales with OKLCH — adjust lightness channel */
  --brand-50:  oklch(0.97 0.02 250);
  --brand-100: oklch(0.93 0.04 250);
  --brand-200: oklch(0.86 0.08 250);
  --brand-300: oklch(0.75 0.12 250);
  --brand-400: oklch(0.65 0.16 250);
  --brand-500: oklch(0.55 0.20 250);  /* Primary midpoint */
  --brand-600: oklch(0.48 0.18 250);
  --brand-700: oklch(0.40 0.16 250);
  --brand-800: oklch(0.32 0.12 250);
  --brand-900: oklch(0.25 0.08 250);
  --brand-950: oklch(0.18 0.05 250);

  /* Neutral scale */
  --gray-50:  oklch(0.98 0.003 250);
  --gray-100: oklch(0.93 0.005 250);
  --gray-500: oklch(0.55 0.014 250);
  --gray-900: oklch(0.21 0.006 250);
}
```

**Tier 2 — Semantic Colors** (purpose-driven, what components reference):

```css
:root {
  --background: var(--gray-50);
  --foreground: var(--gray-900);
  --primary: var(--brand-600);
  --primary-hover: var(--brand-700);
  --primary-foreground: white;
  --secondary: var(--gray-100);
  --secondary-foreground: var(--gray-900);
  --muted: var(--gray-100);
  --muted-foreground: var(--gray-500);
  --destructive: oklch(0.55 0.20 25);
  --success: oklch(0.55 0.16 145);
  --warning: oklch(0.75 0.16 85);
  --border: var(--gray-200);
  --ring: var(--brand-500);
}
```

**Tier 3 — Component Colors** (specific to individual components):

```css
:root {
  --button-bg: var(--primary);
  --button-text: var(--primary-foreground);
  --button-radius: var(--radius-md);
  --input-border: var(--border);
  --card-bg: var(--background);
  --card-border: var(--border);
}
```

### 3.3 Color Palette Strategy (Bold Direction)

Commit to a **dominant color + sharp accent** strategy. Timid, evenly
distributed palettes produce forgettable interfaces:

- Pick ONE dominant brand color and push it hard
- Choose ONE contrasting accent for critical interactive elements
- Use neutrals for everything else — the fewer colors competing, the stronger
  the visual identity
- Ensure the dominant color appears at every visual hierarchy level: background
  tints, border accents, icon fills, CTA buttons

### 3.4 Color Accessibility Rules

| Context | Minimum Contrast Ratio | How to Check |
|---------|----------------------|--------------|
| Normal text (< 18px) | 4.5:1 | `oklch` lightness delta ≥ 0.40 |
| Large text (≥ 18px or 14px bold) | 3:1 | `oklch` lightness delta ≥ 0.30 |
| UI components (borders, icons) | 3:1 | Against adjacent colors |
| Focus indicators | 3:1 | Against both background and element |

---

## 4. Spacing System

### 4.1 The 8-Point Grid

All spacing values must be multiples of 4px, with 8px as the primary unit.
This creates visual consistency and alignment across all components:

```
Scale:  0    1    2    3    4    5    6    8    10   12   16   20   24
Pixels: 0    4    8    12   16   20   24   32   40   48   64   80   96
Token:  none xs   sm   -    md   -    lg   xl   -   2xl  3xl  -    4xl
```

### 4.2 Content Spacing Standards

| Context | Spacing | Rationale |
|---------|---------|-----------|
| Between label and input | 4px (0.25rem) | Close association |
| Between input and error message | 4px (0.25rem) | Close association |
| Between form fields (same group) | 16–24px (1–1.5rem) | Visual grouping |
| Between form groups | 32–48px (2–3rem) | Clear separation |
| Between sections on a page | 64–96px (4–6rem) | Major section break |
| Between card header and body | 16px (1rem) | Breathing room |
| Between list items | 8–12px (0.5–0.75rem) | Distinguishable but compact |
| Between heading and paragraph | 8–12px (0.5–0.75rem) | Clear relationship |

---

## 5. Backgrounds & Visual Depth

### 5.1 Creating Atmosphere

Default to creating atmosphere and depth rather than solid flat colors.
Match the background treatment to the chosen aesthetic direction:

| Technique | Effect | Best For |
|-----------|--------|----------|
| **Gradient meshes** | Organic, flowing color transitions | Hero sections, landing pages |
| **Noise/grain textures** | Tactile, analog warmth | Editorial, playful, retro aesthetics |
| **Geometric patterns** | Structured, technical precision | Dev tools, industrial, data products |
| **Layered transparencies** | Depth, glassmorphism | Modern SaaS, AI products |
| **Dramatic shadows** | Three-dimensionality, elevation | Card-heavy layouts, dashboards |
| **Subtle dot/line grids** | Technical precision, blueprint feel | Engineering tools, portfolios |

### 5.2 Dark Mode Implementation

Dark mode is **not optional** — every project must support light and dark:

- **DO NOT** simply invert colors. Dark mode requires deliberate color adjustment
- Background: Use dark grays (`oklch(0.15–0.20 ...)`) — never pure black `#000000`
- Text: Use off-white (`oklch(0.93–0.96 ...)`) — never pure `#ffffff`
- Shadows: Subtler or replaced with borders
- Brand colors: Desaturate slightly (reduce chroma by 10–15%) to prevent "glow"
  effect on dark backgrounds
- Detection: Use `class` strategy (`.dark` on `<html>`) for user override,
  default to `prefers-color-scheme` media query

```css
.dark {
  --background: oklch(0.15 0.01 250);
  --foreground: oklch(0.93 0.01 250);
  --primary: oklch(0.65 0.15 250);     /* Lighter, less saturated */
  --border: oklch(0.25 0.02 250);
  --muted: oklch(0.22 0.02 250);
}
```

---

## 6. Animation & Motion

### 6.1 Purpose-Driven Motion

Every animation must serve a functional purpose — never decorative alone.
However, well-orchestrated motion is a powerful differentiator:

| Category | Purpose | Duration | Examples |
|----------|---------|----------|----------|
| **Entry** | Elements appearing | 200–500ms | Fade-in, slide-up, scale-in |
| **Exit** | Elements leaving | 150–300ms | Fade-out, slide-down |
| **State change** | Transitioning states | 150–300ms | Color change, expansion |
| **Feedback** | Confirming action | 100–200ms | Button press, checkmark |
| **Loading** | Indicating progress | 500–2000ms (loop) | Spinner, skeleton pulse |
| **Shared element** | Spatial context | 300–500ms | Hero transitions, list expand |

### 6.2 Timing Tokens

```css
:root {
  /* Duration */
  --duration-instant: 0ms;
  --duration-fast: 100ms;
  --duration-normal: 200ms;
  --duration-moderate: 300ms;
  --duration-slow: 500ms;

  /* Easing */
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);  /* Delightful overshoot */
  --ease-decelerate: cubic-bezier(0, 0, 0.2, 1);
}
```

### 6.3 High-Impact Motion Strategy

Focus motion budget on the **highest-impact moments**:

1. **Page load orchestration**: Staggered reveals using `animation-delay`
   create more delight than scattered micro-interactions
2. **Scroll-triggered reveals**: Elements animate into view as they enter the
   viewport — use `IntersectionObserver` or `scroll-timeline`
3. **Hover states that surprise**: Subtle scale, shadow lift, or color shifts
   on interactive elements
4. **View Transitions API**: Prefer native browser view transitions over JS
   animation libraries for page/route transitions

### 6.4 Reduced Motion

Always respect `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 7. Spatial Composition

### 7.1 Breaking Generic Layouts

Avoid predictable, symmetric, evenly-spaced compositions. Consider:

- **Asymmetry**: Off-center hero text, unequal column splits (60/40, 70/30)
- **Overlap**: Elements that break grid boundaries create visual interest
- **Diagonal flow**: Tilted sections, angled dividers between page sections
- **Grid-breaking elements**: One element that intentionally spans or escapes
  the grid creates a focal point
- **Generous negative space OR controlled density**: Both extremes work —
  the middle produces blandness

### 7.2 Visual Hierarchy Through Composition

| Technique | Effect |
|-----------|--------|
| **Scale contrast** | One element dramatically larger than its neighbors |
| **Color weight** | The brightest/most saturated element draws the eye first |
| **Isolation** | An element surrounded by whitespace gains importance |
| **Position** | Top-left (in LTR) is read first; use for most important content |
| **Motion** | The only moving element in a static composition commands attention |
