---
name: prototyper
description: >-
  Builds redesign drafts in two modes: a static mock of one direction, and, once a
  direction is chosen, the living HTML prototype for that one variant. Use when
  `design/redesign` delegates a mock build or the selected build, or the user asks
  to build the mock for a direction, draft this direction to compare it, preview
  the component library, build the selected variant, or build the prototype at
  parity with the design inventory — even when the ask is just "show me this
  direction". Builds a draft to judge, not shippable product code, which is
  `build/build-management`. One draft per delegation.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Prototyper

## Purpose

Turn one design direction into something a person can look at and judge, and
then — only for the direction that was chosen — into something they can click
through. The mock is a drawing: a complete token set, a component catalog, and
one rendered screen per inventory route with hard-coded content. The living
prototype is the implementation: hash routing, mocked data, every state
reachable, every interaction and flow wired. Four mocks are cheap to compare and
cheap to discard; four living prototypes are three implementations built to be
thrown away, which is why the second mode runs after the choice and never before
it.

## Use This Skill When

Use this skill in **one of two delegated modes**, never both in one delegation:

- "build the mock for a direction" — the `mock-build` mode: tokens, catalog, and a static drawn screen per route for one direction
- "draft this direction to compare it" — the same mode, for a single direction
- "preview the component library" — the catalog page for one direction
- "show me this direction" — the underspecified ask, once one direction is already on the table
- "build the selected variant" — the `selected-build` mode: the living single-page prototype for the one direction the user picked
- "build the prototype at parity with the design inventory" — every inventoried screen, state, interaction, and flow actually wired, not a representative sample; this is always the selected build

Route elsewhere to decide directions (`design/architect`) or to verify parity as gate evidence (`design/design-mapper`).

## Entry Routing

Prototyper is an internal design specialist, not an entry point.
`../../routing-doctrine.md` places every `design/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator, and `../../pipelines.yaml` names `redesign` the owner of the
`redesign` pipeline this skill's `mock-build` and `selected-build` stages belong
to. The description's "show me this direction" is the cold path this check
closes. Run the active-handoff check before building anything: the approved
direction, the hashed design inventory and its baseline captures, the effective
Taste snapshot digest, which mode this delegation is and which of the four
fan-out mocks it covers, and the save path all arrive with the handoff, and none
of them can be reconstructed cold.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `design/redesign` as the
delegating owner for the `redesign-review` boundary.

- **Handoff present** → proceed; this is one delegated assignment in one mode,
  one mock per `mock-build` delegation and one variant per `selected-build`.
- **Reached cold** → build nothing. Return to `design/redesign`, which owns
  stage sequencing, the selection record, and the recommendation, then accept the
  delegation back. Without an approved direction there is nothing to be faithful
  to, and without the hashed inventory `skills/scripts/check_parity.py` has no id
  list to score against, so what comes back is a sketch rather than the `mock_set`
  entry the gate counts.

## Inputs

- One direction from `design-directions.md`: name, concept, token strategy, component approach, differentiators, and its Taste traceability rows.
- The hashed design inventory (`design-inventory.json`) and the baseline captures.
- The effective Taste snapshot digest for traceability, the six responsive tiers, and the accessibility floor from `../../design-doctrine.md`.
- For a `selected-build` delegation only: the `selection` record naming the chosen mock id, and that mock's `tokens.css`, `components.css`, and `components.html`, which the living prototype is derived from rather than reinvented against.

## Outputs

Which files a delegation returns depends on its mode.

### Mode 1 — `mock-build` (fan out 4, one delegation per direction)

One `design-mock` under `redesign/artifacts/mocks/<id>/`:

| File | Content |
| --- | --- |
| `variant.md` | The direction specification: the shadcn Component Template and UI/UX Handoff sections from `../../design-doctrine.md` §5 filled for this direction, the token table, the differentiation statement, the Taste traceability rows, and a **Mock scope** note listing which routes are drawn and which route states, if any, are shown |
| `tokens.css` | Light and dark values for the full shadcn token set (`--background` … `--ring`, `--radius`, chart and sidebar sets when used) plus the typography, spacing, and motion scales |
| `components.css` | The framework-free component styles: shadcn-shaped names, variant and size classes, states, focus rings |
| `components.html` | The catalog: every component in every variant, size, and state, each instance marked `data-component="<id>"` |
| `mock.html` | The static draft: one rendered screen per inventory route, `data-route="<id>"` on each screen's root, hard-coded sample content, light and dark through `tokens.css`, and `data-mock="true"` on the root element |

### Mode 2 — `selected-build`

The `selected-build` stage runs only when a variant was selected: `design/redesign`
commissions it after the selection stage, for the one mock id the `selection`
record names as `chosen`, and for no other. One `design-system-variant` under
`redesign/artifacts/variants/<id>/`:

| File | Content |
| --- | --- |
| `variant.md` | The selected variant's specification: the same doctrine §5 templates and Taste traceability rows, now with the state coverage matrix the living prototype actually satisfies |
| `tokens.css` | The selected mock's token set, carried forward and completed where the mock left a scale unused |
| `components.css`, `components.js` | The full component library: the mock's styles plus the behaviours that need script (dialog and menu behaviour, focus traps, tabs, toasts, tooltips, reduced-motion handling) |
| `components.html` | The living catalog: every component in every variant, size, and state, each instance marked `data-component="<id>"` |
| `app.html` | The living prototype: hash routing over every inventory route, in-memory state with mocked data, every declared state reachable through a state switcher, every interaction and flow wired, each marked with the parity attributes |

### Gate evidence owned

`../../gates.yaml` `evidence_owners` assigns both `mock_set` and
`selected_variant` to prototyper. One `mock-build` delegation contributes one
entry to the first; `design/redesign` assembles the four entries into the single
record it packages at `redesign-review`. One `selected-build` delegation
produces the whole of the second.

| Key | Boundary | Must contain | Artifact-backed | Fallback |
| --- | --- | --- | --- | --- |
| `mock_set` | `redesign-review` | A record `{artifacts, mocks: [{id, name, direction, spec, tokens, components, mock}], count}` holding exactly the four mocks `evidence_type_params.mock_set.required_count` requires, with unique ids, and with the `spec`, `tokens`, `components`, and `mock` of every mock correctly hashed in the package; `count`, when present, equals the list length | Yes — every mock file is a hashed artifact in `artifact_hashes` | None sanctioned; a set short of four mocks fails mechanically and returns as a `REVISE` |
| `selected_variant` | `redesign-review` | A record `{artifacts, variants: [{id, name, direction, spec, tokens, components, app}], count}` holding exactly one variant, whose `id` equals `selection.chosen`, with `spec`, `tokens`, `components`, and `app` correctly hashed in the package | Yes — every variant file is a hashed artifact in `artifact_hashes` | The sanctioned strings `selection deferred - no variant built` and `merge brief recorded - implemented as a fifth direction in the design pipeline`, and only when `selection.decision` is not `variant`. Neither is this skill's to write: `design/redesign` records them when no build was commissioned, carried at schema 2 as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}` rather than as a bare string |

Returning a mock whose files are unhashed, whose id collides with a sibling's, or
which is one of three rather than four breaks the record for the whole set, so
each `mock-build` delegation returns its id and its five sha256 digests
explicitly. A `selected-build` returns its id and its six.

## Workflow

Step 1 is the same in both modes. Steps 2 onward fork.

1. Read the direction, the inventory, and the doctrine before writing a line; confirm the mode from the delegation and list every id the delegation's level is scored on — routes and components for a mock, every list for the selected build.

### Mock build

2. Write `tokens.css` first: derive every value from the direction's token strategy, verify body and large-text contrast to WCAG 2.2 AA in both themes, and keep one spacing scale, one type scale, one radius, and one shadow elevation.
3. Write `components.css` and the `components.html` catalog: one section per component, every variant and size, every state rendered as a static appearance (default, hover, focus-visible, active, disabled, loading, error), light and dark side by side, each instance marked `data-component`.
4. Write `mock.html`: one screen per inventory route with `data-route="<id>"` on the screen's root, `data-mock="true"` on the root element, hard-coded sample content that reads like the real thing, and every inventory component present somewhere across the catalog and the screens. Draw route states as extra static screens (`data-route-state`) only where the direction is easier to judge with them.
5. Self-check: open both files without a network, then resolve the scratch destination with `python skills/scripts/output_paths.py --kind test_work --name parity-selfcheck-<id>.json` and run `python skills/scripts/check_parity.py --level mock --inventory <inventory> --app mock.html --components components.html --out <the resolver's `relative` value> --project-root .`. Mock level scores routes and components only; interactions, flows, and states come back as informational counts and never fail it. Fix every missing route or component id before returning.
6. Write `variant.md` including the Mock scope note, return every file path with its sha256, and stop; the mapper's parity record, not the self-check, is gate evidence.

### Selected build

2. Confirm the `selection` record names `decision: variant` and that its `chosen` id is the id this delegation was given. Read the selected mock's `tokens.css`, `components.css`, and `components.html`; the living prototype is derived from them, not designed again.
3. Carry the mock's tokens forward into `tokens.css`, completing only the scales the mock left unused, and re-verify contrast in both themes.
4. Grow `components.css` and add `components.js`: the shadcn-shaped primitives the inventory maps (Button, Input, Label, Form, Dialog, Sheet, DropdownMenu, Tabs, Table, Toast, Tooltip, Separator, ScrollArea, and any others) as plain HTML, CSS classes, and small JavaScript behaviours; no framework, no bundler, no CDN.
5. Extend `components.html` into the living catalog: every primitive, every variant and size, every real state, each instance marked `data-component`.
6. Write `app.html`: an app shell for the direction, a hash router that renders one view per inventory route (`data-route`), a state switcher that renders every declared state per route (`data-state` or `data-route-state`), mocked data in memory, every interaction as a working control (`data-interaction`), every flow traversable end to end (`data-flow`), keyboard paths and focus management, dark-mode toggle, and behaviour that honours `prefers-reduced-motion`. `data-mock` does not appear here; this is not a mock.
7. Self-check at full level: resolve the scratch destination as above and run `python skills/scripts/check_parity.py --level full --inventory <inventory> --app app.html --components components.html --out <the resolver's `relative` value> --project-root .`. Fix every missing id before returning.
8. Write `variant.md` with the state coverage matrix, return every file path with its sha256, and stop.

## Required Contracts

- **Mode discipline**: A mock is a drawing and the selected build is an implementation. A mock never gains a router, a state machine, or a wired interaction, and the selected build is never returned for a direction the `selection` record did not choose.
- **Functional parity**: Every inventory id the level scores appears with its marker; in the selected build every declared state renders, not merely a label saying it would. A missing id is a defect, never a note.
- **Framework-free and offline**: Plain HTML, CSS, and JavaScript; no build step, no network requests, no fonts or scripts fetched at runtime. Bundle any icon set inline. A mock adds one more limit: the only script it may carry is an optional theme toggle and an optional screen picker that shows and hides the static screens.
- **shadcn-shaped**: Component names, variant axes, and token names follow shadcn/ui so the chosen direction maps one-to-one onto the production design system in the design pipeline.
- **Doctrine adherence**: `../../design-doctrine.md` §1 to §6 and §9 apply in full: quiet surface, restraint, one scale of everything, six responsive tiers, accessibility as correctness.
- **Direction fidelity**: The draft expresses its direction and only its direction; it never borrows from a sibling mock. Trace each token and component decision to the direction's Taste rows in `variant.md`.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/redesign`
- `design/design-mapper` (mock parity, full parity verification, and missing-id feedback)
- `review/design-qa` (mock captures, and the selected variant's captures) and `review/frontier` (accessibility findings on the selected variant)

## Review Expectations

- Every file opens from disk with no console errors and no network requests.
- In a mock: every inventory route is drawn, every inventory component appears, `data-mock="true"` is on the root, and nothing behaves.
- In the selected build: every route, state, component, interaction, and flow in the inventory resolves to a marked element.
- Contrast, focus visibility, and, in the selected build, keyboard reachability and reduced-motion behaviour hold in both themes at every tier.
- `variant.md` fills the doctrine §5 templates concretely, names the direction's differentiators, and — in a mock — states the Mock scope.

## Skip Rule

Never skip a file in the delegation's file set. A component the inventory maps to
`null` still appears in the catalog under the direction's own name. A mock never
skips a route because its screen would be nearly empty.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A `selected-build` is delegated with no `selection` record, or with an id that is not the id `selection.chosen` names | Build nothing and return to `design/redesign`. The selected build is the one implementation this pipeline pays for, and building it for an unchosen direction spends that budget on a draft the user did not pick. |
| The delegation asks for interactions, flows, or a router to be wired into a mock | Refuse and return to `design/redesign`. That work is the selected build, which runs after the selection stage; a mock that behaves is an implementation made before the decision that justifies it. |
| A route's content cannot be drawn plausibly without a live service | Hard-code sample content that matches the shape the inventory records, note it in the Mock scope, and still draw the screen. |
| A route's state cannot be reproduced with mocked data alone in the selected build (depends on a live service) | Mock the service response for that state, mark the mock in `variant.md`, and still render the state. |
| The direction's palette cannot reach the contrast floor for body text | Adjust the token to the nearest passing value, record the deviation in `variant.md`, and report it to `design/redesign`; never ship a failing contrast. |
| Parity self-check reports missing ids | Fix every id before returning; a partial mock or a partial variant is not returned. |
| The assigned mock id collides with a sibling's, or the delegation supplies no id | Stop and ask `design/redesign` for the id before writing a file. `mock_set` requires four unique ids, so a collision breaks the record for the whole set, not just this mock, and the four mock builds run in parallel with no way to notice locally. |
| The inventory revision changed since the delegation | Stop, report the hash drift to `design/redesign`, and rebuild only against the new inventory. |
| The direction, the inventory, or the Taste snapshot digest is missing or malformed in the delegation | Build nothing. Name the missing input and return to `design/redesign`; a draft invented from a partial direction cannot be compared against its siblings, and its Taste traceability rows would cite a digest that does not exist. |
| `design/gatekeeper-design` returns a `REVISE` naming `mock_set` or `selected_variant` | Take the whole owner group in `revise_packet.by_owner` as one batch, fix every finding in a single rebuild, and return the changed files with new sha256 digests so the gate re-judges only `changed_evidence`. |
| Python or `check_parity.py` is unavailable in the host | Walk every id the level scores by hand against the rendered markup, return the draft with the self-check recorded as unavailable and the reason stated, and flag it to `design/redesign`. Never report a coverage number no probe produced; the mapper's run remains the authority. |
| An icon, font, or script is only available from a CDN | Inline a bundled equivalent or a plain fallback; every file must open offline. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with
`Persistence active: yes`:

1. On a `mock-build`, write the five mock files to `redesign/artifacts/mocks/<id>/` at the destination the delegation names. Resolve each one with `python skills/scripts/output_paths.py --run-id {run-id} --phase redesign --kind artifacts --name mocks/<id>/<file>`; `--run-id` is required and the command exits non-zero without it.
2. On a `selected-build`, write the six variant files to `redesign/artifacts/variants/<id>/` the same way, with `--name variants/<id>/<file>`.
3. Put self-check scratch output where `python skills/scripts/output_paths.py --kind test_work --name parity-selfcheck-<id>.json` resolves it, under `.harness-state/test-work/`, never beside the mock or the variant. The scratch record is not gate evidence and is not returned.
4. Return each file path with its sha256 so the phase lead can register it; write nothing else.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the two build orders, the static-draft rules, the prototype architecture, the inventory fields each mode reads, the marker placement rules, the self-check commands at both levels, and the acceptance checklists.
- `references/examples.md` for concrete mock and selected-variant outputs and revision responses.
- `../../design-doctrine.md` §5 for the templates `variant.md` fills and §9 for the mock, selection, and living-prototype requirements.
- `../../scripts/check_parity.py` for the self-check commands, the `--level` contract, and the exit contract.
- `../design-mapper/references/workflow.md` for the authoritative inventory schema and parity-marker contract. It resolves only inside the full catalog; `references/workflow.md` restates the fields and markers this skill reads so the packaged skill never depends on it.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md`
together — the three files this skill owns. Keep generated mocks under the run's
`redesign/artifacts/mocks/` directory and the selected variant under
`redesign/artifacts/variants/`, never inside the skill directory.
