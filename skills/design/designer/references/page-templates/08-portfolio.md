# Template 08: Portfolio / Personal Site

**Scope**: Personal portfolio, freelancer site, or personal brand page.
Emphasizes visual impact and personality.

**Layout Architecture**: Single-page scroll with distinct sections.

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│ NAVBAR (minimal, transparent over hero)       │
│ [Name]                    [Work About Contact]│
├──────────────────────────────────────────────┤
│ HERO SECTION                                 │
│ Name (display, large)                        │
│ Role/Title (subtitle, muted)                 │
│ Brief tagline (1-2 lines)                    │
│ [View My Work] [Get in Touch]                │
│ (Optional: subtle background animation)       │
├──────────────────────────────────────────────┤
│ SELECTED WORK / PROJECTS                     │
│ Bento grid or masonry layout                 │
│ ┌──────────┐ ┌──────────┐                   │
│ │ Project  │ │ Project  │                   │
│ │ (large)  │ │ (medium) │                   │
│ └──────────┘ └──────────┘                   │
│ ┌──────┐ ┌──────┐ ┌──────┐                 │
│ │Proj  │ │Proj  │ │Proj  │                 │
│ │(sm)  │ │(sm)  │ │(sm)  │                 │
│ └──────┘ └──────┘ └──────┘                 │
├──────────────────────────────────────────────┤
│ ABOUT SECTION                                │
│ Photo + Bio text (2-column on desktop)        │
│ Skills/technologies list                     │
│ Experience timeline                          │
├──────────────────────────────────────────────┤
│ CONTACT SECTION                              │
│ Heading + description                        │
│ Contact form OR email link + social links    │
├──────────────────────────────────────────────┤
│ FOOTER (minimal)                             │
└──────────────────────────────────────────────┘
```

## Project Card Design

- Thumbnail image or video preview
- Project title
- Brief description (1–2 lines)
- Tags: [React] [Next.js] [Tailwind]
- Hover: Subtle scale + overlay with "View Project" text
