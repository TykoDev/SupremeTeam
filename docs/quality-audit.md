# Quality audit

Open findings only. Fixed findings are in the [changelog](../CHANGELOG.md).
Scores are in [BENCHMARK.md](../BENCHMARK.md).

## Major

| Id | Area | Finding |
|---|---|---|
| N-1 | Harness | Archive extract (`--strip-components`, `--transform`, `-P`, symlink) reaches guard records |
| N-2 | Harness | `cp -rT backup .` copies over the root unread |
| N-3 | Harness | `git clean` pathspecs `:/`, `'*'`, `-e` patterns slip through |
| N-5 | Harness | Root `unzip` outside a run can overwrite hook files |
| G-3 | Gates | Weakening `gates.yaml` passes every validator |
| P-1 | Pipelines | Repeat deploy cannot pass `deploy-readiness` |
| P-2 | Pipelines | `security_seed` refuses its prescribed applicability record |
| O-3 | Orchestrators | No stage produces `taste_snapshot` for a design run |
| O-4 | Protocol | State machine: unreachable Taste state, no investigation COMPLETE |
| D-2 | Protocol | Run phase states are not mapped to protocol states |

## Minor

| Id | Area | Finding |
|---|---|---|
| H-7 | Harness | Read-only runs allow destructive git ref commands |
| H-9 | Harness | Read-only interpreter access to frozen paths is denied |
| H-10 | Harness | Bash `apply_patch` into a frozen path is allowed |
| N-6 | Harness | Root `rsync --delete` exclude edge cases unread |
| N-8 | Harness | Unknown extractors and runtime-built destinations unseen |
| N-9 | Harness | `cd sub && git clean` falsely denied as root-aimed |
| G-7 | Gates | Typed-record `inputs` follow symlinks out of project |
| G-8 | Gates | Manifest with BOM is misparsed |
| G-9 | Gates | `candidate_ids` not cross-checked against the diff |
| G-10 | Gates | Record checks test shape, not nested values |
| G-11 | Gates | `human_go_required` record is untyped |
| G-13 | Gates | `unchecked_fields` overstates; `cycle_cap` never read |
| P-3 | Pipelines | `qa-review` requires keys only conditional stages produce |
| P-4 | Pipelines | Validators miss four pipeline mutations |
| P-5 | Pipelines | `requires`/`produces` declared only in `design` |
| P-6 | Pipelines | Release and investigation stages precede their guard |
| O-6 | Orchestrators | State names split between runs and protocol |
| O-8 | Orchestrators | Delegation names the Agent tool; none grant it |
| O-9 | Orchestrators | Commander grills the user from a sub-agent |
| O-13 | Orchestrators | `skills_engaged` stored as a JSON string |
| O-14 | Orchestrators | Startup `status` needs a run id first |
| O-15 | Orchestrators | Shipped `mcp-tools.md` timestamp forces intake pause |
| O-16 | Orchestrators | Revision-cap wording and counter sharing unclear |
| O-17 | Orchestrators | Copilot precedence drops Tier 0 |
| D-4 | Doctrine | Loop guard accepts a stale pinned lock |
| D-5 | Doctrine | `_probe-*.tmp` has no ownership class |
| D-6 | Doctrine | Judgement labels deny comparators that exist |
| D-9 | Doctrine | A skill-reviewer duty has no backing |
| D-14 | Doctrine | Delivery example uses Tier 1 for a gated edit |
| D-16 | Doctrine | Taste unreadable-profile fallback contradicts its rule |
| D-17 | Doctrine | `_LAYER_CITATION` accepts any `§1`–`§5` |
| D-19 | Doctrine | Info: dual-verdict, clause-3, TTL, `/exit-admiral` |

## Document deductions

From the rubric re-score; each cites file and line.

<details>
<summary>123 deductions</summary>

| Document | Deduction |
|---|---|
| `admiral` | Must-defer sub-orchestrator list omits review/cso, contradicting routing doctrine |
| `admiral` | 'Only standalone tools' list omits audit-improve |
| `admiral` | Lost pointer with stale/released lock classifies stale/inactive, not orphaned |
| `admiral` | Prescribes recover for released lock; save_run refuses it |
| `admiral` | Says record degraded path in _state.md without naming sole writer |
| `admiral` | Claims Delegation Surface lists taste/skill-maker boundaries; it does not |
| `build/bob-the-builder` | Claims byte-for-byte hashing; text digests fold line endings |
| `build/cross-check-build-confirm` | No-code decision 'proven by waiver' though only security_evidence is waivable |
| `build/debugger` | Repairs path and leaves fix in diff; ownership forbids writing implementation |
| `build/debugger` | Claims byte-for-byte hashing; text digests fold line endings |
| `build/health-check` | Claims byte-for-byte hashing; text digests fold line endings |
| `build/health-check` | Library with no start command blocks; owner delegates consumption-path smoke here |
| `build/security-builder` | Seed stage conditional, key required unwaivable; no-boundary case unhandled |
| `build/test-builder` | Claims byte-for-byte hashing; text digests fold line endings |
| `build/test-builder` | Outputs name no *test*.md deliverable; build shape check requires one |
| `careful` | Claims hook-file rule denies on malformed record; allowed without run |
| `contracts/delivery-template.md` | Example records Tier 1 (read-only) for a gated edit |
| `contracts/delivery-template.md` | Hard-coded '10 of 91 ... 81 skipped' stale; actual 10/92/82 |
| `contracts/evidence-standards.md` | Claims evidence containment machine-checked; record inputs follow symlinks outside project |
| `contracts/responsibility-matrix.md` | audit-improve works 'under owning lead'; routing makes it standalone |
| `contracts/responsibility-matrix.md` | RELEASE triggered by gate approval; land-and-deploy stage precedes deploy-readiness |
| `contracts/responsibility-matrix.md` | Gate coverage and Owner column mirrors remain uncompared |
| `contracts/universal-frameworks.md` | Says no test names this file; test_docs_inventory opens it |
| `contracts/universal-frameworks.md` | States/edges called judgement; GuardedTransitionTests parses state table edges |
| `contracts/universal-frameworks.md` | Workflow row omits Submitter-column comparator GateProseTests |
| `contracts/workflow-protocol.md` | TASTE_* states unreachable: TASTE_ACTIVE entered only from TASTE_GATE_REVISE |
| `contracts/workflow-protocol.md` | Investigation boundary has no COMPLETE edge for diagnose-only runs |
| `contracts/workflow-protocol.md` | GATE lacks BUILD/REVIEW edges investigation routing needs |
| `contracts/workflow-protocol.md` | Run phase_state values never mapped to protocol states (D-2) |
| `contracts/workflow-protocol.md` | Fix routed to BUILD needs approved_design_revision without fallback |
| `contracts/workflow-protocol.md` | Cycle cap counter sharing between phase and cross-stage unstated |
| `design-doctrine.md` | taste_snapshot called 'correctly shaped'; it has no typed record |
| `design-doctrine.md` | Commander asks Admiral/Taste for snapshot; no stage produces it (O-3) |
| `design/architect` | design-directions.md saved under artifacts/; redesign owner says reports/ |
| `design/commander` | Agent manifest claims per-phase gating; pipeline has one phase-gate |
| `design/design-mapper` | Parity --out redesign/evidence/... writes outside run directory |
| `design/engineer` | REVISE row assumes engineer owner group; engineer owns no key |
| `design/gatekeeper-design` | Research pattern misses researcher's requirements-brief.md; shape check FAILs (reproduced) |
| `design/gatekeeper-design` | *ui*.md matches requirements-brief.md: false UI-handoff PASS (reproduced) |
| `design/gatekeeper-design` | Claims global fallback exists for mock_rendering; spec has none |
| `design/prototyper` | Says any of five/six unhashed files breaks record; gate checks four |
| `design/prototyper` | Self-check example mixes short input paths with run-path out; exits 2 |
| `design/redesign` | Unexecutable parity described as status unavailable; checker writes no record |
| `design/researcher` | Prescribed requirements-brief.md fails gate shape pattern *research*.md (reproduced) |
| `design/researcher` | Says commander runs intake; pipeline assigns intake-grilling to admiral |
| `design/researcher` | Calls brief architect's only required input; architecture also requires decisions |
| `design/researcher` | REVISE row assumes researcher owner group; researcher owns no key |
| `execution-contract.md` | Clause 3 'resolve Major before a gate' contradicts sanctioned Major deferral |
| `gates.yaml` | Weakened spec passes validate_manifests and every suite (G-3) |
| `gates.yaml` | security_seed refuses prescribed applicability record; 'n/a' passes (P-2) |
| `gates.yaml` | deploy_config/rollback_plan no fallback; repeat deploy cannot pass (P-1) |
| `gates.yaml` | human_go_required untyped; any value passes (G-11) |
| `gates.yaml` | unchecked_fields says cycle_cap read per boundary; check.py never reads |
| `grill-me-doctrine.md` | Binds commander to grill user; delegated commander has no user channel |
| `harness-doctrine.md` | 'Names its lifecycle layer' machine-checked; any §1-§5 citation passes |
| `harness-doctrine.md` | skill-reviewer said to reject per doctrine; skill-reviewer never cites it |
| `harness-doctrine.md` | Layer 3 boundaries called machine-checked despite reproduced freeze bypasses |
| `harness/gatekeeper` | Gate suites pass a weakened gates.yaml (G-3) |
| `harness/gatekeeper` | Typed-record inputs resolve through symlinks out of project |
| `harness/gatekeeper` | BOM manifest misparsed: reports missing artifact hashes and evidence |
| `harness/gatekeeper` | check.py never reads revise_policy.cycle_cap that spec says is read |
| `harness/hooks` | Archive member into records claimed refused; --strip-components extract allowed |
| `harness/hooks` | Contents copy over root claimed refused; cp -rT allowed |
| `harness/hooks` | Root git clean claimed refused; ':/' pathspec allowed |
| `harness/hooks` | Bash apply_patch into frozen path and core record allowed |
| `harness/hooks` | Read-only run allows git branch -D, tag -d, update-ref -d |
| `harness/hooks` | Read-only inline interpreter access to frozen path is denied |
| `investigate` | Example captures reproduction through design-qa, absent from investigation pipeline |
| `mcp-tools.md` | No enforcement section; TTL 'source of truth' read by no code |
| `mcp-tools.md` | Admiral rewrites skill-set file with no declared writer |
| `mcp-tools.md` | 'Installer never replaces it' contradicts replacing unedited prior-release copies |
| `mcp-tools.md` | Epoch placeholder forces intake pause on every fresh install |
| `mcp-tools.md` | 'Workspace copy' undefined; mirror path Claude-specific only |
| `mcp-tools.md` | Declared browser source of truth while both tables ship empty |
| `mcp-tools.md` | No failure-paths section unlike every sibling contract |
| `ownership.yaml` | taste-snapshot owned by taste before design-to-build; nothing produces it |
| `performance-doctrine.md` | evidence_types list omits verdict, stack_lock, revision_ref, variant_set, selection |
| `performance-doctrine.md` | Self-declared reachability gap: no SKILL.md links this doctrine |
| `pipelines.yaml` | setup only on first deployment; repeat release unsatisfiable (P-1) |
| `pipelines.yaml` | qa-review requires keys only conditional stages produce (P-3) |
| `pipelines.yaml` | 'step unique' declared; duplicate step id passes all validators (P-4) |
| `pipelines.yaml` | requires/produces declared only in design pipeline (P-5) |
| `pipelines.yaml` | land-and-deploy stage precedes the GATE->RELEASE boundary closing it (P-6) |
| `pipelines.yaml` | No design stage produces required taste_snapshot (O-3) |
| `qa` | Pipeline signal omits session_pin; any run lock flips to pipeline mode |
| `qa-only` | Claims routing-doctrine classes qa-only standalone; doctrine lists it dual-mode |
| `qa-only` | Pipeline signal omits session_pin requirement for the run lock |
| `qa-only` | Recovery reads owner from status; status prints run ids only (reproduced) |
| `review/bug-review` | Claims fixed filename stops rival bug files; reproduced: rival takes slot |
| `review/code-chief` | Example path report_bug-review.md contradicts lens-mandated deliverable_bug-review.md |
| `review/cso` | Names verdict_security-review.json; gatekeeper-admiral writes .cross-stage.json there |
| `review/cso` | security-review-package.md fills lens_security, never lens_cso; reproduced |
| `review/design-qa` | Packet Findings line omits status the findings record requires |
| `review/design-qa` | Example uses status 'unresolved', not an accepted finding status |
| `review/gatekeeper-code` | Claims rendered_verification is no_fallback at redesign-review; spec says otherwise |
| `review/gatekeeper-code` | Slot-attribution warning covers lens_code only; CSO package fills lens_security |
| `review/mr-robot` | Packet Findings line has no status column; check.py requires one |
| `review/mr-robot` | Example 5 continues a code-chief penetration-review pass as cso security-review REVISE |
| `review/quality-review` | Claims fixed filename stops rival quality files; matcher does not |
| `review/quality-review` | Cites evidence_types.findings; the rule lives in evidence_type_rules.findings |
| `review/security-review` | Packet Findings line omits status that line 132 says is required |
| `review/security-review` | Cross-refs miss: evidence_types.findings and nonexistent 'Scan Evidence' section |
| `routing-doctrine.md` | has_active_run said 'fresh'; also true for orphaned and access_denied |
| `routing-doctrine.md` | /exit-admiral release command parsed or registered nowhere |
| `routing-doctrine.md` | Loop guard accepts any pinned lock; stale locks must not pin |
| `save-ownership.yaml` | Prescribed _probe-{run}.tmp path matches no class; rule calls it gap |
| `save-protocol.md` | Prescribes probe path no save-ownership class covers |
| `save-protocol.md` | Shell writes to core files denied; Bash apply_patch to _state.md allowed |
| `setup-browser-cookies` | Calls repo Windows-primary; runtime manifest declares three equal platforms |
| `ship` | Example 2 carries forward prior-run artifacts the gate rejects |
| `skill-maker` | Example manifest doubles skill-creation/ path; check.py fails it (reproduced) |
| `skill-maker` | PACKAGE_ACTIVE owner skill-creator; pipeline package stage owner is skill-maker |
| `skill-maker/skill-creator` | run_loop example skill-path wrong from skill-creator cwd; fails (reproduced) |
| `skill-maker/skill-reviewer` | Allows cold isolated scoring; doctrine says reached only via skill-maker |
| `skill-maker/skill-reviewer` | Rubric TOC example deducts -2; its own ladder says -1 |
| `taste` | `set` examples store bare strings, which doctrine calls a violation |
| `taste-doctrine.md` | Unavailable-Taste fallback contradicts 'only for project without profile' rule |
| `taste-doctrine.md` | Says skipping existing profile is blocked; gate accepts fallback regardless |
| `taste-doctrine.md` | Snapshot consumption declared; taste pipeline has no snapshot stage |
| `taste/taste-review` | Description says review happens before saving; persistence stage precedes review |
| `taste/taste-review` | Body says 're-read before persisted' yet checks committed persistence_result |
| `manifests` | audit-improve grouped as specialist though routed as standalone tool |
| `unfreeze` | Legacy bare-glob recovery deadlocks: freeze refuses, release refuses (reproduced) |

</details>

## Limits

- Hooks fail open: they prevent accidents, not attacks.
- Hashed evidence proves byte identity, not truth.
