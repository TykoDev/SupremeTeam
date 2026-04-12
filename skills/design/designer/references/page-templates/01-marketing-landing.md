# Template 01: Marketing Landing Page

**Scope**: Primary conversion page for products, services, or campaigns.
Single-page scroll with distinct sections.

**Layout Architecture**: Full-width sections with centered content containers.
No sidebar. Single-column content flow on mobile, multi-column within sections
on desktop.

---

## Section Breakdown

```
┌─────────────────────────────────────────────┐
│ NAVBAR (sticky)                              │
│ [Logo]          [Features Pricing About] [CTA]│
├─────────────────────────────────────────────┤
│ HERO SECTION                                 │
│ Badge: "Now in Beta"                         │
│ Headline (display, max 60 chars)             │
│ Subheadline (muted, 1-2 lines)               │
│ Primary CTA + Secondary CTA                  │
│ Hero visual (screenshot/illustration)        │
│ Social proof: "Trusted by X users"           │
├─────────────────────────────────────────────┤
│ LOGOS / SOCIAL PROOF BAR                     │
│ 4-6 logo icons in a horizontal row           │
├─────────────────────────────────────────────┤
│ PROBLEM SECTION (optional)                   │
│ Heading + description                        │
│ 2-3 pain points with icons                   │
├─────────────────────────────────────────────┤
│ FEATURES SECTION                             │
│ Section heading + description                │
│ 3-column grid of feature cards               │
│ [Icon] Feature title                         │
│ Feature description (2-3 lines)              │
├─────────────────────────────────────────────┤
│ FEATURE HIGHLIGHT (alternating)              │
│ [Image/Mockup]  Feature title               │
│                 Feature description          │
│                 Checklist of capabilities    │
│ (Alternates: image-left / image-right)       │
├─────────────────────────────────────────────┤
│ TESTIMONIALS SECTION                         │
│ Section heading                              │
│ 3-column grid of testimonial cards           │
│ Quote + Author name + Role + Avatar          │
├─────────────────────────────────────────────┤
│ PRICING SECTION (or link to pricing page)    │
├─────────────────────────────────────────────┤
│ FAQ SECTION                                  │
│ Accordion of 5-8 frequently asked questions  │
├─────────────────────────────────────────────┤
│ FINAL CTA SECTION                           │
│ Bold headline + description                  │
│ Primary CTA button                           │
├─────────────────────────────────────────────┤
│ FOOTER                                       │
│ 4-column: Product, Resources, Company, Legal │
│ Bottom bar: Copyright + Social links         │
└─────────────────────────────────────────────┘
```

---

## Responsive Behavior

- **Mobile**: Full-width sections, stacked layout, hamburger menu, hero image
  below text
- **Tablet**: 2-column feature grid, hero image beside text
- **Desktop**: 3-column feature grid, sticky navbar, max-width 1280px container

## Content Strategy

Lead with the value proposition in the hero (what the user gets, not what the
product does). Use social proof early (after hero or in hero itself). Address
objections in FAQ. End with the primary CTA.
