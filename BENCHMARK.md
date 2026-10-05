# Benchmark

Measured state of the Supreme Team catalog: what scores what, how each number was
produced, and what it does not cover. Every figure here was observed, not
estimated. Where a measurement was not taken, this file says so rather than
inferring one.

**When these were measured.** On 2026-10-05, at commit `8eae856`, on the 53-skill
catalog. This is round 3, and it re-measured every skill, artefact and paid figure
on this page. The full report, including the adversarial findings behind the
scores, is in [docs/quality-audit.md](docs/quality-audit.md). That file
consolidates all three audit rounds and gives the current status of every
finding.

The two kinds of number need different handling:

- The rubric scores are model judgements, not machine output.
- The routing accuracy is a paid, networked measurement.

CI re-runs neither, so nothing keeps them true. A number older than the catalog it
describes should be read as history. Test counts are not recorded in this file;
[Tests](#tests) gives the commands that produce them.

## Headline

| Dimension | Result |
|---|---|
| Skill quality, 53-skill catalog | mean **97.5** / 100, median 98, lowest 94, 5 at 100 |
| Spec, harness and doctrine, 21 artifacts | mean **94.0** / 100, lowest 78 (`contracts/workflow-protocol.md`) |
| Routing accuracy, paraphrased requests, 53-skill roster | **89.4%** (278/311) |
| Skills a host registers by name | 22 of 22 at the catalog root; the 31 nested specialists are reached by path |
| Automated tests | seven suites, run by CI; [Tests](#tests) has the command for each, and the count is what a run prints |
| Gate boundaries | 10, all proven satisfiable against the real validator |

Every headline number moved down from the 2026-09-18 revision (99.4, 97.5 and
94.8%). Most of that is not the catalog getting worse:

- **Skills.** Most of the 09-18 deductions were never fixed. The 09-18 ledger
  called them fixed without re-scoring, and this round re-scored them.
- **Spec and doctrine.** None of those files changed between the round-2 audit
  and this round. The adversarial rounds reproduced defects in them that the
  09-18 scoring did not.
- **Routing.** The measurement is noisy, and why it fell is under [Routing](#routing).

## Skills

Scored against the 10-dimension rubric in
[`skills/skill-maker/skill-reviewer/references/scoring-rubric.md`](skills/skill-maker/skill-reviewer/references/scoring-rubric.md):
trigger, scope, depth, style, progressive disclosure, examples, edge cases,
security, structure, documentation — 10 points each.

| Band | Skills |
|---|---|
| 100 | 5 |
| 95–99 | 46 |
| below 95 | 2 |

<details>
<summary>Per-skill scores</summary>

| Skill | Score |
|---|---|
| `design/engineer` | 100 |
| `design/planner` | 100 |
| `document-release` | 100 |
| `land-and-deploy` | 100 |
| `taste/taste-review` | 100 |
| `build/bob-the-builder` | 99 |
| `build/gatekeeper-build` | 99 |
| `build/security-builder` | 99 |
| `design/researcher` | 99 |
| `open-browser` | 99 |
| `pair-agent` | 99 |
| `setup-deploy` | 99 |
| `benchmark` | 98 |
| `browse` | 98 |
| `build/build-management` | 98 |
| `build/debugger` | 98 |
| `build/test-builder` | 98 |
| `careful` | 98 |
| `design/architect` | 98 |
| `design/prototyper` | 98 |
| `freeze` | 98 |
| `gatekeeper-admiral` | 98 |
| `qa-only` | 98 |
| `review/quality-review` | 98 |
| `setup-browser-cookies` | 98 |
| `ship` | 98 |
| `skill-maker/skill-reviewer` | 98 |
| `audit-improve` | 97 |
| `design/commander` | 97 |
| `design/design-mapper` | 97 |
| `investigate` | 97 |
| `qa` | 97 |
| `review/bug-review` | 97 |
| `review/code-chief` | 97 |
| `review/design-qa` | 97 |
| `review/frontier` | 97 |
| `review/security-review` | 97 |
| `session-memory` | 97 |
| `skill-maker` | 97 |
| `skill-maker/skill-creator` | 97 |
| `taste` | 97 |
| `unfreeze` | 97 |
| `build/cross-check-build-confirm` | 96 |
| `design/gatekeeper-design` | 96 |
| `guard` | 96 |
| `review/code-review` | 96 |
| `review/devex-review` | 96 |
| `review/gatekeeper-code` | 96 |
| `admiral` | 95 |
| `build/health-check` | 95 |
| `design/redesign` | 95 |
| `review/cso` | 94 |
| `review/mr-robot` | 94 |

</details>

<details>
<summary>Deductions cited in the 2026-10-05 round — 121 findings across 48 skills</summary>

Every line was checked against the cited source before it cost a point, and most
were reproduced by running the tool the claim is about. Five skills scored clean.
This is the ledger of that round and is not edited afterwards. When a finding is
fixed, the fix is recorded in the changelog and the score changes only at the next
re-score.

Abbreviations: `SB-14` means a lens claims allowed-tools enforces a read-only
posture while it holds Write and Bash. `O-7` means a self-check pairs a
phase-relative `--package` with a project-relative script and exits 2 from the
project root. Paths are under `skills/`.

| Skill | Findings |
|---|---|
| `admiral` | D3 −2: "exactly eleven" audit events and trail appends that `save_run.py` never emits (13 events; trail not appendable) (SKILL.md:240, failure-modes.md:37, workflow.md:55 vs save_run.py:819). D3 −1: save-directory classifications counted as ten, with a stray `conflict` (stub-contract.md:68, agent-protocol.md:57,60 vs _saves.py:33). D6 −1: example appends `LATEST_POINTER_REBUILT` to the trail (examples.md:45 vs agent-protocol.md:59). D8 −1: adapters write the run records directly (adapters/claude.md:48, copilot.md:76 vs save-ownership.yaml:119-131) |
| `gatekeeper-admiral` | D3 −1: claims `candidate_ids` is cross-checked (boundary-evidence.md:59 vs check.py:717-756). D3 −1: the `--prior` reuse rule lets the cross-stage pass re-judge nothing (SKILL.md:165-167, reproduced) |
| `design/commander` | D3 −1: a verdict per phase, where the gate has one phase-gate stage (workflow.md:18 vs pipelines.yaml:94-98). D3 −1: O-7 (SKILL.md:152). D10 −1: intake-brief `required_contracts` do not mirror SKILL.md (intake-brief.yaml:51-55) |
| `design/researcher` | D3 −1: claims the first design stage; `intake-grilling` precedes it (SKILL.md:20,44 vs pipelines.yaml:43-54) |
| `design/architect` | D2 −1: claims the production implementation `ownership.yaml` gives bob-the-builder (SKILL.md:82). D3 −1: taste grilling log attributed to design-mapper; the owner is `taste` (SKILL.md:124 vs ownership.yaml:549) |
| `design/gatekeeper-design` | D3 −2: says the waiver reason is not mechanically checked; `check.py` refuses an unsanctioned reason (boundary-evidence.md:131-136 vs check.py:446-452, reproduced). D3 −1: key-space counts drifted from `check_redesign.py` (key-spaces.md:16,33-53). D6 −1: Example 4 contradicts itself on `mock_rendering` (examples.md:84,92) |
| `design/redesign` | D3 −1: commander or architect "implement it in the real stack" (SKILL.md:39-41 vs ownership.yaml:175). D3 −1: O-7 (SKILL.md:198). D6 −1: no merge-decision example. D9 −1: "eight delegations" vs a ten-row table (stub-contract.md:13-33). D10 −1: mirror comment cites the wrong section (intake-brief.yaml:74) |
| `design/design-mapper` | D3 −1: parity marker required in both files; `check_parity.py` accepts either (workflow.md:95 vs check_parity.py:201-204). D3 −1: hand-writes the aggregate record its own rules forbid (SKILL.md:105 vs :140). D6 −1: the aggregate example has no `inputs`, so the design gate would send it back (examples.md:136-149) |
| `design/prototyper` | D3 −1: "architect implements the chosen variant" (workflow.md:208 vs ownership.yaml:175). D8 −1: self-check scratch in the `harness-tests` path class (SKILL.md:154,222 vs save-ownership.yaml:220-228) |
| `build/build-management` | D3 −1: a deferred Major needs a reopen trigger as well as status and owner (gate-evidence.md:27 vs gates.yaml:313). D3 −1: O-7 (SKILL.md:134) |
| `build/bob-the-builder` | D9 −1: cites `_validate_package_dir`, which does not exist (contracts.md:24-26 vs _gatecheck.py:379) |
| `build/test-builder` | D3 −1: the quarantine record "travels into findings" without the `id`/`severity`/`status` the shape requires (contracts.md:66-69 vs gates.yaml:313). D6 −1: a pytest-style id in a unittest example (examples.md:115) |
| `build/security-builder` | D1 −1: the description names `review/security-review` as a delegator; the body and pipeline do not (SKILL.md:9-11 vs :45-47) |
| `build/cross-check-build-confirm` | D3 −1: says one unproven row "fails the machine"; the gate checks presence only (workflow.md:86-89 vs gates.yaml:11). D6 −1: Example 5 waives via an artifact-backing exemption that does not apply (examples.md:137-141). D8 −1: SB-5 (SKILL.md:83). D9 −1: points to a table "below" that does not exist (workflow.md:56) |
| `build/debugger` | D6 −1: the only repro step names a torn-down script (examples.md:61,95). D6 −1: Example 2 uses the "find the root cause" trigger the skill routes to `investigate` (examples.md:12) |
| `build/health-check` | D3 −1: says only taste-review adds boundary fallbacks; redesign-review declares four (contracts.md:86-88 vs gates.yaml:79). D6 −2: Example 4 passes readiness with a "degraded dependency" (examples.md:92). D9 −2: references to a "ledger above", a "data-only scope" and a "Step 8" that do not exist (SKILL.md:80, workflow.md:78-98) |
| `build/gatekeeper-build` | D9 −1: a comment cites "workflow step 1" for step 2 (scripts/check.py:44) |
| `investigate` | D4 −1: comparison wording that is also false, "debugger no longer advertises 'find the root cause'" (SKILL.md:52). D9 −1: Contents omits Example 0 (examples.md:8-14). D9 −1: names `verdict_investigation-review.json`, which no gatekeeper writes (workflow.md:170) |
| `session-memory` | D3 −1: "LIFE-HARNESS" undefined in the doctrine it cites (SKILL.md:128 vs harness-doctrine.md:88). D6 −2: two example commands are refused by `save_run.py` (examples.md:74,100, reproduced) |
| `review/code-chief` | D3 −1: O-7 (SKILL.md:142). D3 −1: sends single-lens requests to the specialist directly, against `routing-doctrine.md:156` (SKILL.md:54-56). D6 −1: conditional lenses lack `optional: true` (agent-manifest.yaml:47-50) |
| `review/bug-review` | D3 −1: says another packet name leaves the slot empty; `*bug*.md` matches (SKILL.md:63 vs gatekeeper-code check.py:67). D3 −1: `status` required but missing from template and examples (SKILL.md:62,81). D8 −1: SB-14 (SKILL.md:117) |
| `review/code-review` | D3 −1: the packet-name claim (SKILL.md:158 vs check.py:74). D3 −1: `status` missing from template (SKILL.md:84). D6 −1: Example 3 says "go" on an unowned open Major (examples.md:46-52 vs gates.yaml finding_policy). D8 −1: SB-14 (SKILL.md:120) |
| `review/quality-review` | D3 −1: the packet-name claim (SKILL.md:64,169 vs check.py:81). D8 −1: SB-14 (SKILL.md:130) |
| `review/security-review` | D3 −1: cso issues the `security-review` verdict; gatekeeper-admiral does (SKILL.md:121 vs workflow-protocol.md:102). D5 −1: a 103-line examples.md without Contents. D8 −1: no read-only execution-boundary contract (SKILL.md:174-180) |
| `review/cso` | D1 −1: the description claims the `security-review` verdict (SKILL.md:4-5). D6 −3: Example 4 manifest fails `check.py` (doubled `security/` paths; no `submission_id` or `revisions`) (examples.md:58-100, reproduced). D6 −1: Example 5 resubmits a `fail` scan (examples.md:122-127). D7 −1: no ESCALATE for a failed scan with no authorized fix (SKILL.md:212) |
| `review/mr-robot` | D8 −1: SB-14 (SKILL.md:163). D8 −1: says cso authorizes probing; the target's owner does (workflow.md:70 vs probe-protocol.md:38). D6 −2: Example 5's 500 paired requests vs one per class (examples.md:80-82). D6 −1: Example 1 assigns a key this lens does not own (examples.md:23). D3 −1: the cso verdict claim (SKILL.md:114) |
| `review/frontier` | D9 −1: Contents numbered 1,2,3,4,3,4,5 (workflow.md:9-15). D8 −1: SB-14 (SKILL.md:128). D3 −1: `status` missing from template (SKILL.md:85) |
| `review/design-qa` | D8 −1: SB-14 (SKILL.md:127). D7 −1: the skip rule waives with a reason the stage condition makes false (SKILL.md:149 vs pipelines.yaml). D6 −1: capture counts and tiers do not add up (examples.md:48,72-77) |
| `review/devex-review` | D8 −1: says a write escaping an install step is denied; scripts a command runs are not seen (SKILL.md:154 vs guard_hook.py:688). D7 −1: Rule D denies every package install, which no failure mode covers (SKILL.md:162-166). D3 −1: `status` missing from template (SKILL.md:97). D6 −1: Example 5 drops DX-07 and miscounts (examples.md:79) |
| `review/gatekeeper-code` | D8 −1: SB-22, a code-chief summary fills the `*code*.md` slot (check.py:74, reproduced). D3 −2: asks code-chief to "run the CSO lens", which the pipeline has no stage for (SKILL.md:225,251). D3 −1: script and package paths resolve from different directories (SKILL.md:155,269) |
| `skill-maker` | D3 −1: "a score alone goes straight to the reviewer", against internal-specialist routing (SKILL.md:51). D3 −1: gate-submission.md says a paraphrase both fails and passes, and cites stale lines (gate-submission.md:26-38). D5 −1: a reference link resolves to a non-existent path (gate-submission.md:38) |
| `skill-maker/skill-creator` | D3 −1: skill-maker "owns every stage" (SKILL.md:58 vs pipelines.yaml:429-436). D3 −1: SC-23, `quick_validate.py` accepts a name that differs from its directory and reserved words (SKILL.md:116, reproduced). D9 −1: trigger list omits Optimize (SKILL.md:47-52) |
| `skill-maker/skill-reviewer` | D3 −1: skill-maker owns the `review` stage (SKILL.md:61-63 vs pipelines.yaml:433-436). D9 −1: cites Phase 1.2 for a Phase 1.1 rule (SKILL.md:372) |
| `taste` | D3 −1: a flat import map with an unknown `schema` imports with rc 0 (SKILL.md:180 vs taste_prefs.py:564-566, reproduced). D3 −1: says a shell redirect into the store is not denied; Rule C denies it, while a global-store Write is allowed (SKILL.md:154,189). D5 −1: a 193-line workflow.md without Contents |
| `audit-improve` | D1 −2: the description omits the body's trigger phrasings and the `investigate` exclusion (SKILL.md:6). D3 −1: "the appropriate" class and self-check are never named (SKILL.md:40-43,86-87) |
| `browse` | D3 −1: 14 tools called "the registered MCP surface"; `mcp-tools.md` ships empty tables (SKILL.md:45). D8 −1: a full HAR is recorded to a relative path with no deletion (workflow.md:83-86) |
| `open-browser` | D3 −1: "no network call" for an `npx` probe that can download (SKILL.md:58) |
| `setup-browser-cookies` | D8 −2: SC-5, the imported-cookie profile has no location rule and no teardown (SKILL.md:60, workflow.md:17) |
| `pair-agent` | D7 −1: hard-codes CDP port 9222 without checking the endpoint is the browser it launched (workflow.md:32-51) |
| `ship` | D3 −2: P-1, the repeat-release carry-forward is refused as "artifact references another run" (gate-submission.md:111-127, reproduced) |
| `setup-deploy` | D3 −1: P-1, later releases "carry forward" artefacts the next gate rejects (SKILL.md:48,69) |
| `guard` | D1 −1: no "even when" cue in the description. D3 −1: says only the owner releases; approvers can too (enforcement.md:160 vs guard_state.py:152-156). D8 −1: the Rule F and freeze claims omit the root-extract exemption; a root `unzip` overwrote a hook file (SKILL.md:71, reproduced). D9 −1: a 372-word bullet (SKILL.md:70) |
| `careful` | D3 −1: says the destructive block fails open on a malformed record; it still denies (examples.md:94, reproduced). D6 −1: `status --json` sample shows 7 keys; the tool prints 11 (examples.md:113-127) |
| `freeze` | D3 −1: owner-only release (enforcement.md:143 vs guard_state.py:152). D8 −1: "blocks any edit or command that touches a frozen path", but a root `unzip` is allowed (SKILL.md:58,89, reproduced) |
| `unfreeze` | D3 −1: SC-10, approver release for read-only records that store no approvers (SKILL.md:49 vs guard_state.py:261-281). D3 −1: says revoking leaves `released_by`; it does not (SKILL.md:102). D6 −1: "seven keys" in `status --json`; there are 11 (examples.md:42) |
| `qa` | D3 −1: qa-only owns the no-fixes fallback; qa does (gate-package.md:66-68 vs gates.yaml evidence_owners). D5 −1: Contents omits Evidence Keys (gate-package.md:8-15). D6 −1: a non-canonical `--prior` verdict path (examples.md:33) |
| `qa-only` | D8 −1: standalone evidence in a skill-maker-owned path class (SKILL.md:54 vs save-ownership.yaml:247-253). D9 −1: bundle shape differs between SKILL.md and read-only-boundary.md |
| `benchmark` | D3 −1: sample size justified with the single-arm band, not the two-arm one (examples.md:57-60). D6 −1: SC-18, "±40 ms" at 60 runs where its own formula gives ±25 (examples.md:61) |

</details>

<details>
<summary>The 2026-09-18 ledger, re-checked: 20 of 26 deductions still present</summary>

The 09-18 round scored 52 skills at a mean of 99.4, with 31 at 100. Its
26 deductions were later described here as fixed "without re-scoring". Two
rounds have since checked them.

| Status | Items |
|---|---|
| Fixed (4) | `design/engineer` stack-lock precondition; `ship` `submission_id` claim; `build/gatekeeper-build` traversal example; `taste/taste-review` `policy_check` |
| Partly fixed (2) | `admiral` audit-trail appends (fixed in SKILL.md and contracts.md, present in three references); `taste` import schema (exit codes and the `entries` form fixed, a flat map still unchecked) |
| Still present (20) | commander intake mirror; redesign mirror comment and merge example; architect and prototyper implementation ownership; prototyper scratch path; researcher "first stage"; design-mapper union rule; investigate Example 0 and verdict file; qa Evidence Keys; qa-only path class and bundle shape; session-memory "LIFE-HARNESS"; skill-creator Optimize trigger; skill-reviewer review-stage owner; unfreeze approver release; security-review Contents and read-only contract; frontier Contents numbering |

</details>

## Spec, harness and doctrine

Scored against six contract dimensions — authority, enforcement, internal
consistency, cross-consistency, completeness, actionability — normalised to 100.
The enforcement dimension asks one question: does this document state accurately
what is machine-checked and what is judgement?

<details>
<summary>Per-artifact scores</summary>

| Artifact | Score | 09-18 |
|---|---|---|
| `contracts/evidence-standards.md` | 98 | 98 |
| `design-doctrine.md` | 98 | 98 |
| `execution-contract.md` | 98 | 98 |
| `grill-me-doctrine.md` | 98 | 98 |
| `save-ownership.yaml` | 98 | 98 |
| `team+runtime+package-manifest` | 98 | 95 |
| `ownership.yaml` | 97 | 97 |
| `performance-doctrine.md` | 97 | 98 |
| `contracts/universal-frameworks.md` | 95 | 98 |
| `save-protocol.md` | 95 | 97 |
| `taste-doctrine.md` | 95 | 98 |
| `harness-doctrine.md` | 94 | 98 |
| `contracts/responsibility-matrix.md` | 93 | 95 |
| `harness/gatekeeper` | 93 | 98 |
| `routing-doctrine.md` | 93 | 95 |
| `contracts/delivery-template.md` | 92 | 98 |
| `contracts/handoff-templates.md` | 92 | 98 |
| `harness/hooks` | 92 | 98 |
| `gates.yaml` | 91 | 98 |
| `pipelines.yaml` | 91 | 98 |
| `contracts/workflow-protocol.md` | 78 | 98 |

`mcp-tools.md`, which the 09-18 round did not score, scores 81. With it the mean
of 22 is 93.4.

</details>

The 09-18 scores were taken by reading. This round ran what could be run, and the
largest drops are where an executed defect contradicts a document:

- **`workflow-protocol.md`.** The state machine has Taste states that are
  unreachable and no COMPLETE edge for an investigation. Its states are not
  mapped to the phase states the runs actually record.
- **`gates.yaml` and `pipelines.yaml`.** These reproduced:
  - P-1: a repeat deploy cannot pass.
  - P-2: the typed record is refused where `"n/a"` passes.
  - G-3: edits that weaken the spec pass every validator.
- **`harness/hooks`.** The README states the guard denies destructive text that
  is piped into a shell. It does not.
- **`handoff-templates.md`.** The Taste worked example fails the checker.

Each is cited in the [findings register](docs/quality-audit.md#findings-register).

## Routing

The catalog is description-routed: a model picks one skill out of 53 by reading
descriptions. That decision is measured by
[`skills/validation/trigger_eval.py`](skills/validation/trigger_eval.py), which
puts the whole roster in front of a real model and scores which skill wins.

Accuracy moved from 84.0% to a peak of 94.8% across nine rounds, and measured
**89.4%** in round 10.

| Round | What changed | Queries | Correct | Accuracy |
|---|---|---|---|---|
| 1 | First paraphrased measurement | 175 | 147/175 | 84.0% |
| 2 | Eight descriptions rewritten | 174 | 150/174 | 86.2% |
| 3 | Trigger surface expanded, corpus nearly doubled | 310 | 283/310 | 91.3% |
| 4 | Gate pair separated; owner-credit scoring corrected | 310 | 290/310 | 93.5% |
| 5 | Guardrail, performance and gate discriminators | 310 | 291/310 | 93.9% |
| 6 | Lenses cede cold phrasings to their owner | 310 | 291/310 | 93.9% |
| 7 | 15 skills flattened so the host registers them | 310 | 277/310 | 89.4% |
| 8 | Collisions the path prefix had masked | 310 | 288/310 | 92.9% |
| 9 | Regression from the previous round corrected | 310 | 294/310 | 94.8% |
| 10 | Re-measured on 2026-10-05; `audit-improve` added to the roster | 311 | 278/311 | 89.4% |

Round 7 is worth reading twice: accuracy *fell* when the directly-invokable
skills moved to the catalog root. The path prefix had been carrying the
discrimination — `safety-guardrails/guard` against `safety-guardrails/careful` —
and the host never displayed it, because those skills were not registered at all.
Every earlier score was measured against a roster showing prefixes no user would
ever see. The lower number is the truer one.

**Round 10.**

- **By corpus.** Advertised 188/210 and routed 90/101. 15 correct answers were
  credited to the declared delegating owner.
- **Misroutes:**
  - `build/debugger` went to `investigate` 4 times.
  - A build specialist asked cold ("just build the feature") went to `admiral`
    5 times. `admiral` is the documented front door for a cold request but not
    the specialist's declared owner, so the owner-credit rule does not credit
    it. If it did, the score would be 91.0%.
  - `skill-maker/skill-reviewer`, asked in plain English, went elsewhere 3 times.
  - `open-browser` went to `browse` 2 times.
  - The design leads were confused among themselves 5 times.
- **Why one run cannot explain the drop.** The paraphrases are regenerated on
  every run, and the roster gained a skill whose triggers come from its
  description alone. The drop from round 9 cannot be pinned on one cause without
  a repeat run. No variance band has been measured.

### Host registration

Claude Code discovers skills at `.claude/skills/<name>/SKILL.md`, one level deep.
The layout follows the routing classes:

- The 22 skills a user may reach directly sit at the catalog root and register.
- The 31 internal specialists stay nested, where the loader does not offer them.

That is "reached only through the owning sub-orchestrator", expressed in the
filesystem.

Nesting costs those specialists nothing, because delegation never used the skill
loader — `admiral` holds `Read`, `Grep` and `Glob` and no `Skill` tool, and
reaches specialists by path.

Measured by [`skills/validation/run_eval.py`](skills/validation/run_eval.py)
`--registration`. It installs the tree into a scratch project and diffs the host's
reported skill list against a control run with no catalog installed. The control
matters: the host ships skills of its own, and a bare name match cannot tell the
catalog's `code-review` from the one Claude Code bundles.

On 2026-10-05 all 22 root skills registered. The host's own `code-review` shadows
`review/code-review`, which is nested and not meant to register. An earlier
measurement got 20 of 21: `skill-maker` was shadowed by a stale copy in
`~/.claude/skills`. That was an environment artifact, and a reinstall clears it.

## Pipelines and review gates

10 pipelines close at 10 gate boundaries, each with its own required
evidence keys (`gates.yaml` lists them). 4 pipelines carry an explicit phase-gate
stage; the rest are judged once, by the cross-stage gatekeeper.

Phase gatekeepers: `gatekeeper-design`, `gatekeeper-build`, `gatekeeper-code`. Cross-stage: `gatekeeper-admiral`.

[`test_pipeline_workflows.py`](skills/validation/test_pipeline_workflows.py)
does not read the spec and compare it. It builds a package per boundary with real
files and real digests, and submits it to `check.py`. All 10 boundaries are proven
satisfiable.

That is not implied by their being internally consistent. A boundary can require
a key that is also barred from fallback and produced by no stage, and every
document involved would still read correctly.

Refusal tests follow, because a generator that only produces passing packages
proves the generator works, not the gate. One test walks a complete run (open, a
checkpoint per stage, submit, verdict, close) and checks that the audit trail
kept an event per stage.

"Satisfiable" means one legitimate package exists, not that every legitimate path
reaches one. The adversarial rounds found two paths that cannot pass:

- a repeat deployment (P-1);
- a design run that records `security_seed` as a typed applicability record (P-2).

They also found that edits weakening the spec pass every test (G-3). See the
[findings register](docs/quality-audit.md#findings-register).

## Orchestration

[`test_orchestration.py`](skills/validation/test_orchestration.py) checks the
delegation graph:

- every delegation target resolves to a real skill;
- every internal specialist's entry routing names the owner that actually
  delegates to it;
- the graph is acyclic;
- the verdict vocabulary admits no fourth token;
- pipeline owners hold an orchestrator role;
- every stated revision cap matches `gates.yaml`.

It also compares `gates.yaml` `guards` strings against the state machine in
`contracts/workflow-protocol.md`, and pipeline `when` and `fan_out` values against
the skills and gate parameters they depend on.

## Tests

No test count is recorded in this file. A count copied into a document is stale
with the next test added, and nothing here would say so. The counts are produced by
running the suites: each command below ends with a `Ran N tests` line and an `OK` or
`FAILED` verdict, and CI runs every one of them on every change. Dated observations of every count and wall time, round by
round, are in [docs/quality-audit.md](docs/quality-audit.md#benchmark-results).

| Suite | Command |
|---|---|
| hooks | `python -m unittest discover -s skills/harness/hooks -p "test_*.py"` |
| gates | `python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"` |
| validation | `python -m unittest discover -s skills/validation -p "test_*.py"` |
| scripts | `python -m unittest discover -s skills/scripts -p "test_*.py"` |
| taste | `python -m unittest discover -s skills/taste -p "test_*.py"` |
| installers | `python -m unittest discover -s scripts -p "test_*.py"` |
| skill_creator | `python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"` |

The suite names are the keys of `commands` in `skills/runtime-manifest.yaml`, which
holds the same command lines. A test that needs PyYAML says so in its skip message,
so a count with and without PyYAML installed can differ by those skips.

Run them all, from a checkout (the same seven suites and three validators CI runs):

```bash
for d in skills/harness/hooks skills/harness/gatekeeper skills/validation \
         skills/scripts skills/taste scripts skills/skill-maker/skill-creator; do
  python -m unittest discover -s "$d" -p "test_*.py"
done
python skills/scripts/validate_manifests.py
python skills/scripts/check_runtime.py
python skills/scripts/package_check.py --root .
```

## Methodology

### Scoring

Rubric scores are model judgements against a written rubric, not machine output.
Each skill was read against all ten dimensions, and every finding was cited to a
file and line. A deduction was only taken where the claim could be checked against
its source: `gates.yaml`, `ownership.yaml`, `pipelines.yaml`, the harness code, or
the named test.

A document asserting a guarantee nothing enforces is a finding. So is a document
denying a guarantee it has, which is the worse direction because it invites
deleting test-enforced content.

Scores are therefore reproducible in method but not deterministic in value. They
are useful as a relative signal and a defect-finding instrument, not as a
precision metric.

The 2026-10-05 round re-scored all 53 skills with five independent parallel
scorers, and the artifacts with a sixth. Unlike the 09-18 round, the scorers ran
the claims they could: `save_run.py`, `check.py`, `guard_state.py`, the hook
entry point and `quick_validate.py`, each against throwaway copies.

The round produced 121 deductions across 48 skills. The citations, not the
totals, are the output that matters.

Scorer variance is real. No doctrine file changed between the 10-01 and 10-05
rounds, and single artifacts still moved by up to 6 points between scorers.

### Routing measurement

The corpus is drawn from the catalog, never invented, in three forms of rising
difficulty:

- **Advertised** — each skill's own `## Use This Skill When` phrasings.
- **Routed** — phrases lifted from a *sibling's* "Route elsewhere" sentence,
  where the catalog itself declares which skill should win.
- **Paraphrased** — either corpus restated by a model as a developer would
  actually type it, with the catalog's distinctive terms removed.

Only the paraphrased score is quoted. The first two both reached 100%, and both
are close to worthless: the winning description literally contains the query's
words, so the match is nearly free. Rewriting the same queries into a user's own
vocabulary dropped accuracy by sixteen points, which is the difference between
measuring lexical echo and measuring discrimination.

Two scoring rules are applied, and both are visible in the report:

- **Owner credit.** A miss is credited when the chosen skill is the *declared
  delegating owner* of the expected one, read from that skill's own entry
  routing. Routing a cold request to the owner is the documented path, so scoring
  it wrong would measure the catalog against ground truth its own doctrine
  contradicts.
- **Both texts kept.** Every result keeps the original trigger and the text
  actually asked, because a paraphrase can drift far enough that the miss
  belongs to the rewrite.

### What is not measured

- **Agentic behaviour after selection.** The eval measures which skill a model
  picks, not whether it then behaves correctly. A skill can be picked right and
  run wrong.
- **Real sessions end to end.** `run_eval.py` measures registration, not task
  outcomes. A workspace realistic enough to exercise every skill does not exist
  here.
- **What a host's picker offers.** The routing roster is every skill as a
  path-prefixed id, the nested specialists included, which a host that scans one
  level deep never lists (see Host registration above). The routing figure
  measures how well descriptions discriminate, not what a host user can choose.
- **The dual-mode split.** `qa` and `ship` run directly on an explicit standalone
  request and enter through `admiral` on a cold lifecycle request
  (`routing-doctrine.md`, Routing classes). That discriminator is the user's
  intent, which a description alone does not carry, so the eval cannot score
  those skills against `admiral` on it. The shared phrases ("find the root cause",
  "create a skill") are deliberate and tested; they are not a routing error.
- **Run-to-run variance of the routing figure.** Each round is one run with
  freshly generated paraphrases; no repeat runs have been taken to give it an
  error band.
- **Trigger phrasings beyond four per skill.** The corpus takes four; a skill's
  fifth and sixth phrasings are untested.
- **Hook registration on a given host.** The hook behaviour is tested against
  fixtures; whether a particular install has registered it is outside the repo.
- **Stage conditions and delegation at runtime.** `pipelines.yaml` declares
  `when` and `fan_out` values that are now compared against skills and gate
  parameters, but whether a condition ever fires in a real run is judgement.

### Reproducing

```bash
python skills/validation/run_eval.py --registration
python skills/validation/trigger_eval.py --mode both --paraphrase --per-skill 4
```

The routing eval needs network and costs real money: $4.81 for the full 2026-10-05
run of 21 batches. `--pilot` runs a single batch first so the cost is known before
the run.
