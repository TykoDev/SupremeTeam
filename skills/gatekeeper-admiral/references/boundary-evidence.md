# Boundary Evidence Reference

Read this when a submission is at hand and the question is *what a specific key
must be* — a hashed artifact or a claim, which typed record shape, and whether a
waiver is admissible. `../SKILL.md` carries the required-evidence table and the
three rules; this file carries the per-boundary detail behind them.
`../../gates.yaml` remains the authority: where this file and the spec disagree,
the spec wins and this file is the defect.

## Contents

1. Artifact-backed keys per boundary
2. Typed-record roster
3. Sanctioned waivers, verbatim
4. The `redesign-review` overrides
5. Reading a key that is neither artifact-backed nor typed

## 1. Artifact-backed keys per boundary

Each key below must resolve to a path that appears in the package's
`artifact_hashes` map (`../../gates.yaml` `artifact_evidence`). A key whose value
exactly equals one of its sanctioned fallback values is exempt; every other bare
string fails the artifact-backing check.

| Boundary | Artifact-backed keys |
| --- | --- |
| `design-to-build` | `decisions` `architecture` `plan` `taste_snapshot` |
| `redesign-review` | `design_inventory` `taste_grilling` `taste_snapshot` `design_directions` `mock_set` `mock_parity` `mock_rendering` `selection` `selected_variant` `parity_evidence` `rendered_verification` |
| `build-to-review` | `tests` `runtime` |
| `review-to-delivery` | `executed_probes` `rendered_verification` |
| `security-review` | `threat_model` `denial_path_evidence` |
| `investigation-review` | `reproduction` `evidence_chain` |
| `qa-review` | `test_matrix` `executed_probes` |
| `taste-review` | `preference_diff` `confirmation` `conflict_analysis` `persistence_result` `effective_profile` `taste_review_record` |
| `skill-maker-to-delivery` | `link_report` `validation_report` |
| `deploy-readiness` | `deploy_config` `verification_plan` `rollback_plan` |

At manifest schema 2 the rule widens: *every* path-shaped string in an evidence
value must be a correctly hashed artifact, so a free-text value that happens to
mention a file path is checked as though it named one.

## 2. Typed-record roster

`../../gates.yaml` `evidence_types` assigns a record shape to the keys below; the
full shape rules live in that file's `evidence_type_rules`. A key absent from
this table is untyped — required and non-falsy, nothing more.

| Record type | Keys carrying it | What the validator enforces |
| --- | --- | --- |
| `probe` | `tests` `runtime` `executed_probes` `reproduction` `evidence_chain` `test_matrix` `denial_path_evidence` `parity_evidence` | hashed artifacts plus `result.status: pass`; the executed log is the artifact, a count is not |
| `render` | `rendered_verification` | hashed captures, breakpoints, themes, and `inputs` bound by sha256 to the rendered source |
| `scan` | `vulnerability_scan` | tool, command, exit_code, observed_at, bound `inputs`, and a `pass` status — `unavailable` or `error` is a data gap |
| `findings` | `findings` `security_evidence` `defects` `accessibility_evidence` | `{items: [{id, severity, status, …}]}` under the shared severity model and the finding policy |
| `verdict` | `review_verdict` | APPROVED, or REVISE/ESCALATE with a challenge record naming `by` and `reason` |
| `stack_lock` | `stack_lock` | `{slug, versions, overlay_sha256}` validated against `../../tech-stacks/registry.yaml` |
| `revision_ref` | `approved_design_revision` `approved_delivery` | a non-empty approved upstream revision identifier |
| `variant_set` | `mock_set` `selected_variant` | exactly `evidence_type_params.<key>.required_count` entries (4 mocks, 1 selected variant) with unique ids, and the key's `file_fields` (`spec` / `tokens` / `components` / `mock` for a mock, `spec` / `tokens` / `components` / `app` for the built variant) hashed per entry |
| `selection` | `selection` | `{decision, chosen, recommended, decided_by, decided_at, basis}` with `decision` in `variant` / `merge` / `deferred`; `chosen` names a `mock_set` id only under `variant`, and `selected_variant.variants[0].id` must equal it; under `merge` or `deferred` the four build-dependent keys carry the matching sanctioned applicability record |
| Taste records | `preference_diff` `confirmation` `conflict_analysis` `persistence_result` `effective_profile` `consumer_handoff` | the field sets in `evidence_type_rules`; `confirmation.candidate_ids` must equal the exact changed id set |

## 3. Sanctioned waivers, verbatim

A waiver is a typed applicability record — `{applicable: false, reason, scope,
decided_by}` — whose reason should be one of the strings below.

**Know how much of that the machine enforces**, because it is less than the
sentence above suggests. `check.py` mechanically rejects two things: a waiver on
a key this boundary does not list as waivable (*evidence not waivable*), and an
applicability record missing any of `reason`, `scope`, `decided_by`
(`check.py:343-355`). It does **not** compare the reason *text* against this
table for an ordinary waivable key — any non-empty reason passes. The wording is
compared in exactly two places: for a bare fallback string, which schema 2
rejects on form anyway, and for the four selection-dependent keys at
`redesign-review`, where `check_selection_dependencies` requires the reason to
match the one the `selection.decision` implies, exactly.

So for most keys the sanctioned wording is a **judgement** standard, enforced by
workflow step 4 and by this gate returning `REVISE`, not by the checker. A green
self-check does not mean the reasons were read. Read them.

| Key | The only sanctioned reason |
| --- | --- |
| `security_evidence` | no trust-boundary change - security-builder not engaged |
| `stack_lock` | no new runtime or framework - existing stack unchanged |
| `ui_evidence` | no user-facing surface - design system not engaged |
| `taste_snapshot` | no saved Taste profile available |
| `rendered_verification` | no visible surface changed - rendered verification not applicable |
| `denial_path_evidence` | static analysis only - active probes not authorized |
| `vulnerability_scan` | no dependency or source scan surface - scanner not engaged |
| `fixes_applied` | report-only run - no fixes applied |
| `team_manifest` | single skill - no team manifest produced |

`taste-review` declares three waivers of its own, admissible only at that
boundary: `before_revision` ("new store - no prior revision"), `consumer_handoff`
("preference management only - no downstream consumer"), and
`residual_uncertainty` ("none observed").

The table above is the *global* map. Two boundaries depart from it, and the
boundary's own entry in `../../gates.yaml` always wins: `redesign-review` removes
`mock_rendering` from waivability entirely and **replaces** the list for
`rendered_verification` and three sibling keys with two reasons of its own (§4),
so the global `rendered_verification` reason is not available there; and
`taste-review` adds the three reasons named above for keys with no global entry.
Check the boundary before checking this table.

`confirmation` is deliberately absent from every list. Inferred preferences and
any global write, promotion, reset, or revocation require the explicit record, so
a `confirmation` waiver is rejected as *evidence not waivable* rather than as a
bad reason.

## 4. The `redesign-review` overrides

`redesign-review` overrides the global fallback map in both directions. Read the
boundary's own `no_fallback` and `fallback_values` off `../../gates.yaml` before
judging any waiver there.

**Narrowed — `mock_rendering`.** The boundary lists it under `no_fallback`, so it
accepts neither a sanctioned string nor an applicability record, even though
`render`-typed keys are waivable elsewhere. The reasoning is substantive: the
four directions are mocks, and a mock that was never rendered is not evidence of
anything. Treat an attempted waiver as a `REVISE` routed to `design-qa`, the
key's owner, and ask for hashed captures across the required breakpoints and
themes, bound by `inputs` to each mock.

**Replaced — `rendered_verification` and its three build-dependent siblings.** At
this boundary `rendered_verification`, `selected_variant`, `parity_evidence`, and
`accessibility_evidence` each carry a boundary-level `fallback_values` list, and
that list is **exhaustive**: a boundary entry shadows the global entry for the
same key instead of extending it. `../../harness/gatekeeper/check.py:361-362`
resolves `boundary.fallback_values[key] or spec.fallback_values[key]` — the
boundary list short-circuits, so the two reasons below are the only sanctioned
wordings here, both quoted verbatim in `../../gates.yaml`:

| Reason | When it is true |
| --- | --- |
| `selection deferred - no variant built` | `selection.decision` is `deferred` — the run stopped at the mock set |
| `merge brief recorded - implemented as a fifth direction in the design pipeline` | `selection.decision` is `merge` — the chosen direction is a synthesis handed onward, not a built variant |

The consequence is easy to get backwards, so state it plainly: the global
`rendered_verification` reason — `no visible surface changed - rendered
verification not applicable` — is **not sanctioned at `redesign-review`**, even
though it is sanctioned at every other boundary that requires the key. A package
asserting it here is a `REVISE` for an unsanctioned waiver reason, not a granted
waiver. The other three keys have no global entry at all, so the same two reasons
are the whole list for them by construction.

Accept either only when `selection` actually carries the matching `decision`, and
only as a typed applicability record. A `variant` decision makes all four keys
mandatory: there is a built variant, so it can be rendered, measured, and
compared. Rejecting a correctly-recorded deferred or merge record is as much a
failure as granting a waiver the boundary refuses — it routes a `REVISE` to
`design-qa` for evidence no one was ever required to produce.

## 5. Reading a key that is neither artifact-backed nor typed

Untyped keys — `interfaces`, `acceptance`, `security_seed`, `ui_evidence`,
`implementation`, `traceability`, `residual_risk`, `revision_lineage`, `scope`,
`intent`, `mechanism`, `fix_path`, `recommendation`, `skills`, `human_go_required`,
and the rest — are checked only for presence and non-falsiness. The validator
cannot tell an adequate `acceptance` statement from an empty one that happens to
contain words.

That gap is the judgment half of this gate. For each untyped key, ask whether the
next consumer could act on the value as written, and treat a value that only
restates the key name as absent.

## Cross-references

- `../../gates.yaml` — the authority for everything on this page.
- `../SKILL.md` — the required-evidence table, the three rules, and owner routing.
- `../references/workflow.md` — the order these checks run in.
- `../references/examples.md` — worked submissions applying them.
