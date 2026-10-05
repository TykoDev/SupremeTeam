# Supreme Team quality audit and benchmark — 2026-10-01, round 2

## Executive verdict

**Overall: 76/100. The documents are strong, but the executable paths are weaker
than the earlier scores claim.** Every suite, validator and lint check is green
(2,284 tests on Python 3.13). The 53 skills score a mean of **97.8** on the
catalog's own 10-dimension rubric. Those numbers measure what the catalog already
tests. This round went further: it ran the documented procedures literally, sent
hostile input to the guard, sent forged packages to the gates, and mutated the
specs. That surfaced two Critical and fifteen Major defects that no current test
catches. The four lowest-scoring surfaces are exactly the ones that were executed
rather than read.

| Surface | Score | Previous (round 1, today) | What moved it |
|---|---:|---:|---|
| Skills (rubric, 53) | **97.8** (min 94) | 99.4 (BENCHMARK, 09-18) | Of the 26 deductions in the 09-18 ledger, 19 are still present; new citations found |
| Doctrines, protocols and contracts (15) | **89.7** (min 80) | 88 | Strong cross-reference hygiene; the state machine has drifted from the runs |
| Pipelines | **71.8** | 93 | Two boundaries cannot be satisfied on legitimate paths; requires/produces declared in 1 of 10 pipelines |
| Review gates | **77.3** | 94 | A Critical finding can be approved through a depth-bounded layout check; mutations that weaken the spec pass |
| Harness (hooks and guard) | **65.2** | 85 | One allowed `cp` erases the guard record; `$PWD/` targets get past freeze |
| Orchestrators (procedural) | **54.7** | 89 | Every phase lead's documented checkpoint command is refused by `save_run.py` |
| **Overall** (equal weight) | **76/100** | 90 | |

Round 1 scored surfaces by reading them. This round scored them by running them.
Both numbers are model judgements against a stated method, not machine output.
The cited, reproduced findings below are the durable output. The totals are a
summary of them.

## Scope and method

- **Benchmark.** All seven suites, the three validators, and `ruff==0.16.9`, the
  version CI pins. They ran sequentially so the load-sensitive timing assertions
  were not skewed. The run used Python 3.13.14 with PyYAML 6.0.1, plus the CI
  "without PyYAML" leg (a bare venv) for the validation, scripts and gates suites.
  Hook latency was measured as a host invokes it: a cold `pre_tool_use.py`
  process per call.
- **Seven independent auditors** worked in parallel on a read-only checkout, each
  with scratch sandboxes:
  - harness: adversarial guard probing, about 230 probes;
  - gates and pipelines: forged packages and spec mutation;
  - orchestrators: a tabletop run of three requests, executing `save_run.py`
    exactly as instructed;
  - doctrines: claim extraction plus automated link, path, flag and symbol
    resolution;
  - three skill groups, scored on the rubric in
    `skills/skill-maker/skill-reviewer/references/scoring-rubric.md`.
- **Verification.** A finding counts only if it is cited on both sides (the claim
  and its source of truth). Each is marked CONFIRMED when reproduced, or PLAUSIBLE
  when only reasoned from the code. The lead auditor re-reproduced the headline
  findings independently (O-1, H-1, H-2, H-3, H-5, G-1, D-1).
- **Surface scores.** Each is the mean of six dimensions per surface (listed in
  each section). Skills use the rubric mean. The overall score is the equal-weight
  mean of the six surfaces.

## Benchmark results

| Suite / check | Result | Tests | Wall time |
|---|---|---:|---:|
| hooks | OK (2 skipped) | 928 | 151.0 s |
| gates | OK (1 skipped) | 255 | 21.8 s |
| validation | OK (1 skipped) | 257 | 10.0 s |
| scripts | OK | 386 | 20.4 s |
| taste | OK | 213 | 6.2 s |
| installers | OK | 85 | 48.4 s |
| skill-creator | OK | 160 | 2.2 s |
| validation / scripts / gates without PyYAML | OK (9 / 3 / 1 skipped) | 254 / 386 / 255 | 9.4 / 20.3 / 21.8 s |
| `check_runtime.py` / `validate_manifests.py` / `package_check.py` | pass | — | 0.08 / 0.08 / 0.12 s |
| `ruff check .` (0.16.9) | clean | — | 0.05 s |

- **Totals:** 2,284 tests with PyYAML, all passing. The full sequential run took
  about 5 minutes.
- **Hook latency** (cold process, n=36 × 3 projects):

  | Hook | Median | p95 |
  |---|---:|---:|
  | `pre_tool_use.py` | 76–81 ms | 98–103 ms |
  | `post_tool_use.py` | 84 ms | — |
  | `user_prompt_submit.py` | 64 ms | — |

  A bare interpreter starts in 15–20 ms. Scanning cost is linear: a 57–115 KB
  command scans in ≤140 ms.
- **Floor behaviour:**
  - Under Python 3.11 (this container's default `python3`), `check_runtime.py`
    correctly exits 1 with `Ready: no`.
  - The gatekeeper wrappers do not report the floor. They crash with
    `AttributeError: 'PosixPath' object has no attribute 'is_junction'`
    (`_gatecheck.py:437`) instead of a floor message (G-12).
  - 14 readiness tests fail rather than skip on 3.11.
- **Static profile:**

  | Measure | Value |
  |---|---|
  | `SKILL.md` length | mean 197 lines, median 171, max 468 |
  | Description length | mean 516 chars, max 600, none above the 1,024 host limit |
  | `allowed-tools` declared | every skill |
  | Skills with no `references/` | `audit-improve` only |
  | Code size | 22.6k lines of non-test Python against 33.5k lines of tests in 68 modules |

- **Reference hygiene (doctrine auditor, automated), 0 broken in every class:**

  | Reference class | Checked |
  |---|---:|
  | Markdown links and anchors | 254 |
  | Backticked paths | 383 |
  | CLI flags | 97 |
  | Test, class and constant names | 283 |
  | Quoted failure strings | ~40 |

**Reading the benchmark.** The green suite and zero broken references are real
strengths. But the suite catches none of H-1 to H-7, G-1, G-2, P-1 or P-2, or
the 13-document checkpoint contradiction (O-1). Test count is not test adequacy,
and the gap sits in the safety-critical paths.

## Critical findings

**O-1 — every phase lead's checkpoint command is refused (CONFIRMED, reproduced
independently).**
- **The instructions.** Thirteen documents in twelve skills tell the agent to
  run `save_run.py checkpoint --owner <self>`:
  - commander, build-management, code-chief, cso, redesign (×2), investigate,
    bob-the-builder, test-builder, health-check, debugger and
    cross-check-build-confirm, each in its `references/workflow.md`
    (cso: `gate-submission.md:91`);
  - session-memory's `references/examples.md:43`.
- **The refusal.** `admiral/references/workflow.md:40` states that
  `--owner <lead>` "is refused every time", because admiral holds the run lock.
  `save_run.py:339-343` (`require_owner`) enforces it.
- **Repro.** `save_run.py create --run-id r1 --owner admiral …` followed by
  `checkpoint --run-id r1 --owner commander --expect-revision 1 --set
  phase_state=DESIGN_ACTIVE` returns `refused: lock is owned by 'admiral', not
  'commander'`, rc=1.
- **Effect.** session-memory forbids working around a refusal, so a literal agent
  stalls at the first checkpoint of every pipeline that admiral delegates.

**H-1 — copying into a record's directory erases the guard record (CONFIRMED,
reproduced independently).**
- **The rule.** Rule C protects `.harness-state/guard-state.json` against `mv`,
  `>`, `rm` and similar writes. It treats the directory itself as a record target
  only for verbs in `_REMOVE_VIA` (`guard_hook.py:337` and `:803`), and that set
  has no `cp`.
- **Repro** (freeze `src/payments/**` recorded):
  1. `cp /tmp/x/guard-state.json .harness-state/` is allowed.
  2. After it runs, `guard_state.py status` shows `frozen: -`.
  3. `echo x > src/payments/a.py` is then allowed.
- **Inside a read-only run** the same lift works in a single command.
- **The same bypass** works through `install`, `rsync`, `cp -t`, `ln -sf`,
  `tar -C`, `cd .harness-state && cp … .`, and against `_state.md` and
  `.claude/settings*.json` (Rule F).
- **The claim it breaks.** README:165-166 names this exact self-lift as what
  Rule C exists to stop.

## Major findings

### Harness

- **H-2 (CONFIRMED, reproduced).** `$PWD/…` and `$CLAUDE_PROJECT_DIR/…` targets
  get past freeze, block and Rule F.
  - Allowed: `echo x > "$PWD/src/payments/a.py"`, `rm -rf "$PWD"`, and a write of
    `{"disableAllHooks":true}` to `$CLAUDE_PROJECT_DIR/.claude/settings.local.json`.
  - Inconsistently, `${PWD}/…` is denied.
  - Cause: `_cmdscan._lookup` (`_cmdscan.py:606`) resolves only `HOME`.
- **H-3 (CONFIRMED, partly reproduced).** Tree writers aimed above a boundary are
  not treated as tree writes.
  - Under freeze, allowed: `find src -exec sed -i … {} +`,
    `rsync -a --delete /tmp/empty/ src/`, `tar -xf a.tar -C src`.
  - With no boundary at all (Rule C), allowed: `git clean -fdx skillset-saves`
    and `rsync --delete … .harness-state/`.
  - This contradicts README:156 and :166.
- **H-4 (CONFIRMED by auditor).** Appending `raise SystemExit(0)` to
  `skills/scripts/save_taxonomy.py` is allowed, and it silently disables the
  guard with no fault recorded.
  - Rule F protects only `HOOK_DIR/**` (`guard_hook.py:840-847`).
  - `_state.py:59-62` imports the module.
  - `pre_tool_use.py:48` catches only `Exception`, so `SystemExit` escapes.
- **H-5 (CONFIRMED, reproduced).** Rule A does not see destructive text inside a
  pipe or a launcher.
  - Allowed: `echo 'rm -rf /' | sh`, `watch 'rm -rf /'`,
    `perl -e 'system("rm -rf /")'`.
  - The README states the opposite twice: README:150, and its "What the guard
    cannot see" list.

### Review gates

- **G-1 (CONFIRMED, code re-read).** `_run_layout_dir` walks only four levels
  (`check.py:309`). A schema-1 manifest at
  `skillset-saves/runs/R1/review/d0/d1/d2/manifest.json` is therefore treated as a
  detached package. A package carrying an **open Critical finding** passes
  `review-to-delivery` (rc=0). One level higher, the same package is refused.
- **G-2 (CONFIRMED).** A UTF-8 BOM before `---` (`_gatecheck.py:270`), or a quoted
  `'revision'` key, defeats `MIXED_REVISIONS` and `MIXED_SUBMISSION_IDS`, so
  mixed-revision packages report `REVISION_COHERENT PASS`. The related
  manifest-side BOM misparse is G-8.
- **G-3 (CONFIRMED).** Edits that weaken the gate spec pass every validator and
  every related test:
  - adding `fallback_values.findings: ["no findings"]`;
  - making `executed_probes` waivable;
  - dropping `tests` from `build-to-review` `artifact_evidence`.

### Pipelines

- **P-1 (CONFIRMED).** A repeat deployment cannot pass `deploy-readiness`.
  - `setup` runs only `when: first deployment` (`pipelines.yaml:456`), but
    `deploy_config` and `rollback_plan` are artifact-backed with no fallback.
  - The "carry forward" path that `setup-deploy/SKILL.md:48` prescribes is
    refused as "artifact references another run".
- **P-2 (CONFIRMED).** For design `security_seed` (a conditional stage), the gate
  refuses the typed applicability record that `failure_paths.when_condition_ambiguous`
  prescribes ("evidence not waivable"), while the bare prose `"n/a"` passes.

### Orchestrators

- **O-2 (CONFIRMED).** All three admiral adapters tell the agent to write
  run-state, lock and audit files directly (`adapters/claude.md:48`,
  `copilot.md:76-77`, `codex.md:13`). Rule C denies those writes.
- **O-3 (CONFIRMED).** Nothing produces `taste_snapshot` for an ordinary design
  run:
  - commander asks "Admiral/Taste" for it (SKILL.md:120), but admiral has no
    snapshot procedure;
  - taste covers only explicit management and redesign;
  - the design pipeline has no taste stage.
- **O-4 / D-1 (CONFIRMED, reproduced).** The state machine in
  `contracts/workflow-protocol.md` is incomplete:
  - No row transitions into `TASTE_ACTIVE` except `TASTE_GATE_REVISE`, so the
    Taste states cannot be reached.
  - `investigation-review` has no COMPLETE edge, so a diagnose-only "find out
    why" cannot close.
  - Routing a fix to BUILD requires an `approved_design_revision` that has no
    fallback.
- **D-2 (CONFIRMED).** The runs record `DESIGN_ACTIVE`, `*_GATE_PENDING` and
  `DISPUTED_AWAITING_USER`, while the protocol declares
  INTAKE/DESIGN/GATE/REVISE/ESCALATE. No mapping exists between the two, yet
  admiral `contracts.md:146` binds every transition to the protocol.
- **D-3 (CONFIRMED).** The Taste worked example in `handoff-templates.md:182-210`
  fails the real checker with `bare fallback string not accepted at schema 2:
  residual_uncertainty`.
- **O-5 (PLAUSIBLE).** Running `check.py --prior` against the phase verdict gives
  `prior_reusable: true` with every key unchanged. admiral SKILL:134 and
  gatekeeper-admiral:269 then re-judge only changed evidence, so the cross-stage
  "second look" can judge nothing.

## Minor and info findings (abridged)

**Harness**
- H-6: `git push -f` and `--mirror` are allowed by Rule A.
- H-7: Rule D misses `git branch -D`, `tag`, `update-ref -d`, `worktree`, `gc`
  and `config`.
- H-8: the fault and observation counters do unlocked read-modify-write, so 400
  writes recorded 58.
- H-9: inline interpreter code that only *reads* a frozen path is denied (false
  positive).
- H-10: an `apply_patch` argv shell form is not covered.
- H-11: the `atomic_write` in-place fallback truncates the file before writing,
  and the directory is not fsynced.

**Gates**
- G-4: a revision retyped from `1` to `"1"` evades idempotency drift.
- G-5: zero-byte or whitespace evidence passes.
- G-6: findings without `id` pass, and duplicate ids pass.
- G-7: typed-record `inputs` follow symlinks out of the project.
- G-8: a manifest with a BOM is silently misparsed.
- G-9: taste-review `candidate_ids` are not cross-checked.
- G-10: record checks are shape-only (`themes:[None]`; `status: pass` beside
  `exit_code: 1` passes).
- G-11: `human_go_required` is untyped.
- G-12: on Python < 3.13 the gates crash instead of reporting the floor.
- G-13: `unchecked_fields` overstates what is read; nothing caps the revision
  count.

**Pipelines**
- P-3: `qa-review` requires `defects` and `executed_probes`, but only
  conditional stages produce them.
- P-4: the validators miss a duplicate step id, a misrouted `evidence_owners`,
  `phase-gate` moved first, and a dependency on a conditional stage.
- P-5: requires/produces is declared only in `design`.
- P-6: release and investigation list stages that the gate guards before the
  boundary they close at.

**Orchestrators**
- O-6: the state names are split between the runs and the protocol (see D-2).
- O-7: gate commands use cwd-relative `--package <phase>/manifest.json`; from the
  project root, as admiral instructs, the result is rc=2.
- O-8: delegation goes "via the Agent tool", but no orchestrator grants Agent.
- O-9: commander grills the user from inside a sub-agent with no relay.
- O-10: the claim of "exactly eleven" audit events is wrong; there are thirteen.
- O-11: `create` omits `--execution-mode`, so it defaults to `agent`.
- O-12: delegation checkpoints omit `--next-action`.
- O-13: `skills_engaged` is stored as a JSON string.
- O-14: startup `status` requires a run id before any id is known.
- O-15: admiral rewrites `mcp-tools.md` inside the skill set, and the file ships
  at the epoch timestamp, so every fresh install pauses at intake.
- O-16: the cap wording differs ("two failed revision attempts" against "REVISE
  twice") and never says whether a boundary's phase and cross-stage caps share
  one counter.
- O-17: copilot precedence drops Tier 0; `claude.md` carries a stale model
  trailer.

**Doctrines**
- D-4: the loop guard accepts any lock with `session_pin: true`, including a
  stale one (Minor: "active" mitigates).
- D-5: the `_probe-*.tmp` path has no ownership class.
- D-6, D-7: judgement labels deny comparators that do exist.
- D-8: `_PROJECT_ENV` and `_ROOT_MARKERS` citations are stale.
- D-9: a skill-reviewer duty in the harness doctrine is unbacked.
- D-10: six save classifications are listed where there are eleven.
- D-11: the audit-event count is wrong (see O-10).
- D-12: the SAFETY owner omits `careful`.
- D-13: the delivery-template destination command exits 1 because it lacks
  `--name`.
- D-14: the delivery example uses Tier 1 for a gated edit and hard-codes stale
  counts.
- D-15: the grill-me "seven artifacts" claim is wrong.
- D-16: Taste's unreadable-profile fallback contradicts its own rule.
- D-17: `_LAYER_CITATION` accepts any `§1`–`§5`.
- D-18 to D-22 are info items: class counts, the dual-verdict claim, the clause-3
  vs `major_deferral` mismatch, `mcp-tools` TTL is unchecked, and
  `/exit-admiral` is unregistered.

**Skills.** The per-skill deductions are below. The notable ones not already
listed:
- **Read-only claims the tools don't back.** Six review lenses claim
  "allowed-tools withholds Edit so the posture is enforced". They hold Write and
  Bash, and no read-only record is created (SB-14). cross-check-build-confirm
  makes the same claim (SB-5).
- **Gate slot patterns.** The `*code*.md` gate slot is satisfied by
  `report_code-chief-summary.md` (SB-22).
- **unfreeze.** It claims approver release for read-only records, but
  `cmd_read_only` records no approvers (SC-10).
- **benchmark.** The worked example's confidence-band arithmetic contradicts
  itself (SC-18).
- **skill-maker gate submission.** It says a paraphrased `team_manifest` "fails
  the mechanical check"; `check.py` passes it (SC-20).
- **quick_validate.py.** It accepts a skill whose `name` differs from its
  directory, contrary to skill-creator's claim (SC-23).
- **Browser credentials.** setup-browser-cookies leaves imported cookies in a
  profile with no location rule and no teardown (SC-5).

## Skills: rubric scores (53)

Mean **97.8**, min **94**. Five skills score 100, 47 score 95–99, and one is
below 95. The 09-18 benchmark reported a mean of 99.4 with 31 at 100.

| Group | Scores |
|---|---|
| Admiral layer | admiral 97 · gatekeeper-admiral 99 |
| Design | commander 96 · researcher 98 · planner 99 · architect 96 · engineer 99 · gatekeeper-design 98 · **redesign 94** · design-mapper 99 · prototyper 98 |
| Build | build-management 97 · bob-the-builder 98 · test-builder 97 · security-builder 99 · cross-check-build-confirm 97 · debugger 96 · health-check 95 · gatekeeper-build 99 |
| Review | code-chief 95 · bug-review 98 · code-review 98 · quality-review 98 · security-review 96 · cso 97 · mr-robot 98 · frontier 97 · design-qa 98 · devex-review 99 · gatekeeper-code 98 |
| Cross-cutting | investigate 95 · skill-maker 99 · skill-creator 97 · skill-reviewer 98 · session-memory 98 |
| Taste | taste 99 · taste-review 100 |
| Standalone | audit-improve 95 · browse 97 · open-browser 99 · setup-browser-cookies 98 · pair-agent 99 · ship 99 · land-and-deploy 100 · setup-deploy 99 · document-release 100 · guard 99 · careful 100 · freeze 100 · unfreeze 97 · qa 98 · qa-only 97 · benchmark 97 |

**Ledger regression.** `BENCHMARK.md` says findings from the 2026-09-18 round
"have since been fixed". Of its 26 deductions:

- **19 are still present:**
  - commander intake-brief mirror;
  - redesign: mirror comment and merge example;
  - architect and prototyper: implementation ownership;
  - prototyper scratch path;
  - researcher "first stage";
  - design-mapper union rule;
  - session-memory "LIFE-HARNESS";
  - investigate: Example 0 TOC and verdict file name;
  - qa Evidence Keys TOC;
  - qa-only: path class and bundle shape;
  - skill-creator Optimize trigger;
  - skill-reviewer review-stage owner;
  - security-review: TOC and read-only contract;
  - frontier TOC numbering.
- **6 are fixed:** engineer, taste, ship, gatekeeper-build, taste-review and
  unfreeze-globs.
- **1 is partly fixed:** admiral audit trail (SA-2).

**Why the rubric and orchestrator scores diverge.** On the rubric, admiral scores
97, commander 96 and investigate 95. As executable procedures they score 66, 52
and 52. The rubric reads each file on its own, and the most damaging defect
(O-1) costs each affected skill only D3 −2 on it. The procedural score measures
whether an agent following the text reaches the end.

## Scores by dimension

| Harness | Score | | Gates | Score | | Pipelines | Score | | Orchestrators | Score |
|---|---:|---|---|---:|---|---|---:|---|---|---:|
| Correctness | 70 | | Correctness | 84 | | Correctness | 76 | | Executability | 55 |
| Adversarial robustness | 48 | | Adversarial robustness | 70 | | Mutation robustness | 62 | | Contract fidelity | 60 |
| Failure direction | 75 | | Internal consistency | 84 | | Internal consistency | 78 | | Termination | 70 |
| Test adequacy | 50 | | Cross-file | 76 | | Cross-file | 70 | | Cross-orchestrator | 48 |
| Performance | 86 | | Test adequacy | 66 | | Test adequacy | 60 | | Tool fidelity | 60 |
| Doc–code | 62 | | Error messages | 84 | | Error messages | 85 | | Context economy | 35 |

Context economy: before its first delegation on a full-lifecycle request, admiral
requires about 1,400 lines (~17k words) of mandatory reading. A resume requires
about 950.

| Doctrine / contract | Score | | Doctrine / contract | Score |
|---|---:|---|---|---:|
| evidence-standards | 95 | | responsibility-matrix | 91 |
| design-doctrine | 94 | | handoff-templates | 91 |
| taste-doctrine | 93 | | harness-doctrine | 90 |
| execution-contract | 93 | | routing-doctrine | 89 |
| grill-me-doctrine | 92 | | universal-frameworks | 89 |
| save-protocol | 91 | | delivery-template | 87 |
| performance-doctrine | 91 | | workflow-protocol | **80** |
| | | | mcp-tools | **80** |

## Strengths (verified)

- **`save_run.py`.** Lock ownership, `block --reason`, stale-lock `recover`,
  `complete`/`--reopen`, and evidence re-hashing all behave exactly as admiral
  documents them. A crash injected after `_lock.md` was published recovered to a
  coherent state. Six concurrent checkpoints produced exactly one winner.
- **Gate containment.** Traversal, absolute, drive, UNC, cross-run and
  artifact-symlink paths are refused. Duplicate keys, a bad schema and NaN or
  bool exit codes fail loud with exit 2. REVISE packets group failures by owner.
- **Analyser breadth.** Redirects, `tee`, `dd`, `sed -i`, `perl -pi`, wrappers,
  `eval`, `sh -c`, here-strings, globs, case changes, `..`, symlinks and `cd`
  chains are all handled correctly. Scanning is linear-time.
- **Reference integrity.** Across about 1,000 links, paths, flags and symbols,
  none is broken.
- **Candour.** Nearly every doctrine carries an enforcement-status table. Most
  errors are understatements, which is the safe direction.
- **Tier 0 and caps.** The fast path is tightly bounded. The cap of 2 and its
  escalation are applied uniformly.

## Recommended remediation order

1. **O-1.** Replace `--owner <self>` with `--owner admiral --set
   delegated_to=<self>` in the 13 documents. Then add a validation test that
   rejects any `save_run.py checkpoint --owner X` example where X is not the
   documented lock holder.
2. **H-1 and H-3.** Treat any copy, install, link, rsync or extract whose
   destination is a directory holding a single-writer record as a write to that
   record, and add `git clean` and `rsync --delete` to the tree verbs.
3. **H-2.** Resolve `$PWD`, `$CLAUDE_PROJECT_DIR` and `$OLDPWD` the way `${PWD}`
   already is. Deny unresolved variables that prefix a protected path.
4. **H-4.** Add the guard's whole import closure, including `skills/scripts/`
   modules, to Rule F, and catch `BaseException` in `pre_tool_use.py`.
5. **G-1.** Detect run layout by searching every ancestor, not four levels.
6. **G-2.** Strip a BOM and normalise keys in `_gatecheck`.
7. **G-3.** Add mutation tests that make spec weakening fail.
8. **P-1 and P-2.** Add a sanctioned carry-forward for repeat deploys, and accept
   the typed applicability record for `security_seed`.
9. **D-1, D-2 and O-4.** Reconcile `workflow-protocol.md` with the phase-state
   vocabulary the runs record. Add Taste entry edges and an investigation
   COMPLETE edge, and add a reachability test.
10. **O-2, O-3 and D-3.** Fix the adapters, assign a `taste_snapshot` producer,
    and make the Taste example pass the checker. Then clear the 19 stale ledger
    items and re-run the rubric so that `BENCHMARK.md` stops overstating the
    current state.

## Remediation status

The scores and findings above are the before-state and are not edited. The two
Critical findings and four Major findings (the first four after them in the
remediation order) are resolved. Each one has a regression test that fails on
the pre-fix code; together the new tests produced 53 failures and 2 errors there.

| Finding | Fix | Regression test |
|---|---|---|
| O-1 | 15 checkpoint commands in 12 skills now pass `--owner admiral` (the lock holder) and record the delegate with `--set delegated_to=`. The new test found two multi-line examples the audit missed. | `validation/test_save_prose.py` refuses any documented `save_run.py` command whose `--owner` is not the writer's lock holder |
| H-1 | The analyser names the file a copy, link or install lands as (`dir/<name>`). Rule C reads a sync, an extract, a recursive or contents copy, `git clean` and `find -exec` editors as tree writes into a record directory. | `test_guard_rules.DirectoryDepositTests` (record deposits and neighbours) |
| H-3 | Rule B counts `rsync`, extracts, recursive or contents copies, `Copy-Item` and `find -exec` editors aimed above a boundary as tree writes. A plain `cp a.py src/` is judged by the file it lands as. | `DirectoryDepositTests` (tree writes and neighbours) |
| H-2 | `$PWD` resolves to the shell's directory, and the `_state.PROJECT_ENV` variables resolve to the host's values. A path led by an unresolved variable is also judged without it. Rule F reads launchers and unplaced writes as Rule B does. | `DirectoryDepositTests` (variable spellings), `test_guard_cmdscan` |
| H-4 | Rule F covers `skills/scripts/data_formats.py` and `save_taxonomy.py`. A rule that raises `SystemExit` is counted and skipped. A taxonomy that fails its import is counted, and the guard keeps enforcing. The entry counts any `SystemExit` the guard did not take itself. | `test_guard_harness_files`, `test_pre_tool_entry.PoisonedHelperTests`, `EntryPointTests` |
| G-1 | `check.py` finds the run directory from any depth. | `test_gate_run_layout` (depths 1 to 6, a schema-1 package with an open Critical) |

Still open from this audit:

- **Major, not yet fixed:** H-5, G-2, G-3, P-1, P-2, O-2, O-3, O-4/D-1, D-2 and
  D-3, plus O-5, which is plausible but unconfirmed.
- **All Minor and Info findings.**

### Follow-up: root-level writes

The root-level gap left open above is now closed. Rule C reads a command aimed at
the project root by what it would remove or land in the record directories, and
only while a record exists:

- `git clean -d` with `-x`/`-X`, or without them when the directory is not
  git-ignored;
- `rsync --delete`;
- an archive whose members land there; the guard lists tar and zip archives,
  and one it cannot read is refused;
- a contents copy or sync whose source holds one, or whose source is not named
  or not on disk.

`-e` and `--exclude` lift the refusal. At the owner's request, a freeze no longer
refuses an archive unpacked at the project root, and Rule F refuses one only
while an Admiral run is active. Covered by `test_guard_rules.RootExtractTests`
and `RootRecordReachTests`, which fail 21 times on the previous commit.

### Re-measured in round 3

[Round 3](quality-audit-2026-10-05.md) re-ran every reproduction above on
`8eae856`. O-1, H-1 to H-4 and G-1 hold. The root-level follow-up is only partly
closed: other spellings still reach the records, and two of them are regressions
from this commit:

- `tar --strip-components`, `--transform` and `-P`, and archive symlink members (N-1);
- `cp -rT` (N-2);
- `git clean` pathspecs and `-c clean.requireForce=false` (N-3);
- `git stash --all` (N-4);
- a root `unzip` of `.claude/` or of a blocked path outside an Admiral run (N-5).

O-5 is now confirmed. Every other finding listed above as open is still present.
