---
name: prototyper
description: >-
  Builds one redesign variant: tokens, a framework-free shadcn-shaped component
  library with a living catalog, and a single-page HTML prototype at parity with the
  design inventory. Use when `design/redesign` delegates a variant build, or the user
  asks for a living HTML prototype, a clickable mock of a design direction, or one of
  several directions made real to compare — even when the ask is just "show me this
  direction". Builds a prototype to judge, not shippable product code, which is
  `build/build-management`. One variant per delegation.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
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
- "show me this direction" — the underspecified ask, once one direction is already on the table
- "build the prototype at parity with the design inventory" — every inventoried screen and state actually rendered, not a representative sample

Route elsewhere to decide directions (`design/architect`) or to verify parity as gate evidence (`design/design-mapper`).

## Entry Routing

Prototyper is an internal design specialist, not an entry point.
`../../routing-doctrine.md` places every `design/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator, and `../../pipelines.yaml` names `redesign` the owner of the
`redesign` pipeline this skill's `variant-build` stage belongs to. The
description's "show me this direction" is the cold path this check closes. Run the
active-handoff check before building anything: the approved direction, the hashed
design inventory and its baseline captures, the effective Taste snapshot digest,
which of the four fan-out variants this delegation is, and the save path all
arrive with the handoff, and none of them can be reconstructed cold.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `design/redesign` as the
delegating owner for the `redesign-review` boundary.

- **Handoff present** → proceed; this is one delegated `variant-build` assignment,
  one variant per delegation.
- **Reached cold** → build no variant. Return to `design/redesign`, which owns
  stage sequencing and the recommendation, then accept the delegation back.
  Without an approved direction there is nothing to be faithful to, and without
  the hashed inventory `skills/scripts/check_parity.py` has no id list to score
  against, so what comes back is a mockup rather than the `variant_set` entry the
  gate counts.

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

### Gate evidence owned

`../../gates.yaml` `evidence_owners` assigns `variant_set` to prototyper. One delegation contributes one entry; `design/redesign` assembles the four entries into the single record it packages at `redesign-review`.

| Key | Boundary | Must contain | Artifact-backed | Fallback |
| --- | --- | --- | --- | --- |
| `variant_set` | `redesign-review` | A record `{artifacts, variants: [{id, name, direction, spec, tokens, components, app}], count}` holding exactly the four variants `evidence_type_params.variant_set.required_count` requires, with unique ids, and with the `spec`, `tokens`, `components`, and `app` of every variant correctly hashed in the package; `count`, when present, equals the list length | Yes — every variant file is a hashed artifact in `artifact_hashes` | None sanctioned; a set short of four variants fails mechanically and returns as a `REVISE` |

Returning a variant whose files are unhashed, whose id collides with a sibling's, or which is one of three rather than four breaks the record for the whole set, so each delegation returns its id and its six sha256 digests explicitly.

## Workflow

1. Read the direction, the inventory, and the doctrine before writing a line; list every route, state, component, interaction, and flow id the prototype must carry.
2. Write `tokens.css` first: derive every value from the direction's token strategy, verify body and large-text contrast to WCAG 2.2 AA in both themes, and keep one spacing scale, one type scale, one radius, and one shadow elevation.
3. Build the component library with shadcn-shaped primitives (Button, Input, Label, Form, Dialog, Sheet, DropdownMenu, Tabs, Table, Toast, Tooltip, Separator, ScrollArea, and any the inventory maps) as plain HTML, CSS classes, and small JavaScript behaviours; no framework, no bundler, no CDN.
4. Write `components.html`: one section per component, every variant and size, every state (default, hover, focus-visible, active, disabled, loading, error), light and dark side by side, each instance marked `data-component`.
5. Write `app.html`: an app shell for the direction, a hash router that renders one view per inventory route (`data-route`), a state switcher that renders every declared state per route (`data-state` or `data-route-state`), mocked data in memory, every interaction as a working control (`data-interaction`), every flow traversable end to end (`data-flow`), keyboard paths and focus management, dark-mode toggle, and behaviour that honours `prefers-reduced-motion`.
6. Self-check: open both files without a network and walk every route and state, then resolve the scratch destination with `python skills/scripts/output_paths.py --kind test_work --name parity-selfcheck-<id>.json` and run `python skills/scripts/check_parity.py --inventory <inventory> --app app.html --components components.html --out <the resolver's `relative` value> --project-root .`. Fix every missing id before returning. The resolver returns JSON whose `relative` field is the path to pass, always under `.harness-state/test-work/`, and exits non-zero on an absolute or traversing name — that exit is the containment check, so never compose the scratch path by hand.
7. Write `variant.md`, return every file path with its sha256, and stop; the mapper's parity record, not the self-check, is gate evidence.

## Required Contracts

- **Functional parity**: Every inventory id appears with its marker; every declared state renders, not merely a label saying it would. A missing id is a defect, never a note.
- **Framework-free and offline**: Plain HTML, CSS, and JavaScript; no build step, no network requests, no fonts or scripts fetched at runtime. Bundle any icon set inline.
- **shadcn-shaped**: Component names, variant axes, and token names follow shadcn/ui so the chosen variant maps one-to-one onto the production design system in the design pipeline.
- **Doctrine adherence**: `../../design-doctrine.md` §1 to §6 and §9 apply in full: quiet surface, restraint, one scale of everything, six responsive tiers, accessibility as correctness.
- **Direction fidelity**: The variant expresses its direction and only its direction; it never borrows from a sibling variant. Trace each token and component decision to the direction's Taste rows in `variant.md`.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
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
| The assigned variant id collides with a sibling's, or the delegation supplies no id | Stop and ask `design/redesign` for the id before writing a file. `variant_set` requires four unique ids, so a collision breaks the record for the whole set, not just this variant, and the four builds run in parallel with no way to notice locally. |
| The inventory revision changed since the delegation | Stop, report the hash drift to `design/redesign`, and rebuild only against the new inventory. |
| The direction, the inventory, or the Taste snapshot digest is missing or malformed in the delegation | Build nothing. Name the missing input and return to `design/redesign`; a variant invented from a partial direction cannot be compared against its siblings, and its Taste traceability rows would cite a digest that does not exist. |
| `design/gatekeeper-design` returns a `REVISE` naming `variant_set` for this variant | Take the whole owner group in `revise_packet.by_owner` as one batch, fix every finding in a single rebuild, and return the changed files with new sha256 digests so the gate re-judges only `changed_evidence`. |
| Python or `check_parity.py` is unavailable in the host | Walk every inventory id by hand against the rendered markup, return the variant with the self-check recorded as unavailable and the reason stated, and flag it to `design/redesign`. Never report a coverage number no probe produced; the mapper's run remains the authority. |
| An icon, font, or script is only available from a CDN | Inline a bundled equivalent or a plain fallback; the prototype must open offline. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the six variant files to `redesign/artifacts/variants/<id>/` at the destination the delegation names. Resolve each one with `python skills/scripts/output_paths.py --run-id {run-id} --phase redesign --kind artifacts --name variants/<id>/<file>`; `--run-id` is required and the command exits non-zero without it.
2. Put self-check scratch output where `python skills/scripts/output_paths.py --kind test_work --name parity-selfcheck-<id>.json` resolves it, under `.harness-state/test-work/`, never beside the variant. The scratch record is not gate evidence and is not returned.
3. Return each file path with its sha256 so the phase lead can register it; write nothing else.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the build order, the prototype architecture, the inventory fields this skill reads, the marker placement rules, the self-check command, and the acceptance checklist.
- `references/examples.md` for concrete variant outputs and revision responses.
- `../../design-doctrine.md` §5 for the templates `variant.md` fills and §9 for prototype requirements.
- `../../scripts/check_parity.py` for the self-check command and its exit contract.
- `../design-mapper/references/workflow.md` for the authoritative inventory schema and parity-marker contract. It resolves only inside the full catalog; `references/workflow.md` restates the fields and markers this skill reads so the packaged skill never depends on it.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together — the three files this skill owns. Keep generated variants under the run's `redesign/artifacts/variants/` directory, never inside the skill directory.
