---
name: design-qa
description: >-
  This skill should be used when the user asks to "review the design",
  "audit the frontend", "visual QA", "check the UI quality",
  "fix UI issues", "design audit", "review component styling",
  "check design tokens", "run design-qa", "audit CSS quality",
  "find design inconsistencies", "does this look right?", "check
  the visual hierarchy", "polish this UI", "check the spacing", "are
  the margins right?", "visual refactor this", or wants systematic
  visual quality assurance of frontend implementations. Audits rendered output against design
  tokens and visual best practices across 10 domains (hierarchy,
  typography, spacing, color, states, responsive, AI slop). Applies
  mechanical CSS fixes directly (up to 30 per session) and presents
  subjective findings for user decision.
  DO NOT USE for performance or accessibility auditing (use frontier).
  DO NOT USE for structural component refactoring — design-qa changes
  CSS values, not component architecture.
version: 1.0.0
---

# Design-QA — Frontend Visual Quality Assurance Specialist

## Purpose

This skill performs systematic visual quality assurance of frontend implementations by auditing the actual rendered output against design specifications, design tokens, and visual best practices. Where `frontier` audits frontend code for performance, accessibility, and security, design-qa audits for **visual correctness** — does the implementation look right, feel right, and stay consistent?

Every finding includes the specific source file, line number, and a concrete fix. Findings are classified as mechanical (CSS values, spacing, sizing) or subjective (hierarchy, balance, rhythm), with mechanical fixes applied automatically and subjective findings presented for user decision.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.
Before reviewing, confirm the UI artifact includes both the design spec (tokens,
component inventory) and a rendered build or screenshot set. If either is missing,
state the gap — do not infer visual intent from code alone.

## Differentiation

| Aspect | frontier | design-qa |
|--------|----------|-----------|
| **Focus** | Performance, a11y, security, architecture | Visual correctness, design consistency |
| **Output** | Audit report with scores | Audit + fixes applied |
| **Evidence** | Code analysis | Visual inspection + code analysis |
| **Fixes** | Recommends | Applies mechanical fixes directly |
| **Design tokens** | Checks for existence | Validates usage and consistency |

---

## Design-QA Workflow

### Phase 1: Setup & Detection

1. **Detect design system:**
   - Check for `DESIGN.md`, `design-tokens.json`, or CSS custom property files
   - If found: parse design tokens (colors, spacing, typography, breakpoints)
   - If not found: extract tokens from the existing CSS as the baseline

2. **Detect frontend stack:**
   - Framework (React, Vue, Angular, Svelte, vanilla)
   - CSS approach (Vanilla CSS, Tailwind, CSS-in-JS, SCSS)
   - Component structure

### Phase 2: Baseline Assessment

Read all frontend source files and build a mental model of:
- Color palette in use (all unique color values)
- Typography scale (all font-size, line-height, font-weight values)
- Spacing scale (all margin, padding, gap values)
- Component hierarchy (layout → sections → components → elements)

### Phase 3: Visual Hierarchy Audit

Examine the component tree for hierarchy violations:

| Check | What to Evaluate |
|-------|------------------|
| Heading order | H1→H2→H3 progression without skips |
| Size contrast | Primary elements are larger than secondary |
| Weight contrast | Important text is bolder than body text |
| Color contrast | Active/primary elements have stronger color than inactive |
| Whitespace hierarchy | Section gaps > component gaps > element gaps |

### Phase 4: Typography Audit

| Check | What to Evaluate |
|-------|------------------|
| Font scale consistency | All font-sizes map to the design token scale |
| Line height ratio | Line height is 1.4-1.6× font size for body text |
| Font weight usage | Weights are from the design system, not arbitrary |
| Text alignment | Consistent alignment patterns within sections |
| Orphans/widows | Headings and labels are not left dangling |

### Phase 5: Spacing Audit

| Check | What to Evaluate |
|-------|------------------|
| Spacing scale adherence | All spacing values use design token multiples |
| Consistent gutters | Grid gaps are uniform within sections |
| Touch target spacing | Interactive elements have adequate spacing (min 8px gap) |
| Section rhythm | Vertical rhythm follows a consistent base unit |
| Edge cases | No zero-padding on containers, no collapsed margins causing issues |

### Phase 6: Color Audit

| Check | What to Evaluate |
|-------|------------------|
| Palette adherence | All colors map to design token palette |
| Semantic color usage | Error=red, success=green, warning=amber (or project equivalents) |
| Contrast ratios | Text-on-background meets WCAG AA (4.5:1 normal, 3:1 large) |
| Dark mode consistency | If dark mode exists, all colors have dark mode equivalents |
| Color harmony | No clashing adjacent colors |

### Phase 7: Interactive State Audit

| State | What to Verify |
|-------|---------------|
| Default | Base appearance is clean and intentional |
| Hover | Visual feedback on interactive elements |
| Focus | Focus ring visible and meets WCAG 2.2 requirements |
| Active/Pressed | Tactile feedback (scale, color shift) |
| Disabled | Visually distinct, not just opacity change |
| Loading | Loading indicator or skeleton, not blank/frozen |
| Error | Error state visually distinct with descriptive text |
| Empty | Empty states are helpful, not blank |

### Phase 8: Responsive Audit

| Breakpoint | What to Check |
|-----------|--------------|
| 320px (mobile) | No horizontal overflow, readable text, stacked layout |
| 768px (tablet) | Appropriate column count, touch-friendly spacing |
| 1024px+ (desktop) | Full layout utilized, no excessive whitespace |
| Between breakpoints | No layout breaks at intermediate widths |

### Phase 9: AI Slop Detection

Identify hallmarks of AI-generated or lazy-generated UI using a systematic 3-step methodology:

**Step 1: Pattern scan** — Grep for obvious signals:

| Signal | Detection Method | Severity |
|--------|-----------------|----------|
| Generic placeholder text | Search for "Lorem ipsum", "Your content here", "placeholder", "example.com" in rendered text | Major |
| Stock gradient abuse | Search for `linear-gradient` with >3 color stops that serve no design purpose | Minor |
| Missing states | Check each interactive component for error, loading, empty, disabled states | Major — per missing state |
| Identical components | Compare sibling component styles — flag copy-paste with zero variation | Minor |
| Orphaned styles | Match CSS rules against rendered DOM — flag rules with no matching element | Minor |
| Magic numbers | Find hardcoded pixel values (e.g., `margin: 13px`) not in the design token scale | Major |

**Step 2: Semantic coherence check** — Verify that the visual output tells a coherent story:
- Does the color palette have a clear primary/secondary/accent hierarchy?
- Does the typography scale serve readability (not just aesthetics)?
- Are interactive affordances consistent (all buttons look like buttons)?
- Is the whitespace intentional (consistent rhythm) or arbitrary?

**Step 3: Confidence assessment** — Rate the overall AI slop risk:
- **Clean**: 0-1 signals detected, coherent visual story
- **Suspect**: 2-4 signals detected, some incoherence
- **Detected**: 5+ signals detected or fundamental coherence failure

If slop is Detected, classify as a Major finding and recommend a manual design review before proceeding.

### Phase 10: Report & Fix

**Classification:**

| Type | Action |
|------|--------|
| Mechanical (CSS values, spacing, sizing) | Fix directly with atomic commits |
| Subjective (hierarchy, balance, aesthetics) | Present options, let user decide |
| Structural (component architecture) | Document recommendation, do not change |

**Fix protocol for mechanical issues:**

1. Locate the source file and line
2. Apply the minimal CSS/styling change
3. Verify the fix does not break other components
4. Commit with a descriptive message: `fix(ui): {what was fixed}`

**Self-regulation:**
- Hard cap at 30 fixes per session
- If >30 mechanical issues found, prioritize by visibility (above-the-fold first)
- Present the remaining issues as recommendations

**Output report:**

```markdown
# DESIGN-QA AUDIT REPORT

## Design System Status
- Design tokens: [Found / Extracted / Missing]
- Token adherence: [High / Medium / Low]

## Domain Scores

| Domain | Score | Issues Found | Fixed |
|--------|-------|-------------|-------|
| Visual Hierarchy | [Pass/Warn/Fail] | [n] | [n] |
| Typography | [Pass/Warn/Fail] | [n] | [n] |
| Spacing | [Pass/Warn/Fail] | [n] | [n] |
| Color | [Pass/Warn/Fail] | [n] | [n] |
| Interactive States | [Pass/Warn/Fail] | [n] | [n] |
| Responsive | [Pass/Warn/Fail] | [n] | [n] |
| AI Slop | [Clean/Detected] | [n] | [n] |

## Findings (by severity)
[Structured findings with evidence, source location, and fix status]

## Applied Fixes
[List of files changed with before/after descriptions]

## Recommendations
[Subjective and structural recommendations for user review]
```

Append the structured pipeline summary:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 7
skill: design-qa
status: COMPLETE
risk_assessment: [High / Medium / Low]
domain_scores:
  visual_hierarchy: [Pass / Warn / Fail]
  typography: [Pass / Warn / Fail]
  spacing: [Pass / Warn / Fail]
  color: [Pass / Warn / Fail]
  interactive_states: [Pass / Warn / Fail]
  responsive: [Pass / Warn / Fail]
  ai_slop: [Clean / Detected]
finding_count:
  critical: [n]
  major: [n]
  minor: [n]
fixes_applied: [n]
verdict: [Pass / Conditional / Fail]
---
```

**Worked visual-fix example:**

**Phase:** Token Adherence (Phase 2)
**Finding:** Card component uses hardcoded `border-radius: 12px` instead of the design token `--radius-lg` (which resolves to 12px today but may change).

**Before:**
```css
.card { border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
```

**After:**
```css
.card { border-radius: var(--radius-lg); box-shadow: var(--shadow-md); }
```

**Why:** Hardcoded values bypass the token system. When the design team updates `--radius-lg` to 16px for a brand refresh, this card would remain at 12px, creating visual inconsistency. Token references ensure all components update atomically.

---

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation after frontier (Phase 6) completes
- Execute the full 10-phase audit
- Apply mechanical fixes directly
- Submit report and remaining recommendations to code-chief
- Include the structured pipeline summary block

**When invoked standalone:**
- Execute the full 10-phase audit independently
- Apply mechanical fixes directly
- Present the report to the user

---

## Proactive Triggers

Invoke design-qa proactively after frontend design changes, component library
updates, or when visual inconsistencies are reported.

---

## Important Rules

1. **CSS-first philosophy.** Prefer CSS/styling changes over structural/HTML changes.
2. **Atomic commits.** Each fix is one commit with a descriptive message.
3. **Self-regulate.** Hard cap at 30 fixes. Prioritize by visibility.
4. **Mechanical vs subjective.** Fix mechanical issues. Present subjective ones.
5. **Treat design tokens as the single source of truth** because hardcoded values silently drift when the design system updates. If design tokens exist, they govern all values.
6. **No structural changes.** Do not rearrange component architecture. Document and recommend. If a structural change is essential for visual correctness (e.g., a layout container is missing entirely), escalate to code-chief with the recommendation and evidence. Code-chief routes structural changes through bob-the-builder.
7. **Conflicting design systems.** If the codebase mixes multiple design systems (e.g., both Material UI and a custom token set), flag the conflict as a Major finding. Audit against the project's declared design system; if none is declared, audit against the dominant system by file count and recommend consolidation.

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No design tokens or design system | Extract implicit tokens from existing CSS as baseline. Note the absence as a Major finding and recommend establishing a design token file. Score against the extracted baseline. |
| Server-rendered pages (no SPA) | Adjust interactive state audit — server-rendered pages may lack client-side hover/focus states. Check that server-generated HTML has correct semantic structure. All other phases apply normally. |
| CSS-in-JS (styled-components, Emotion) | File:line references point to JS/TS files. Parsing is harder but the same checks apply — look for theme tokens, spacing constants, and color tokens in the theme provider. |
| Tailwind-only styling | Check for consistent utility class usage rather than raw CSS values. Design token adherence maps to Tailwind config (theme.extend). Flag custom arbitrary values (`[14px]`) that bypass the design system. |
| No frontend code in change set | Report "Not applicable — no frontend files in scope" and skip the audit. Do not generate phantom findings. |
| Legacy codebase with no consistent patterns | Lower the baseline expectations but still flag the worst offenders. Prioritize above-the-fold visibility and user-facing pages. |
| Dark mode exists but is incomplete | Flag every component missing dark mode equivalents. Classify as Major if user-facing, Minor if admin-only. |
| Mechanical fix limit exceeded (>30 issues) | Stop applying fixes at 30. Present the remaining issues ranked by visibility. Recommend a dedicated cleanup pass. |
| Print stylesheets exist or are expected | Audit `@media print` rules for hidden navigation, readable font sizes, forced light background, and page-break control. Score print quality separately because screen-optimized tokens (shadows, gradients, animations) waste ink and hurt readability on paper. |
| RTL language support is required | Verify `dir="rtl"` on `<html>`, logical CSS properties (`margin-inline-start` instead of `margin-left`), mirrored icons, and bidirectional text handling. Flag any physical direction properties (`left`/`right`) as Major because they break layout for RTL users. |

---

## Additional Resources

### Reference Files

- **`references/visual-audit-checklist.md`** — The canonical per-domain audit checklist with framework-specific checks, scoring anchors, and evidence expectations for each visual domain
- **`references/frontend-patterns.md`** — Common frontend design patterns, component archetypes, token usage conventions, and CSS best practices used to judge whether the implementation feels intentional rather than generic

---
*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the audit report, write it to the designated save path as `deliverable_design-qa-report.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 7
   skill: design-qa
   name: Design QA Report
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations.

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
