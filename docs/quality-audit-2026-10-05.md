# Supreme Team quality audit and benchmark — 2026-10-05, round 3

## Executive verdict

**Overall: 78/100, up from 76.** All seven suites pass (2,308 tests on
Python 3.13), as do the validators and the pinned lint. All 22 root-level skills
register with the host.

Round 3 is a re-measurement of commit `8eae856`, which carries the round-2
remediation (O-1, H-1 to H-4, G-1 and the root-level-write follow-up). It confirms
that those six fixes hold. It also finds that the last of them, the root-level
follow-up, is not closed. Four new Major bypasses, N-1 to N-4, each lift a freeze
in one allowed command. Two Majors, N-1 and N-5, are regressions introduced by
`8eae856` itself. Every other Critical and Major left open in round 2 is still open.

| Surface | Round 3 | Round 2 (10-01) | What moved it |
|---|---:|---:|---|
| Skills (rubric, 53) | **97.5** (min 94) | 97.8 (min 94) | No rubric-visible change; 20 of the 26 deductions in the 09-18 ledger are still present |
| Doctrines, protocols and contracts (15) | **93.1** (min 78) | 89.7 (min 80) | None of these files changed since round 2, so the rise is scorer variance, not improvement |
| Pipelines | **71.8** | 71.8 | No pipeline or gate-spec file changed; P-1, P-2 and the G-3 mutations re-reproduced |
| Review gates | **78.7** | 77.3 | G-1 fixed; G-2 to G-13 unchanged |
| Harness (hooks and guard) | **69.2** | 65.2 | H-1 to H-4 fixed; N-1 to N-5 found, two of them regressions |
| Orchestrators (procedural) | **59.2** | 54.7 | O-1 fixed in all 12 lead skills; O-2, O-3, O-5 and O-7 remain |
| **Overall** (equal weight) | **78/100** | 76 | 77.7 with the doctrine row held at its round-2 value |

Like round 2, every score here is a model judgement against a stated method, not
machine output. The durable output is the set of cited, reproduced findings. The
totals only summarise them.

The doctrine row shows how large scorer variance can be. None of the 15 doctrine
and contract files changed between the rounds (`git diff f232d7c 8eae856` touches
none of them). Even so, single files moved by as much as 6 points, from −2 for
workflow-protocol to +6 for grill-me, performance-doctrine and
universal-frameworks. A move of that size on one artefact is therefore not a
trend.

## Scope and method

- **Commit.** `8eae856`, read-only. Every probe ran in copies of the checkout
  under a scratch directory.
- **Benchmark.**
  - The seven suites ran sequentially on Python 3.13.14 with PyYAML 6.0.1.
  - The CI "without PyYAML" leg (validation, scripts and gates) ran in a bare venv.
  - The three validators ran, plus `ruff==0.16.9`, the version CI pins.
  - Hook latency was measured as a host invokes it: one cold process per call.
  - Two paid measurements ran against the live host:
    - the routing eval, `trigger_eval.py --mode both --paraphrase --per-skill 4`;
    - host registration, `run_eval.py --registration`.
- **Seven independent auditors**, run in parallel:
  - five skill groups, scored on the rubric in
    `skills/skill-maker/skill-reviewer/references/scoring-rubric.md`;
  - one for the spec, harness and doctrine artefacts, using six contract
    dimensions and spec mutation;
  - one re-verifier, who re-ran every round-2 reproduction and made about 130
    new guard probes against `8eae856`.
- **Verification.**
  - A finding counts only when it is cited on both sides: the claim and its
    source of truth.
  - Each is marked CONFIRMED when reproduced, or PLAUSIBLE when only reasoned
    from the code.
  - The lead auditor reproduced N-1 and N-2 independently. N-1 was executed
    for real: after the extract, `guard_state.py status` printed `frozen: -`.
  - Where two auditors disagreed (G-10), the lead re-read the code; see the
    status table.

## Benchmark results

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

- **Totals.** 2,308 tests with PyYAML, all passing. Round 2 had 2,284; the 24
  new tests are the round-2 regression tests in hooks (+22), gates (+1) and
  validation (+1).
- **Timing caveat.** The installers suite (86.7 s, against 48.4 s in round 2)
  and the taste suite ran while the routing eval and the auditors were also
  running. Read their wall times as an upper bound.
- **Hook latency.** Cold process, n=40 per row:

  | Hook and input | Median | p95 |
  |---|---:|---:|
  | `pre_tool_use.py`, no boundary (read / write) | 81 / 84 ms | 101 / 94 ms |
  | `pre_tool_use.py`, freeze recorded (read / denied write) | 84 / 82 ms | 103 / 106 ms |
  | `pre_tool_use.py`, a 9.5 KB chained command | 127–130 ms | 169–175 ms |
  | `post_tool_use.py` | 80 ms | 99 ms |
  | `user_prompt_submit.py` | 59 ms | 75 ms |

  A bare interpreter starts in 14 ms. The new archive listing is the one
  non-linear cost: a 150,000-member tar costs about 3.1 s per call, and a
  compressed archive is decompressed in full with no size cap (N-9).
- **Floor behaviour.** Under Python 3.11 (this container's `python3`),
  `check_runtime.py` correctly prints `Ready: no`. The gatekeeper wrappers still
  crash with `AttributeError: … is_junction` instead of reporting the floor (G-12).
- **Static profile.**

  | Measure | Value |
  |---|---|
  | `SKILL.md` length | mean 197 lines, median 171, max 468 (`skill-maker`) |
  | Description length | mean 516 chars, max 600, none above the 1,024 host limit |
  | Skills with no `references/` | `audit-improve` only |
  | Code size | 23.0k lines of non-test Python, 33.9k lines of tests in 68 modules |

## Routing and registration

**Routing, round 10: 278/311 = 89.4%**, measured on the 53-skill roster for
$4.81. Round 9, on 09-18 with 52 skills, measured 94.8%.

- **By corpus.** Advertised 188/210 (89.5%); routed 90/101 (89.1%). Both
  corpora are paraphrased.
- **Owner credit.** 15 correct answers were credited because the chosen skill is
  the expected skill's declared delegating owner (`via_owner`).
- **Misroute clusters:**
  - `build/debugger` → `investigate`: 4.
  - Build specialists → `admiral`: 5 (`bob-the-builder` ×3, `test-builder`,
    `qa-only`). `admiral` is the documented front door for a cold request
    (`routing-doctrine.md`), but it is not the declared owner of a build
    specialist, so the scoring rule does not credit these. If it did, the score
    would be 283/311 (91.0%). That is a question about the scoring rule, not a
    re-score.
  - `skill-maker/skill-reviewer` asked as plain English ("is this good enough to
    go live", "go over this thing I wrote for you"): 3, to `code-chief`, `ship`
    and `qa-only`.
  - `open-browser` → `browse`: 2.
  - Design leads among themselves (`commander`, `planner`, `engineer`,
    `architect`, `researcher`): 5.
- **Reading the drop.** The paraphrases are regenerated on every run, and the
  roster gained `audit-improve` (the one skill with no `## Use This Skill When`,
  so its triggers come from its description). One run cannot separate those
  causes from catalog drift. A repeat run would be needed to give a variance
  band.

**Registration:**

- All 22 root-level skills registered against a control session that had no
  catalog installed.
- `review/code-review` is shadowed by the host's own `code-review`. It is a
  nested specialist that is not meant to register, and the name collision is
  harmless.
- The 30 nested specialists did not register, as designed. 18 of them are named
  in `routing-doctrine.md`, which reaches them by path.
- Round 1 measured 20 of 21, because of a stale user-level copy. This host had
  none.

## Status of the round-2 findings

### Claimed fixed in round 2

| Id | Re-run | Status |
|---|---|---|
| O-1 | The old `--owner commander` form is still refused. The documented `--owner admiral --set delegated_to=commander` is accepted. All 19 documented checkpoint commands name the lock holder. | **Fixed** |
| H-1 | Under a freeze, every one of these is denied, and so is the follow-on frozen write: `cp`, `install`, `rsync`, `cp -t`, `ln -sf`, `tar -C .harness-state`, `cd .harness-state && cp … .`, and the `.claude/` copy. | **Fixed** |
| H-2 | `$PWD`, `${PWD}`, `$OLDPWD`, `$CLAUDE_PROJECT_DIR` and an unknown variable are all resolved or denied. | **Fixed** |
| H-3 | `find src -exec sed -i`, `rsync --delete … src/`, `tar -C src` and `git clean -fdx skillset-saves` are denied. | **Fixed** (root-level spellings: N-1 to N-4) |
| H-4 | Appends to `save_taxonomy.py` and `data_formats.py` are denied. A poisoned module still lets the guard deny, and the guard records the `SystemExit`. | **Fixed** |
| G-1 | A schema-1 package with an open Critical is refused at depth 3 and at depth 10. | **Fixed** |
| Root-level writes | The baseline cases in `RootExtractTests` and `RootRecordReachTests` are denied, but many other spellings get through (N-1 to N-8). | **Partly fixed** |

### Open Critical and Major findings: all still present

| Id | Re-run result |
|---|---|
| H-5 | `echo 'rm -rf /' \| sh`, `watch 'rm -rf /'`, `perl -e 'system("rm -rf /")'` and `python3 -c 'import os; os.system("rm -rf /")'` are allowed. |
| G-2 | With a BOM, `'revision'` or `"revision"`, two different revisions still report `REVISION_COHERENT PASS`. |
| G-3 | Each of three weakening edits to `gates.yaml` passes every validator and suite. |
| P-1 | Carrying forward a repeat deploy gets `artifact references another run` ×2. |
| P-2 | `"n/a"` passes for `security_seed`; the typed applicability record gets `evidence not waivable`. |
| O-2 | The adapters still tell the agent to write the run records directly, and Rule C denies that write. |
| O-3 | Nothing produces `taste_snapshot` for an ordinary design run. |
| O-4 / D-1 | `TASTE_ACTIVE` is reachable only from `TASTE_GATE_REVISE`. `investigation-review` has no COMPLETE edge. `GATE` has no transition to BUILD or REVIEW. |
| D-2 | The phase states the runs record are not mapped to the protocol's states. |
| D-3 | The Taste worked example fails the checker on `residual_uncertainty`. |
| O-5 | Now **CONFIRMED**: with the phase verdict as `--prior`, the checker returns `prior_reusable: true` and `changed_evidence: []`, so the cross-stage gate re-judges nothing. |

### Minor findings

| Status | Findings |
|---|---|
| Still present | H-6 to H-11; G-4 to G-7, G-9, G-11, G-12, G-13; P-3 to P-6; O-6 to O-17; D-4 to D-9, D-12 to D-17, D-19 to D-22 |
| Still present (G-8) | A BOM manifest fails closed but is misparsed: a JSON one gets 14 bogus "missing" errors, and a YAML one is read as having no schema version |
| Still present (G-10) | The auditors disagreed; the lead re-read `check.py:804-814`. A top-level `result: pass` beside `exit_code: 1` is refused, and was refused before round 2 too. A nested `result: {status: pass, exit_code: 1}` and `themes: [None]` still pass |
| Partly fixed | D-10: `save-protocol.md` lists 11 classifications, but `routing-doctrine.md` still lists 6 |
| Fixed | D-11 in `save-protocol.md` (13 audit events). `admiral/SKILL.md:240` still says "exactly eleven" (O-10) |

## New findings on `8eae856`

| Id | Sev | Finding | Status |
|---|---|---|---|
| N-1 | Major | An extract whose member names the guard reads literally can still land in the records. Spellings that get through: `tar --strip-components=1`, `--transform 's,^,.harness-state/,'`, `-xPf` with absolute names, and a symlink member (`lnk -> .harness-state`, then `lnk/guard-state.json`). **Regression:** the strip-components spelling was denied on `ac263cc`. | CONFIRMED (lead re-ran it; freeze lifted) |
| N-2 | Major | `cp -rT backup .` and `cp --no-target-directory` copy a backup over the root. Only the `x/.` spelling is read as a contents copy. | CONFIRMED (lead) |
| N-3 | Major | `git clean` has several holes. Pathspecs `:/`, `'*'` and `':(glob)**'` get through. An `-e` pattern is judged by its first segment only. `-c clean.requireForce=false clean -dx` needs no `-f`. The ignore-file reading skips `!` lines and treats a partial path as ignoring the whole directory. | CONFIRMED |
| N-4 | Major | `git stash --all` removes both record directories, even with the shipped `.gitignore`. `git stash -u` does the same when the records are not ignored. | CONFIRMED |
| N-5 | Major | Under a freeze or block with no Admiral run, a root `unzip` that carries `.claude/settings.local.json` (setting `disableAllHooks`), a hook file or a blocked path is allowed. All of these were denied on `ac263cc`. The README states the trade as deliberate, but Rule C already lists the archive members and could cover these paths. **Regression.** | CONFIRMED |
| N-6 | Minor | Rule C does not refuse `rsync --delete` at the root when the command also uses `--delete-excluded`, a partial-path exclude, or `--include` before `--exclude`. A freeze still blocks these. | Decision CONFIRMED; effect PLAUSIBLE (no rsync here) |
| N-7 | Minor | Rule C does not read `find . -name guard-state.json -delete` at the root. | CONFIRMED |
| N-8 | Minor | Extractors the guard does not know: `jar xf`, `python3 -m zipfile -e`, `bsdtar`, `gtar`, `pax`, `cpio`. A tar+zip polyglot gets through, as does an archive swapped earlier in the same command and a destination built at run time (`"$(pwd)"`, `~+`). | CONFIRMED |
| N-9 | Minor | False positives: `cd src && git clean -fdx` and `cd docs && unzip ../a.zip` are denied as "aimed at the project root", and so is `tar -xOf`. The archive listing is unbounded (above). | CONFIRMED |
| N-10 | Minor | Several documents claim more than the code does: the hooks README says `echo "rm -rf /"` is denied, but it is allowed. The round-2 report says "the root-level gap is now closed". A blocked-glob denial message says "frozen boundary". The `guard` and `freeze` skill docs do not mention the root-extract exemption. | CONFIRMED |

## Skills: rubric scores (53)

Mean **97.5**, median 98, min **94**. Five skills score 100, 46 score 95–99
and two score 94. There are 121 cited deductions across 48 skills.

| Group | Scores |
|---|---|
| Admiral layer | admiral 95 · gatekeeper-admiral 98 |
| Design | commander 97 · researcher 99 · **planner 100** · architect 98 · **engineer 100** · gatekeeper-design 96 · redesign 95 · design-mapper 97 · prototyper 98 |
| Build | build-management 98 · bob-the-builder 99 · test-builder 98 · security-builder 99 · cross-check-build-confirm 96 · debugger 98 · health-check 95 · gatekeeper-build 99 |
| Review | code-chief 97 · bug-review 97 · code-review 96 · quality-review 98 · security-review 97 · **cso 94** · **mr-robot 94** · frontier 97 · design-qa 97 · devex-review 96 · gatekeeper-code 96 |
| Cross-cutting | investigate 97 · skill-maker 97 · skill-creator 97 · skill-reviewer 98 · session-memory 97 |
| Taste | taste 97 · **taste-review 100** |
| Standalone | audit-improve 97 · browse 98 · open-browser 99 · setup-browser-cookies 98 · pair-agent 99 · ship 98 · **land-and-deploy 100** · setup-deploy 99 · **document-release 100** · guard 96 · careful 98 · freeze 98 · unfreeze 97 · qa 97 · qa-only 98 · benchmark 98 |

The full ledger, one line per deduction, is in
[BENCHMARK.md](../BENCHMARK.md#skills). The patterns that recur across skills:

- **Self-check commands that cannot run as written (O-7 family).** commander,
  redesign, code-chief, build-management and gatekeeper-code all pair a
  phase-relative `--package <phase>/manifest.json` with a project-relative
  script path. Run from the project root, as admiral instructs, the check exits 2.
- **Verdict ownership misattributed.**
  - cso, mr-robot and security-review say cso issues the `security-review`
    verdict. The protocol and `pipelines.yaml` give it to gatekeeper-admiral.
  - gatekeeper-code asks code-chief to "run the CSO lens", which the review
    pipeline has no stage for.
- **Read-only postures claimed but not enforced (SB-14, SB-5).** Six review
  lenses and cross-check-build-confirm still hold Write and Bash, and none of
  them records a read-only boundary.
  - devex-review states that a write escaping an install step is denied. The
    guard does not see scripts that a command runs.
- **Owner releases.** guard and freeze say only the owner can release a
  boundary, but `guard_state.py` also accepts approvers. unfreeze says the
  opposite for read-only records, which store no approvers.
- **Worked examples that fail the real tools.**
  - cso Example 4 fails `check.py` four times.
  - Two session-memory commands are refused by `save_run.py`.
  - The quarantine record in test-builder fails the findings shape.
  - The design-mapper example omits the `mock_parity` binding, so the gate
    would reject it.

**The 09-18 ledger.** Of its 26 deductions, 20 are still present, 2 are partly
fixed (the admiral audit trail and the taste flat-map import) and 4 are fixed
(engineer, ship, gatekeeper-build and taste-review). Round 2 counted taste and
the unfreeze glob item as fixed. This round reproduced a remaining taste case
and found the unfreeze approver claim still in `SKILL.md:49`.

## Spec, harness and doctrine artefacts

Scored on six contract dimensions (authority, enforcement, internal consistency,
cross-consistency, completeness, actionability), normalised to 100.

- **The 21 artefacts BENCHMARK.md tracks:** mean **94.0**. The 09-18 figure was
  97.5.
- **With `mcp-tools.md` added:** mean **93.4** across 22.

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

The largest deductions:

- **workflow-protocol: the O-4/D-1/D-2 state machine.**
  - Taste states are unreachable.
  - `design-to-build` and `build-to-review` cannot be walked through `GATE`.
  - The run phase states are unmapped.
  - The SAFETY owner list omits `careful`.
- **mcp-tools.**
  - No enforcement statement and no failure paths.
  - The "workspace copy" it says takes precedence has no location.
  - No ownership class, though admiral rewrites the file.
  - It claims pipeline users that do not reference it.
- **gates.yaml and the gatekeeper.**
  - G-2 to G-7, G-9 and G-12 reproduced.
  - The findings record "requires an id" that the checker never reads.
- **harness/hooks README.**
  - The `echo "rm -rf /"` claim and the H-5 claim (N-10).
  - The H-6 and H-7 gaps.
  - The heartbeat is said to write `_state.md`; the code writes `_lock.md` and
    `_latest.md`.
- **delivery-template.**
  - The destination command exits 1 without `--name` (D-13).
  - The example uses Tier 1 for a gated edit (D-14).
  - The anchored-copy counts say 10 of 91; the comparator gives 9 of 91.
- **universal-frameworks.** Two comparators are denied that exist:
  `test_docs_inventory.py:278` opens the file, and the workflow-protocol
  enforcement table is called "judgement".

## Scores by dimension

| Harness | R2 | R3 | | Gates | R2 | R3 | | Orchestrators | R2 | R3 |
|---|---:|---:|---|---|---:|---:|---|---|---:|---:|
| Correctness | 70 | 75 | | Correctness | 84 | 86 | | Executability | 55 | 68 |
| Adversarial robustness | 48 | 57 | | Adversarial robustness | 70 | 74 | | Contract fidelity | 60 | 64 |
| Failure direction | 75 | 80 | | Internal consistency | 84 | 84 | | Termination | 70 | 72 |
| Test adequacy | 50 | 56 | | Cross-file | 76 | 76 | | Cross-orchestrator | 48 | 56 |
| Performance | 86 | 83 | | Test adequacy | 66 | 68 | | Tool fidelity | 60 | 60 |
| Doc–code | 62 | 64 | | Error messages | 84 | 84 | | Context economy | 35 | 35 |

The pipeline dimensions are unchanged from round 2: correctness 76, mutation
robustness 62, internal consistency 78, cross-file 70, test adequacy 60 and error
messages 85, for a mean of 71.8.

## Recommended remediation order

1. **N-1, N-2, N-5 (regressions and record lifts).**
   - Judge an extract by the path each member lands at after `--strip-components`,
     `--transform` and `-P`. Refuse any symlink member.
   - Read `cp -T` / `--no-target-directory` as a contents copy.
   - Extend the existing root-extract member listing to `.claude/`, the hook
     files and blocked globs, whether or not an Admiral run is active.
2. **N-3, N-4.**
   - Treat `git clean` with any pathspec that is not a plain relative path, or
     with `-c clean.requireForce=false`, as aimed at the root.
   - Add `git stash -u/--all` to the root record reach.
3. **H-5.** Read text piped into a shell, and the arguments of `watch` and
   `system()`-style interpreters, the way `bash -c` already is.
4. **G-2, G-3.** Strip a BOM and normalise quoted keys in `_gatecheck`. Add
   mutation tests that fail when the spec is weakened.
5. **P-1, P-2.** Provide a sanctioned carry-forward for repeat deploys, and
   accept the typed applicability record for `security_seed`.
6. **O-4/D-1, D-2, D-3, O-5.**
   - Reconcile the state machine with the run phase states and add a
     reachability test.
   - Make the Taste example pass the checker.
   - Stop `--prior` from reusing a phase verdict at the cross-stage boundary.
7. **The O-7 family and verdict ownership.**
   - Give every self-check one runnable form from the project root.
   - Correct the cso/security-review verdict attribution and the gatekeeper-code
     "CSO lens".
8. **Clear the 20 surviving 09-18 ledger items**, then re-run the rubric.
