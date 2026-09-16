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
4. The `redesign-review` override
5. Reading a key that is neither artifact-backed nor typed

## 1. Artifact-backed keys per boundary

Each key below must resolve to a path that appears in the package's
`artifact_hashes` map (`../../gates.yaml` `artifact_evidence`). A key whose value
exactly equals one of its sanctioned fallback values is exempt; every other bare
string fails the artifact-backing check.

| Boundary | Artifact-backed keys |
| --- | --- |
| `design-to-build` | `decisions` `architecture` `plan` `taste_snapshot` |
| `redesign-review` | `design_inventory` `taste_grilling` `taste_snapshot` `design_directions` `variant_set` `parity_evidence` `rendered_verification` |
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
| `variant_set` | `variant_set` | exactly `evidence_type_params.variant_set.required_count` variants, unique ids, and `spec` / `tokens` / `components` / `app` hashed per variant |
| Taste records | `preference_diff` `confirmation` `conflict_analysis` `persistence_result` `effective_profile` `consumer_handoff` | the field sets in `evidence_type_rules`; `confirmation.candidate_ids` must equal the exact changed id set |

## 3. Sanctioned waivers, verbatim

A waiver is a typed applicability record — `{applicable: false, reason, scope,
decided_by}` — whose reason is one of the strings below. Any other string, and
any waiver on a key not listed here, fails mechanically.

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

`confirmation` is deliberately absent from every list. Inferred preferences and
any global write, promotion, reset, or revocation require the explicit record, so
a `confirmation` waiver is rejected as *evidence not waivable* rather than as a
bad reason.

## 4. The `redesign-review` override

`../../gates.yaml` lists `rendered_verification` under `redesign-review`'s
`no_fallback`. At that boundary the key accepts neither the sanctioned string in
§3 nor an applicability record, even though the global fallback exists
everywhere else.

The reasoning is substantive rather than procedural: a redesign changes a visible
surface by definition, so "no visible surface changed" cannot be a true statement
about a redesign package. Treat an attempted waiver there as a `REVISE` routed to
`design-qa`, and ask for hashed captures across the required breakpoints and
themes, bound by `inputs` to the rendered variant.

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
