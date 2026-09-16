---
name: prototyper
description: >-
  Builds one design-system variant for the redesign pipeline: a token set, a
  framework-free shadcn-shaped UI component library with a living catalog page,
  and a living single-page HTML prototype that reproduces every route, state,
  component, interaction, and flow in the design inventory at functional parity.
  Use when `design/redesign` delegates a variant build from one design direction,
  or the user asks for a living HTML prototype, a clickable mock of a design
  direction, or a component library preview. Builds exactly one variant per
  delegation; defers direction choice to `design/architect` and parity ownership
  to `design/design-mapper`.
version: 1.0.0
---

# Prototyper

## Purpose

Turn one design direction into something a person can open, click through, and
compare: a complete token set, a UI component library with every variant and
state on one catalog page, and a single-page prototype of the whole surface that
behaves like the current application. Every parity id from the inventory is
present and marked so the parity checker can prove it.

## Use This Skill When

Use this skill to **build one living variant** from an approved direction:

- "build variant two from the directions" — token set, component library, and prototype for one direction
- "give me a living HTML prototype of this direction" — the same, for a single direction
- "preview the component library" — the catalog page for one variant

Route elsewhere to decide directions (`design/architect`) or to verify parity as gate evidence (`design/design-mapper`).

## Inputs

- One direction from `design-directions.md`: name, concept, token strategy, component approach, differentiators, and its Taste traceability rows.
- The hashed design inventory (`design-inventory.json`) and the baseline captures.
- The effective Taste snapshot digest for traceability, the six responsive tiers, and the accessibility floor from `../../design-doctrine.md`.

## Outputs

One `design-system-variant` under `redesign/artifacts/variants/<id>/`:

| File | Content |
| --- | --- |
| `variant.md` | The variant specification: the shadcn Component Template and UI/UX Handoff sections from `../../design-doctrine.md` §5 filled for this variant, the token table, the differentiation statement, the Taste traceability rows, and the state coverage matrix |
| `tokens.css` | Light and dark values for the full shadcn token set (`--background` … `--ring`, `--radius`, chart and sidebar sets when used) plus the typography, spacing, and motion scales |
| `components.css`, `components.js` | The framework-free component library: shadcn-shaped names, variant and size classes, states, focus rings, dialog and menu behaviour, reduced-motion handling |
| `components.html` | The living catalog: every component in every variant, size, and state, each instance marked `data-component="<id>"` |
| `app.html` | The living prototype: hash routing over every inventory route, in-memory state with mocked data, every declared state reachable through a state switcher, every interaction and flow wired, each marked with the parity attributes |

## Workflow

1. Read the direction, the inventory, and the doctrine before writing a line; list every route, state, component, interaction, and flow id the prototype must carry.
2. Write `tokens.css` first: derive every value from the direction's token strategy, verify body and large-text contrast to WCAG 2.2 AA in both themes, and keep one spacing scale, one type scale, one radius, and one shadow elevation.
3. Build the component library with shadcn-shaped primitives (Button, Input, Label, Form, Dialog, Sheet, DropdownMenu, Tabs, Table, Toast, Tooltip, Separator, ScrollArea, and any the inventory maps) as plain HTML, CSS classes, and small JavaScript behaviours; no framework, no bundler, no CDN.
4. Write `components.html`: one section per component, every variant and size, every state (default, hover, focus-visible, active, disabled, loading, error), light and dark side by side, each instance marked `data-component`.
5. Write `app.html`: an app shell for the direction, a hash router that renders one view per inventory route (`data-route`), a state switcher that renders every declared state per route (`data-state` or `data-route-state`), mocked data in memory, every interaction as a working control (`data-interaction`), every flow traversable end to end (`data-flow`), keyboard paths and focus management, dark-mode toggle, and behaviour that honours `prefers-reduced-motion`.
6. Self-check: open both files without a network, walk every route and state, then run `python skills/scripts/check_parity.py --inventory <inventory> --app app.html --components components.html --out <scratch under .harness-state/>` and fix every missing id before returning.
7. Write `variant.md`, return every file path with its sha256, and stop; the mapper's parity record, not the self-check, is gate evidence.

## Required Contracts

- **Functional parity**: Every inventory id appears with its marker; every declared state renders, not merely a label saying it would. A missing id is a defect, never a note.
- **Framework-free and offline**: Plain HTML, CSS, and JavaScript; no build step, no network requests, no fonts or scripts fetched at runtime. Bundle any icon set inline.
- **shadcn-shaped**: Component names, variant axes, and token names follow shadcn/ui so the chosen variant maps one-to-one onto the production design system in the design pipeline.
- **Doctrine adherence**: `../../design-doctrine.md` §1 to §6 and §9 apply in full: quiet surface, restraint, one scale of everything, six responsive tiers, accessibility as correctness.
- **Direction fidelity**: The variant expresses its direction and only its direction; it never borrows from a sibling variant. Trace each token and component decision to the direction's Taste rows in `variant.md`.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/redesign`
- `design/design-mapper` (parity verification and missing-id feedback)
- `review/design-qa` and `review/frontier` (rendered and accessibility evidence on the returned files)

## Review Expectations

- Both HTML files open from disk with no console errors and no network requests.
- Every route, state, component, interaction, and flow in the inventory resolves to a marked element.
- Contrast, focus visibility, keyboard reachability, and reduced-motion behaviour hold in both themes at every tier.
- `variant.md` fills the doctrine §5 templates concretely and names the direction's differentiators.

## Skip Rule

Never skip a file in the variant set. A component the inventory maps to `null` still appears in the catalog under the variant's own name.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A route's state cannot be reproduced with mocked data alone (depends on a live service) | Mock the service response for that state, mark the mock in `variant.md`, and still render the state. |
| The direction's palette cannot reach the contrast floor for body text | Adjust the token to the nearest passing value, record the deviation in `variant.md`, and report it to `design/redesign`; never ship a failing contrast. |
| Parity self-check reports missing ids | Fix every id before returning; a partial variant is not returned. |
| The inventory revision changed since the delegation | Stop, report the hash drift to `design/redesign`, and rebuild only against the new inventory. |
| An icon, font, or script is only available from a CDN | Inline a bundled equivalent or a plain fallback; the prototype must open offline. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the six variant files to `redesign/artifacts/variants/<id>/` at the destination the delegation names (resolved with `python skills/scripts/output_paths.py --phase redesign --kind artifacts`).
2. Put self-check scratch output under `.harness-state/`, never beside the variant.
3. Return each file path with its sha256 so the phase lead can register it; write nothing else.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the build order, the prototype architecture, the marker placement rules, and the acceptance checklist.
- `references/examples.md` for concrete variant outputs and revision responses.
- `../../design-doctrine.md` §5 for the templates `variant.md` fills and §9 for prototype requirements.
- `../design-mapper/references/workflow.md` for the inventory schema and parity-marker contract.
- `../../scripts/check_parity.py` for the self-check command.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated variants under the run's `redesign/artifacts/variants/` directory, never inside the skill directory.
