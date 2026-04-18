# Design Philosophy

Every design decision made by `designer` must trace back to a deliberate
visual and interaction point of view. The goal is not visual novelty for its
own sake; the goal is a frontend that feels unmistakably chosen rather than
defaulted.

## Core Principles

| Principle | Meaning |
|-----------|---------|
| **Bold & Intentional** | Commit to a clear aesthetic direction and execute it with precision. Generic, safe, cookie-cutter interfaces are unacceptable. |
| **Progressive Disclosure** | Show only what matters at each moment. Complexity is revealed through interaction, not dumped into every screen. |
| **Consistency as Trust** | Same color, icon, motion, and interaction for the same purpose everywhere. Inconsistency erodes confidence. |
| **Accessible by Default** | WCAG 2.2 Level AA is the baseline. Use semantic HTML first and ARIA only where semantics are insufficient. |
| **Performance is Design** | A design that loads slowly is a bad design. Target Core Web Vitals: LCP < 2.5s, INP < 200ms, CLS < 0.1. |
| **Token-First** | Every visual value (color, spacing, font size, shadow, radius, duration) must come from a design token. Zero magic numbers. |

## Visual Identity: Be Unforgettable

Do not produce generic AI-generated aesthetics. The following are prohibited as
default choices:

- **Fonts**: Inter, Roboto, Arial, or system-ui defaults
- **Colors**: Purple gradients on white backgrounds or generic blue/gray schemes
- **Layouts**: Predictable symmetric grids or cookie-cutter card layouts
- **Motion**: No animation, or decorative animation with no communicative role

Instead, commit to a specific aesthetic direction and ensure each visual choice
reinforces it. No two projects should converge on the same visual identity by
accident.

## Decision Test

Use these checks before finalizing the design direction:

1. Can the aesthetic direction be described in one sentence without using vague
   words like "modern" or "clean"?
2. Do typography, color, spacing, backgrounds, and motion all reinforce that
   direction rather than competing with it?
3. Would a reviewer be able to distinguish this project from a default template
   after seeing one screen?
4. Does the design remain accessible and performant after the visual choices
   are applied?

If the answer to any of these is no, refine the direction before handing the
design package to `gatekeeper-design`.