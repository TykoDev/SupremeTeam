# Supreme Team quality audits

This file is the single record of the catalog's quality audits. Every finding
those audits raised is kept here, with its current status. BENCHMARK.md carries
the headline numbers and the per-skill deduction ledger. This file carries what
sits behind them:

- the benchmark runs, the reproductions and the surface scores;
- every finding, under a stable id, with its status today.

Three rounds have been run so far. Each later round re-ran the reproductions of
the one before it.

| Round | Date | Audited at | Method | Overall | Tests |
|---|---|---|---|---:|---|
| 1 | 2026-10-01 | the tree before `98976d4` | Read-and-score on five dimensions, plus the suites | 90 | 2,277 run, 1 failed, 4 environment-limited |
| 2 | 2026-10-01 | the tree before `f232d7c` | Executed: literal procedures, about 230 hostile guard probes, forged gate packages, spec mutation | 76 | 2,284, all passing |
| 3 | 2026-10-05 | `8eae856` | Round 2's method again, every round-2 reproduction re-run, about 130 new guard probes, paid routing and registration runs | 78 | 2,308, all passing |

Round 1's 90 and the executed rounds' 76 and 78 measure different things.
Round 1 scored surfaces by reading them; rounds 2 and 3 scored them by running
them. Every score in this file is a model judgement against a stated method, not
machine output. The durable output is the cited, reproduced findings. The totals
only summarise them.

## Contents

- [Current state (round 3)](#current-state-round-3)
- [Method](#method)
- [Benchmark results](#benchmark-results)
- [Routing and registration](#routing-and-registration)
- [Findings register](#findings-register)
- [Skills](#skills)
- [Spec, harness and doctrine artefacts](#spec-harness-and-doctrine-artefacts)
- [Scores by dimension](#scores-by-dimension)
- [Strengths](#strengths)
- [Recommended remediation order](#recommended-remediation-order)
- [Remediation history](#remediation-history)

## Current state (round 3)

**Overall: 78/100, up from 76 in round 2.**

- All seven suites pass: 2,308 tests on Python 3.13.
- The validators and the pinned lint pass.
- All 22 root-level skills register with the host.

**What the remediation fixed.** Commit `8eae856` carries the round-2 remediation:
O-1, H-1 to H-4, G-1, and the root-level-write follow-up. All six of those fixes
hold.

**What is still open.**

- The root-level follow-up is not closed:
  - four new Major bypasses, N-1 to N-4, each lift a freeze in one allowed
    command;
  - two Majors, N-1 and N-5, are regressions from `8eae856` itself.
- Every other Critical and Major left open in round 2 is still open.

| Surface | Round 3 | Round 2 | Round 1 | What moved it in round 3 |
|---|---:|---:|---:|---|
| Skills (rubric, 53) | **97.5** (min 94) | 97.8 (min 94) | 90 | No rubric-visible change. 20 of the 26 deductions in the 09-18 ledger are still present |
| Doctrines, protocols and contracts (15) | **93.1** (min 78) | 89.7 (min 80) | 88 | None of these files changed since round 2. The rise is scorer variance, not improvement |
| Pipelines | **71.8** | 71.8 | 93 | No pipeline or gate-spec file changed. P-1, P-2 and the G-3 mutations reproduced again |
| Review gates | **78.7** | 77.3 | 94 | G-1 fixed; G-2 to G-13 unchanged |
| Harness (hooks and guard) | **69.2** | 65.2 | 85 | H-1 to H-4 fixed; N-1 to N-5 found, two of them regressions |
| Orchestrators (procedural) | **59.2** | 54.7 | 89 | O-1 fixed in all 12 lead skills; O-2, O-3, O-5 and O-7 remain |
| **Overall** (equal weight) | **78/100** | 76 | 90 | 77.7 with the doctrine row held at its round-2 value |

The doctrine row shows how large scorer variance can be. None of the 15 doctrine
and contract files changed between rounds 2 and 3: `git diff f232d7c 8eae856`
touches none of them. Even so, single files moved by as much as 6 points, from
−2 for workflow-protocol to +6 for grill-me, performance-doctrine and
universal-frameworks. A move of that size on one artefact is not a trend.

## Method

### Round 3

- **Scope.** Commit `8eae856`, read-only. Every probe ran in copies of the
  checkout under a scratch directory.
- **Benchmark.**
  - The seven suites ran sequentially on Python 3.13.14 with PyYAML 6.0.1.
  - The CI "without PyYAML" leg (validation, scripts and gates) ran in a bare
    venv.
  - The three validators ran, as did `ruff==0.16.9`, the version CI pins.
  - Hook latency was measured the way a host invokes the hooks: one cold process
    per call.
  - Two paid measurements ran against the live host: the routing eval
    (`trigger_eval.py --mode both --paraphrase --per-skill 4`) and host
    registration (`run_eval.py --registration`).
- **Seven independent auditors**, in parallel:
  - five scored the skills in groups, on the rubric in
    `skills/skill-maker/skill-reviewer/references/scoring-rubric.md`;
  - one scored the spec, harness and doctrine artefacts on six contract
    dimensions, using spec mutation;
  - one re-ran every round-2 reproduction and made about 130 new guard probes.
- **Verification.**
  - A finding counts only when it is cited on both sides: the claim and its
    source of truth.
  - Each finding is marked CONFIRMED when it was reproduced, or PLAUSIBLE when it
    was only reasoned from the code.
  - The lead auditor reproduced N-1 and N-2 independently. N-1 was executed for
    real: after the extract, `guard_state.py status` printed `frozen: -`.
  - Where two auditors disagreed (G-10), the lead re-read the code.

### Round 2

Unlike round 1, round 2 executed what it scored:

- documented procedures were run literally;
- about 230 hostile inputs were sent to the guard;
- forged packages were submitted to the gates;
- the specs were mutated.

Seven auditors ran in parallel:

- harness;
- gates and pipelines;
- orchestrators, as a tabletop run of three requests that executed `save_run.py`
  exactly as instructed;
- doctrines, by extracting claims and resolving every link, path, flag and
  symbol automatically;
- three skill groups.

The lead auditor re-reproduced O-1, H-1, H-2, H-3, H-5, G-1 and D-1. Each surface
score is the mean of six dimensions (see [Scores by dimension](#scores-by-dimension)).

### Round 1

Round 1 covered:

- all 53 `SKILL.md` files;
- the doctrine files and the save, execution and MCP protocols;
- the ten pipelines and ten gate boundaries;
- the hook and gate harnesses;
- the orchestrators.

Every surface was scored on five equally weighted dimensions: coverage,
consistency, enforcement, safety and operability. It was a checkout audit, not a
production-effectiveness study. No saved runs or trajectories existed, so the
round measured specification quality, deterministic validation, test breadth and
local runtime behaviour.

## Benchmark results

### Round 3

| Suite / check | Result | Tests | Wall time |
|---|---|---:|---:|
| hooks | OK (2 skipped) | 950 | 153.1 s |
| gates | OK (1 skipped) | 256 | 20.9 s |
| validation | OK (1 skipped) | 258 | 9.9 s |
| scripts | OK | 386 | 23.5 s |
| taste | OK | 213 | 11.9 s |
| installers | OK | 85 | 86.7 s |
| skill-creator | OK | 160 | 4.2 s |
| gates / validation / scripts without PyYAML | OK (1 / 9 / 3 skipped) | 256 / 255 / 386 | 23.9 / 9.8 / 20.6 s |
| `validate_manifests.py` / `check_runtime.py` / `package_check.py` | pass | — | 0.09 / 0.12 / 0.11 s |
| `ruff check .` (0.16.9) | clean | — | — |

- **Totals.** 2,308 tests with PyYAML, all passing.
- **Timing caveat.** The installers and taste suites ran while the routing eval
  and the auditors were also running. Read their wall times as an upper bound.
- **Hook latency.** Cold process, n=40 per row:

  | Hook and input | Median | p95 |
  |---|---:|---:|
  | `pre_tool_use.py`, no boundary (read / write) | 81 / 84 ms | 101 / 94 ms |
  | `pre_tool_use.py`, freeze recorded (read / denied write) | 84 / 82 ms | 103 / 106 ms |
  | `pre_tool_use.py`, a 9.5 KB chained command | 127–130 ms | 169–175 ms |
  | `post_tool_use.py` | 80 ms | 99 ms |
  | `user_prompt_submit.py` | 59 ms | 75 ms |

  - A bare interpreter starts in 14 ms.
  - The archive listing added in `8eae856` is the one non-linear cost. A
    150,000-member tar costs about 3.1 s per call, and a compressed archive is
    decompressed in full, with no size cap (N-9).
- **Floor behaviour.** Under Python 3.11, `check_runtime.py` correctly prints
  `Ready: no`. The gatekeeper wrappers still crash with
  `AttributeError: … is_junction` instead of reporting the floor (G-12).
- **Static profile.**

  | Measure | Value |
  |---|---|
  | `SKILL.md` length | mean 197 lines, median 171, max 468 (`skill-maker`) |
  | Description length | mean 516 chars, max 600, none above the 1,024 host limit |
  | Skills with no `references/` | `audit-improve` only |
  | Code size | 23.0k lines of non-test Python, 33.9k lines of tests in 68 modules |

### Suite counts across rounds

| Suite | Round 1 | Round 2 | Round 3 |
|---|---:|---:|---:|
| hooks | 927, one performance assertion failed (F-01) | 928 | 950 |
| gates | 255 | 255 | 256 |
| validation | 253 (9 skipped) | 257 | 258 |
| scripts | 386 | 386 | 386 |
| taste | 213 | 213 | 213 |
| installers | 85 | 85 | 85 |
| skill-creator | 158, four environment-limited failures (F-03) | 160 | 160 |
| **Total** | 2,277 | 2,284 | 2,308 |

The count rose by 24 from round 2 to round 3. All 24 are regression tests for the
round-2 fixes: hooks +22, gates +1 and validation +1.

The other measurements, by round:

- **Round 1** ran Python 3.13.13. Its wall times were roughly double the later
  rounds: hooks 299.6 s, installers 181.1 s.
- **Round 2** measured `pre_tool_use.py` at a median of 76–81 ms and a p95 of
  98–103 ms, over n=36 in each of 3 projects. Its doctrine auditor resolved
  references automatically with zero broken in every class: 254 Markdown links
  and anchors, 383 backticked paths, 97 CLI flags, 283 test, class and constant
  names, and about 40 quoted failure strings.

Single local wall-clock observations locate cost; they are not cross-host
baselines. A longitudinal timing benchmark needs at least five full samples per
supported OS, reported as median and p95.

## Routing and registration

These are round 3's paid measurements. The routing history from round 1 onward
is in [BENCHMARK.md](../BENCHMARK.md#routing).

**Routing, round 10: 278/311 = 89.4%**, measured on the 53-skill roster for
$4.81. Round 9 measured 94.8% on 09-18, when the roster had 52 skills.

- **By corpus.** Advertised 188/210 (89.5%); routed 90/101 (89.1%). Both corpora
  are paraphrased.
- **Owner credit.** 15 correct answers were credited because the chosen skill is
  the expected skill's declared delegating owner (`via_owner`).
- **Misroute clusters:**
  - `build/debugger` → `investigate`: 4.
  - Specialists → `admiral`: 5 (`bob-the-builder` ×3, `test-builder`, `qa-only`).
    `admiral` is the documented front door for a cold request, but it is not the
    declared owner of a specialist, so the scoring rule does not credit it. If it
    did, the score would be 283/311 (91.0%).
  - `skill-maker/skill-reviewer` asked in plain English: 3, going to
    `code-chief`, `ship` and `qa-only`.
  - `open-browser` → `browse`: 2.
  - The design leads among themselves: 5.
- **Reading the drop.** The paraphrases are regenerated on every run. The roster
  also gained `audit-improve`, the one skill with no `## Use This Skill When`. One
  run cannot separate those causes from catalog drift; giving a variance band
  needs a repeat run.

**Registration:**

- All 22 root-level skills registered, measured against a control session with no
  catalog installed.
- The host's own `code-review` shadows `review/code-review`, a nested specialist
  that is not meant to register.
- The 30 other nested specialists did not register, as designed. 18 of them are
  named in `routing-doctrine.md`, which reaches them by path.

## Findings register

Ids are stable across rounds:

| Prefix | Raised in | Covers |
|---|---|---|
| `F-` | round 1 | |
| `H-` | round 2 | harness |
| `G-` | round 2 | gates |
| `P-` | round 2 | pipelines |
| `O-` | round 2 | orchestrators |
| `D-` | round 2 | doctrines |
| `N-` | round 3 | new findings |

"Status" is the state as of round 3, and every open entry was re-run in that
round.

### Open: Critical and Major

| Id | Sev | Finding | Status (round 3) |
|---|---|---|---|
| N-1 | Major | **Archive extracts still reach the guard records.** The guard reads an archive's member names literally, so these land in the records: `tar --strip-components=1`, `--transform 's,^,.harness-state/,'`, `-xPf` (absolute names), and a symlink member (`lnk -> .harness-state`, then `lnk/guard-state.json`). **Regression:** the strip-components spelling was denied on `ac263cc`. | CONFIRMED by the lead: the freeze was lifted |
| N-2 | Major | **Contents copy over the root.** `cp -rT backup .` and `cp --no-target-directory` copy a backup over the root. Only the `x/.` spelling is read as a contents copy. | CONFIRMED by the lead |
| N-3 | Major | **`git clean` holes:** <ul><li>the pathspecs `:/`, `'*'` and `':(glob)**'` get through;</li><li>an `-e` pattern is judged by its first segment only;</li><li>`-c clean.requireForce=false clean -dx` needs no `-f`;</li><li>the ignore-file reading skips `!` lines and treats a partial path as ignoring the whole directory.</li></ul> | CONFIRMED |
| N-4 | Major | **`git stash` removes the records.** `git stash --all` removes both record directories, even with the shipped `.gitignore`. `git stash -u` does the same when the records are not ignored. | CONFIRMED |
| N-5 | Major | **Root unzip outside a run.** Under a freeze or block with no Admiral run, a root `unzip` is allowed even when it carries `.claude/settings.local.json` (setting `disableAllHooks`), a hook file or a blocked path. All of these were denied on `ac263cc`. The hooks README states the trade as deliberate, but Rule C already lists the archive's members and could cover these paths. **Regression.** | CONFIRMED |
| H-5 | Major | **Rule A misses destructive text inside a pipe or a launcher.** Allowed: `echo 'rm -rf /' \| sh`, `watch 'rm -rf /'`, `perl -e 'system("rm -rf /")'` and `python3 -c 'import os; os.system("rm -rf /")'`. `bash -c 'rm -rf /'` is denied. The hooks README says the opposite twice. | Still present |
| G-2 | Major | **Revision checks defeated by a BOM or quoted key.** A UTF-8 BOM before `---` (`_gatecheck.py:270`), or a quoted `'revision'` or `"revision"` key, defeats `MIXED_REVISIONS` and `MIXED_SUBMISSION_IDS`. Packages with mixed revisions then report `REVISION_COHERENT PASS`. | Still present |
| G-3 | Major | **Weakening the gate spec goes unnoticed.** Each of these edits passes every validator and every related test: <ul><li>adding `fallback_values.findings: ["no findings"]`;</li><li>making `executed_probes` waivable;</li><li>dropping `tests` from the `build-to-review` `artifact_evidence`.</li></ul> | Still present |
| P-1 | Major | **A repeat deployment cannot pass `deploy-readiness`.** `setup` runs only `when: first deployment` (`pipelines.yaml:456`). `deploy_config` and `rollback_plan` are artifact-backed with no fallback. The carry-forward that `setup-deploy` and `ship` prescribe is refused: "artifact references another run". | Still present |
| P-2 | Major | **`security_seed` rejects the prescribed record.** For design `security_seed`, a conditional stage, the gate refuses the typed applicability record that `failure_paths.when_condition_ambiguous` prescribes ("evidence not waivable"). The bare prose `"n/a"` passes. | Still present |
| O-2 | Major | **Adapters write the run records directly.** All three admiral adapters (`adapters/claude.md:48`, `copilot.md:76-77`, `codex.md:13`) tell the agent to write the run-state, lock and audit files directly. Rule C denies those writes. | Still present |
| O-3 | Major | **No `taste_snapshot` for a design run.** Nothing produces `taste_snapshot` for an ordinary design run: <ul><li>commander asks "Admiral/Taste" for it;</li><li>admiral has no snapshot procedure;</li><li>taste covers only explicit management and redesign;</li><li>the design pipeline has no taste stage.</li></ul> | Still present |
| O-4 / D-1 | Major | **The state machine in `contracts/workflow-protocol.md` is incomplete:** <ul><li>`TASTE_ACTIVE` is entered only from `TASTE_GATE_REVISE`;</li><li>`investigation-review` has no COMPLETE edge, so a diagnose-only "find out why" cannot close;</li><li>`GATE` has no transition to BUILD or REVIEW;</li><li>routing a fix to BUILD needs an `approved_design_revision` with no fallback.</li></ul> | Still present |
| D-2 | Major | **Phase states are not mapped to the protocol.** The runs record `DESIGN_ACTIVE`, `*_GATE_PENDING` and `DISPUTED_AWAITING_USER`. The protocol declares INTAKE, DESIGN, GATE, REVISE and ESCALATE, and nothing maps one set to the other. Even so, admiral `contracts.md:146` binds every transition to the protocol. | Still present |
| D-3 | Major | **The Taste worked example fails the checker.** The example in `handoff-templates.md:182-210` fails with `bare fallback string not accepted at schema 2: residual_uncertainty`. | Still present |
| O-5 | Major | **The cross-stage second look can judge nothing.** Running `check.py --prior` against the phase verdict gives `prior_reusable: true` and `changed_evidence: []`. gatekeeper-admiral re-judges only changed evidence, so the cross-stage "second look" judges nothing. | Still present; upgraded from PLAUSIBLE to CONFIRMED in round 3 |

### Open: Minor and Info

**Harness**

| Id | Finding | Status |
|---|---|---|
| H-6 | Rule A allows `git push -f`, `--force` and `--mirror`. | Still present |
| H-7 | In a read-only run, Rule D allows: <ul><li>`git branch -D`, `tag -d` and `update-ref -d`;</li><li>`worktree remove`, `gc` and `config`;</li><li>`branch -m`, `reflog expire` and `remote remove`.</li></ul> | Still present |
| H-8 | The fault and observation counters do an unlocked read-modify-write. 200 concurrent fault writes recorded 23. | Still present |
| H-9 | Inline interpreter code that only *reads* a frozen path is denied, a false positive. | Still present |
| H-10 | A Bash `apply_patch` into a frozen path is allowed, in heredoc, argument or pipe form. | Still present |
| H-11 | The in-place fallback in `atomic_write` truncates the file before it writes (`_fsutil.py:106`), and the directory is never fsynced. | Still present |
| N-6 | Rule C does not refuse a root `rsync --delete` that also uses `--delete-excluded`, a partial-path exclude, or `--include` before `--exclude`. A freeze still blocks these. | Decision CONFIRMED; effect PLAUSIBLE |
| N-7 | Rule C does not read `find . -name guard-state.json -delete` at the root. | CONFIRMED |
| N-8 | Extracts the guard cannot see: <ul><li>extractors it does not know: `jar xf`, `python3 -m zipfile -e`, `bsdtar`, `gtar`, `pax`, `cpio`;</li><li>a tar+zip polyglot;</li><li>an archive swapped earlier in the same command;</li><li>destinations built at run time (`"$(pwd)"`, `~+`).</li></ul> | CONFIRMED |
| N-9 | False positives: `cd src && git clean -fdx`, `cd docs && unzip ../a.zip` and `tar -xOf` are denied as "aimed at the project root". The archive listing has no bound on size or cost. | CONFIRMED |
| N-10 | Docs that claim more than the code does: <ul><li>the hooks README says `echo "rm -rf /"` is denied, but it is allowed;</li><li>a blocked-glob denial says "frozen boundary";</li><li>the `guard` and `freeze` skill docs omit the root-extract exemption;</li><li>round 2 stated that the root-level gap "is now closed".</li></ul> | CONFIRMED |

**Gates**

| Id | Finding | Status |
|---|---|---|
| G-4 | A revision retyped from `1` to `"1"` evades idempotency drift. | Still present |
| G-5 | Zero-byte or whitespace-only evidence passes. | Still present |
| G-6 | Findings with no `id` pass, and so do duplicate ids. `gates.yaml` says an id is required. | Still present |
| G-7 | Typed-record `inputs` follow symlinks out of the project. | Still present |
| G-8 | A manifest with a BOM fails closed, but is misparsed: a JSON one gets 14 bogus "missing" errors, and a YAML one is read as having no schema version. | Still present |
| G-9 | taste-review `candidate_ids` are not cross-checked against the preference diff. | Still present |
| G-10 | Record checks only test shape: <ul><li>`themes: [None]` passes;</li><li>a nested `result: {status: pass, exit_code: 1}` passes;</li><li>a top-level `pass` beside `exit_code: 1` is refused (`check.py:804-814`), and was refused before round 2 as well.</li></ul> | Still present |
| G-11 | `human_go_required` is untyped (`"no"` and `{"x": null}` pass). | Still present |
| G-12 | On Python < 3.13 the gate wrappers crash with `AttributeError: … is_junction` instead of reporting the floor. | Still present |
| G-13 | `unchecked_fields` overstates what is read, and `check.py` never reads `cycle_cap`. | Still present |

**Pipelines**

| Id | Finding | Status |
|---|---|---|
| P-3 | `qa-review` requires `defects` and `executed_probes`, but only conditional stages produce them. | Still present |
| P-4 | The validators miss each of these four mutations: <ul><li>a duplicate step id;</li><li>a misrouted `evidence_owners`;</li><li>`phase-gate` moved first;</li><li>a dependency on a conditional stage.</li></ul> | Still present |
| P-5 | Requires/produces is declared only in the `design` pipeline. | Still present |
| P-6 | release and investigation list stages that the gate guards before the boundary they close at. | Still present |

**Orchestrators**

| Id | Finding | Status |
|---|---|---|
| O-6 | The state names are split between the runs and the protocol (see D-2). | Still present |
| O-7 | Self-check commands pair a project-relative script path with a phase-relative `--package <phase>/manifest.json`. Run from the project root, as admiral instructs, they exit 2. Present in commander, redesign, code-chief, build-management and gatekeeper-code. | Still present |
| O-8 | Delegation goes "via the Agent tool", but no orchestrator grants Agent. | Still present |
| O-9 | commander grills the user from inside a sub-agent, with no relay back to the user. | Still present |
| O-10 | admiral claims "exactly eleven" audit events (`SKILL.md:240`); the code emits thirteen. | Still present |
| O-11 | `create` omits `--execution-mode`, so it defaults to `agent`. | Still present |
| O-12 | Delegation checkpoints omit `--next-action`. | Still present |
| O-13 | `skills_engaged` is stored as a JSON string. | Still present |
| O-14 | Startup `status` requires a run id before any id is known. | Still present |
| O-15 | admiral rewrites `mcp-tools.md` inside the skill set, and the file ships with the epoch timestamp, so every fresh install pauses at intake. | Still present |
| O-16 | The cap wording differs ("two failed revision attempts" against "REVISE twice"). It never says whether a boundary's phase cap and cross-stage cap share one counter. | Still present |
| O-17 | Copilot precedence drops Tier 0, and `adapters/claude.md` carries a stale model trailer. | Still present |

**Doctrines**

| Id | Finding | Status |
|---|---|---|
| D-4 | The loop guard accepts any lock with `session_pin: true`, a stale one included. | Still present |
| D-5 | The `_probe-*.tmp` path has no ownership class. | Still present |
| D-6, D-7 | Judgement labels deny comparators that exist. For example, `universal-frameworks.md` says no test names the file, but `test_docs_inventory.py:278` opens it. | Still present |
| D-8 | The `_PROJECT_ENV` and `_ROOT_MARKERS` citations are stale. | Still present |
| D-9 | A skill-reviewer duty in the harness doctrine has nothing backing it. | Still present |
| D-10 | Six save classifications are listed where there are eleven. | Partly fixed: `save-protocol.md` lists 11; `routing-doctrine.md` still lists 6 |
| D-12 | The SAFETY owner list omits `careful`. | Still present |
| D-13 | The delivery-template destination command exits 1 for lack of `--name`. | Still present |
| D-14 | The delivery example uses Tier 1 for a gated edit, and hard-codes counts. The anchored-copy count says 10 of 91; the comparator gives 9 of 91. | Still present |
| D-15 | The grill-me "seven artifacts" claim is wrong. | Still present |
| D-16 | Taste's fallback for an unreadable profile contradicts its own rule. | Still present |
| D-17 | `_LAYER_CITATION` accepts any `§1`–`§5`. | Still present |
| D-18 | Class counts. | Mostly fixed: `runtime-manifest.yaml` line 82 says 17 `--kind` values; there are 18 |
| D-19 to D-22 | Info items: <ul><li>D-19: the dual-verdict claim;</li><li>D-20: the clause-3 versus `major_deferral` mismatch;</li><li>D-21: the `mcp-tools` TTL is unchecked;</li><li>D-22: `/exit-admiral` is unregistered.</li></ul> | Still present |

### Resolved

| Id | Round | Finding | Fixed by |
|---|---|---|---|
| F-01 | 1 | The command scanner exceeded its 4 s hostile-input budget on a deeply nested PowerShell block, at 4.3–4.5 s in four of four runs. | Recursive replay stops at the existing 64-level brace bound. A 1,000-level regression proves `Remove-Item` stays visible. |
| F-02 | 1 | Hook enforcement was not registered on the audited host. | Registered through the sanctioned repair command, on that host only. No host configuration was committed. |
| F-03 | 1 | Older-interpreter checks treated dormant pyenv shims as runnable, and four launches failed with 127. | Discovery probes each candidate's version first. |
| F-04 | 1 | Specification density: the largest skills ran to 458, 414 and 402 lines. | Operator indexes were added above 400 lines, and a catalog contract now enforces a 500-line ceiling. |
| O-1 | 2 (Critical) | Every phase lead's checkpoint ran `save_run.py checkpoint --owner <self>`, and `require_owner` refuses it because admiral holds the lock. A literal agent stalled at the first checkpoint of every delegated pipeline. | The 15 commands in 12 skills now pass `--owner admiral --set delegated_to=<self>`. `validation/test_save_prose.py` refuses any documented command whose `--owner` is not the lock holder. |
| H-1 | 2 (Critical) | Copying into a record's directory replaced the guard record. `cp /tmp/x/guard-state.json .harness-state/` lifted every freeze, and so did `install`, `rsync`, `cp -t`, `ln -sf`, `tar -C` and `cd … && cp`. | The analyser names the file a copy lands as. Rule C reads syncs, extracts, recursive copies, `git clean` and `find -exec` editors as tree writes into a record directory. |
| H-2 | 2 | Targets spelled with `$PWD` or `$CLAUDE_PROJECT_DIR` got past a freeze, a block and Rule F. | Both resolve. A path led by an unresolved variable is judged without it. |
| H-3 | 2 | Tree writers aimed above a boundary were not treated as tree writes: `find -exec sed -i`, `rsync --delete` and `tar -C src`. | Rule B counts them as tree writes. |
| H-4 | 2 | Appending `raise SystemExit(0)` to `skills/scripts/save_taxonomy.py` silently disabled the guard. | Rule F covers the guard's import closure, and a `SystemExit` raised inside a rule is counted. |
| G-1 | 2 | A run layout found only four levels deep let a package with an open Critical pass `review-to-delivery`. | `check.py` finds the run directory from any depth. |
| D-11 | 2 | `save-protocol.md` miscounted the audit events. | It now says thirteen. The same miscount in admiral is O-10. |

## Skills

Round 3 scored all 53 skills on the 10-dimension rubric. The per-skill table and
the ledger of 121 cited deductions are in
[BENCHMARK.md](../BENCHMARK.md#skills).

- Mean **97.5**, median 98, lowest **94**.
- 5 skills score 100, 46 score 95–99, and 2 score 94.

| Group | Scores |
|---|---|
| Admiral layer | admiral 95 · gatekeeper-admiral 98 |
| Design | commander 97 · researcher 99 · **planner 100** · architect 98 · **engineer 100** · gatekeeper-design 96 · redesign 95 · design-mapper 97 · prototyper 98 |
| Build | build-management 98 · bob-the-builder 99 · test-builder 98 · security-builder 99 · cross-check-build-confirm 96 · debugger 98 · health-check 95 · gatekeeper-build 99 |
| Review | code-chief 97 · bug-review 97 · code-review 96 · quality-review 98 · security-review 97 · **cso 94** · **mr-robot 94** · frontier 97 · design-qa 97 · devex-review 96 · gatekeeper-code 96 |
| Cross-cutting | investigate 97 · skill-maker 97 · skill-creator 97 · skill-reviewer 98 · session-memory 97 |
| Taste | taste 97 · **taste-review 100** |
| Standalone | audit-improve 97 · browse 98 · open-browser 99 · setup-browser-cookies 98 · pair-agent 99 · ship 98 · **land-and-deploy 100** · setup-deploy 99 · **document-release 100** · guard 96 · careful 98 · freeze 98 · unfreeze 97 · qa 97 · qa-only 98 · benchmark 98 |

These patterns recur across skills:

- **Self-check commands that cannot run as written (O-7).**
- **Verdict ownership misattributed.**
  - cso, mr-robot and security-review say cso issues the `security-review`
    verdict; the protocol and `pipelines.yaml` give it to gatekeeper-admiral.
  - gatekeeper-code asks code-chief to "run the CSO lens", but the review pipeline
    has no stage for it.
- **Read-only postures claimed but not enforced.**
  - Six review lenses (SB-14) and cross-check-build-confirm (SB-5) still hold
    Write and Bash, and none of them records a read-only boundary.
  - devex-review says a write that escapes an install step is denied, but the
    guard does not see the scripts a command runs.
- **Who can release a boundary.**
  - guard and freeze say only the owner can release one, but `guard_state.py`
    also accepts approvers.
  - unfreeze says the opposite about read-only records, which store no approvers.
- **Worked examples that fail the real tools.**
  - cso Example 4 fails `check.py` four times.
  - Two session-memory commands are refused by `save_run.py`.
  - test-builder's quarantine record fails the findings shape.
  - The design-mapper aggregate example would be sent back by the design gate.

**The 09-18 ledger.** Of its 26 deductions:

- 20 are still present;
- 2 are partly fixed: the admiral audit trail and the taste flat-map import;
- 4 are fixed: engineer, ship, gatekeeper-build and taste-review.

**Rubric scores are not procedural scores.** In round 2, admiral, commander and
investigate scored 97, 96 and 95 on the rubric. As executable procedures they
scored 66, 52 and 52. The rubric reads each file on its own, so the most damaging
defect, O-1, cost each affected skill only D3 −2. The procedural score instead
measures whether an agent that follows the text reaches the end.

## Spec, harness and doctrine artefacts

Round 3 scored these on six contract dimensions, normalised to 100: authority,
enforcement, internal consistency, cross-consistency, completeness and
actionability.

- The 21 artefacts BENCHMARK.md tracks have a mean of **94.0**.
- With `mcp-tools.md` added, the mean of all 22 is **93.4**.

| Score | Artefacts |
|---:|---|
| 98 | evidence-standards, design-doctrine, execution-contract, grill-me-doctrine, save-ownership.yaml, team + runtime + package manifests |
| 97 | ownership.yaml, performance-doctrine |
| 95 | universal-frameworks, taste-doctrine, save-protocol |
| 94 | harness-doctrine |
| 93 | responsibility-matrix, harness/gatekeeper, routing-doctrine |
| 92 | delivery-template, handoff-templates, harness/hooks |
| 91 | gates.yaml, pipelines.yaml |
| 81 | mcp-tools.md |
| **78** | contracts/workflow-protocol.md |

Round 2's doctrine scores, for comparison:

| Artefact | Score |
|---|---:|
| evidence-standards | 95 |
| design-doctrine | 94 |
| taste-doctrine, execution-contract | 93 |
| grill-me-doctrine | 92 |
| save-protocol, performance-doctrine, responsibility-matrix, handoff-templates | 91 |
| harness-doctrine | 90 |
| routing-doctrine, universal-frameworks | 89 |
| delivery-template | 87 |
| workflow-protocol, mcp-tools | 80 |

The largest round-3 deductions:

- **workflow-protocol:** O-4/D-1, D-2 and D-12.
- **mcp-tools:**
  - no enforcement statement and no failure paths;
  - the "workspace copy" it says takes precedence has no location;
  - it has no ownership class, though admiral rewrites the file;
  - it claims pipeline users that do not reference it.
- **gates.yaml and the gatekeeper:** G-2 to G-7, G-9 and G-12 reproduced.
- **harness/hooks README:**
  - H-5, H-6, H-7 and N-10;
  - it says the heartbeat writes `_state.md`, but the code writes `_lock.md` and
    `_latest.md`.
- **delivery-template:** D-13 and D-14.

## Scores by dimension

Rounds 2 and 3 score each executed surface as the mean of six dimensions.

| Harness | R2 | R3 | | Gates | R2 | R3 | | Orchestrators | R2 | R3 |
|---|---:|---:|---|---|---:|---:|---|---|---:|---:|
| Correctness | 70 | 75 | | Correctness | 84 | 86 | | Executability | 55 | 68 |
| Adversarial robustness | 48 | 57 | | Adversarial robustness | 70 | 74 | | Contract fidelity | 60 | 64 |
| Failure direction | 75 | 80 | | Internal consistency | 84 | 84 | | Termination | 70 | 72 |
| Test adequacy | 50 | 56 | | Cross-file | 76 | 76 | | Cross-orchestrator | 48 | 56 |
| Performance | 86 | 83 | | Test adequacy | 66 | 68 | | Tool fidelity | 60 | 60 |
| Doc–code | 62 | 64 | | Error messages | 84 | 84 | | Context economy | 35 | 35 |

**Pipelines.** Unchanged in both rounds: correctness 76, mutation robustness 62,
internal consistency 78, cross-file 70, test adequacy 60 and error messages 85,
for a mean of 71.8.

**Context economy.** Before its first delegation on a full-lifecycle request,
admiral requires about 1,400 lines (about 17k words) of mandatory reading. A
resume requires about 950.

**Round 1 scorecard.** Five dimensions per surface:

| Surface | Coverage | Consistency | Enforcement | Safety | Operability | Score |
|---|---:|---:|---:|---:|---:|---:|
| Skills | 94 | 92 | 88 | 91 | 85 | 90 |
| Doctrines and protocols | 93 | 91 | 86 | 92 | 78 | 88 |
| Pipelines | 95 | 96 | 95 | 91 | 88 | 93 |
| Review gates | 96 | 96 | 97 | 95 | 86 | 94 |
| Harness | 92 | 90 | 91 | 91 | 71 | 85 |
| Orchestrators | 94 | 92 | 89 | 92 | 78 | 89 |

## Strengths

These were verified by execution in round 2 and still hold in round 3.

- **`save_run.py`.**
  - Lock ownership, `block --reason`, stale-lock `recover`, `complete`/`--reopen`
    and evidence re-hashing all behave exactly as admiral documents them.
  - A crash injected after `_lock.md` was published recovered to a coherent
    state.
  - Six concurrent checkpoints produced exactly one winner.
- **Gate containment.**
  - Traversal, absolute, drive, UNC, cross-run and artifact-symlink paths are
    refused.
  - Duplicate keys, a bad schema, and NaN or bool exit codes fail loud with exit 2.
  - REVISE packets group failures by owner.
- **Analyser breadth.**
  - These are all handled correctly: redirects, `tee`, `dd`, `sed -i` and
    `perl -pi`; wrappers, `eval`, `sh -c` and here-strings; globs, case changes,
    `..`, symlinks and `cd` chains.
  - Scanning is linear-time.
- **Reference integrity.** Across about 1,000 links, paths, flags and symbols,
  none is broken.
- **Candour.** Nearly every doctrine carries an enforcement-status table, and
  most of their errors are understatements, which is the safe direction.
- **Tier 0 and caps.** The fast path is tightly bounded, and the cap of 2 and its
  escalation are applied uniformly.
- **Pipelines and gates.** Round 1 found these the most traceable part of the
  system, thanks to:
  - machine-readable stage ownership and dependencies, conditional stages,
    fan-out, delegates and closing boundaries;
  - typed evidence, artifact hashes and sanctioned applicability records;
  - revision-aware reuse.

## Recommended remediation order

1. **N-1, N-2, N-5: regressions and record lifts.**
   - Judge an extract by the path each member lands at after
     `--strip-components`, `--transform` and `-P`, and refuse symlink members.
   - Read `cp -T` / `--no-target-directory` as a contents copy.
   - Extend the root-extract member listing to `.claude/`, the hook files and the
     blocked globs, whether or not an Admiral run is active.
2. **N-3, N-4.**
   - Treat `git clean` as aimed at the root when it is given a pathspec that is
     not a plain relative path, or `-c clean.requireForce=false`.
   - Add `git stash -u` and `git stash --all` to the root record reach.
3. **H-5.** Read text piped into a shell, and the arguments of `watch` and of
   `system()`-style interpreters, the way `bash -c` already is.
4. **G-2, G-3.**
   - Strip a BOM and normalise quoted keys in `_gatecheck`.
   - Add mutation tests that fail when the spec is weakened.
5. **P-1, P-2.**
   - Provide a sanctioned carry-forward for repeat deploys.
   - Accept the typed applicability record for `security_seed`.
6. **O-4/D-1, D-2, D-3, O-5.**
   - Reconcile the state machine with the run phase states, and add a
     reachability test.
   - Make the Taste example pass the checker.
   - Stop `--prior` from reusing a phase verdict at the cross-stage boundary.
7. **O-2, O-3, O-7 and verdict ownership.**
   - Fix the adapters and assign a `taste_snapshot` producer.
   - Give every self-check one form that runs from the project root.
   - Correct the cso and security-review verdict attribution.
8. **The 20 surviving 09-18 ledger items.** Clear them, then re-run the rubric.

## Remediation history

**Round 1 (`98976d4`).** All four findings were resolved (see [Resolved](#resolved)).
After the fixes, the hook suite passed 928 tests and skill-creator passed 160.

**Round 2 (`3f5ac35`, `a72795a`, `ac263cc`).** O-1, H-1, H-2, H-3, H-4 and G-1
were resolved, each with a regression test that fails on the pre-fix code.
Together those tests produced 53 failures and 2 errors on the old code.

| Finding | Regression test |
|---|---|
| O-1 | `validation/test_save_prose.py` |
| H-1, H-3 | `test_guard_rules.DirectoryDepositTests` (record deposits, tree writes and their neighbours) |
| H-2 | `DirectoryDepositTests` (variable spellings), `test_guard_cmdscan` |
| H-4 | `test_guard_harness_files`, `test_pre_tool_entry.PoisonedHelperTests`, `EntryPointTests` |
| G-1 | `test_gate_run_layout` (depths 1 to 6; a schema-1 package with an open Critical) |

**Root-level follow-up (`8eae856`).** Rule C now reads a command aimed at the
project root by what it would remove or land in the record directories, but only
while a record exists. The cases it reads:

- `git clean -d` with `-x` or `-X`, or without them when the directory is not
  git-ignored;
- `rsync --delete`;
- an extract whose tar or zip members land there. An archive the guard cannot
  read is refused;
- a contents copy whose source holds a record, or is not named or not on disk.

`-e` and `--exclude` lift the refusal. At the owner's request:

- a freeze no longer refuses an archive unpacked at the project root;
- Rule F refuses one only while an Admiral run is active.

`test_guard_rules.RootExtractTests` and `RootRecordReachTests` cover it; they fail
21 times on the previous commit. Round 3 found the follow-up only partly closed
(N-1 to N-10).
