# Supreme Team quality audit and benchmark — 2026-10-01

## Executive verdict

**Baseline score: 90/100 — strong, contract-driven system.** The catalog has unusually strong machine-readable
ownership, routing, evidence, and cross-document parity controls. The principal
quality defect found in the initial audit was a repeatable performance-budget
failure in the hostile-input path of the command scanner. The remediation in
this change resolves all four findings; the original scorecard and observations
remain below as the before-state rather than being rewritten as if they passed.

This is a checkout audit, not a production effectiveness study. No saved runs or
tool trajectories existed, so this review measures specification quality,
deterministic validation, test breadth, and local runtime behavior. It does not
claim that real-world delegations complete successfully at a particular rate.

## Scope and method

The audit covered all 53 `SKILL.md` files, the six named doctrine files plus the
save, execution, and MCP protocols, all ten pipeline definitions, all ten gate
boundaries, the hook and gate harnesses, and the pipeline owners and gatekeepers.
The following equally weighted dimensions were used for every surface:

1. **Coverage** — declared responsibilities and failure paths are complete.
2. **Consistency** — prose, manifests, ownership, and routing agree.
3. **Enforcement** — important claims are checked rather than merely stated.
4. **Safety** — inputs, destructive actions, evidence, and failure states fail in
   the intended direction.
5. **Operability** — the surface is understandable, testable, portable, and fast
   enough for its role.

Each surface score is the average of those dimensions. The overall score is the
equal-weight average of the six surface scores below. Scores are evidence-based
but remain an expert assessment, not output from the skill-reviewer's per-skill
rubric and not a statistically calibrated industry percentile.

## Scorecard

| Surface | Coverage | Consistency | Enforcement | Safety | Operability | Score |
|---|---:|---:|---:|---:|---:|---:|
| Skills | 94 | 92 | 88 | 91 | 85 | **90** |
| Doctrines and protocols | 93 | 91 | 86 | 92 | 78 | **88** |
| Pipelines | 95 | 96 | 95 | 91 | 88 | **93** |
| Review gates | 96 | 96 | 97 | 95 | 86 | **94** |
| Harness | 92 | 90 | 91 | 91 | 71 | **85** |
| Orchestrators | 94 | 92 | 89 | 92 | 78 | **89** |
| **Overall** |  |  |  |  |  | **90/100** |

## Benchmark evidence

### Inventory and static structure

- 53 skill definitions, 10,440 total `SKILL.md` lines, a median of 171 lines,
  and no skill over the reviewer's 500-line progressive-disclosure ceiling.
- Ten pipelines and ten matching gate boundaries were loaded successfully.
- Manifest validation resolved 53 team members, 45 owners, 85 owned artifacts,
  11 agent delegates, and all ten pipelines and boundaries with zero errors.
- Before this report was added, package validation selected 440 files with no
  missing required assets or package violations. The post-change check selected
  441 with the same clean result.
- The read-only runtime audit scanned zero runs and zero trajectories because
  neither generated root existed. Its only findings were the informational
  `save_root_missing` and `harness_root_missing` conditions.

### Test benchmark

| Suite/check | Result | Tests | Time |
|---|---|---:|---:|
| Hook harness | **Fail**: one performance assertion | 927 (2 skipped) | 299.632 s |
| Gate harness | Pass | 255 (1 skipped) | 45.657 s |
| Contract validation | Pass | 253 (9 skipped) | 18.914 s |
| Shared scripts | Pass | 386 (3 skipped) | 35.411 s |
| Taste | Pass | 213 | 8.755 s |
| Installers | Pass | 85 | 181.118 s |
| Skill creator | Environment-limited: four missing-interpreter failures | 158 (1 skipped) | 4.592 s |
| Runtime check | Pass | — | 0.175 s |
| Manifest validator | Pass | — | 0.196 s |
| Package validator | Pass | — | 0.255 s |

Across the seven suites, 2,277 tests ran. Excluding four checks that could not
launch the unselected pyenv 3.10/3.11 interpreters, 2,272 passed and one failed.
The full fail-fast command reached the hook failure in 302.111 seconds. Times are
single local wall-clock observations on Python 3.13.13, not cross-host baselines;
they should be used to locate cost, not to claim a stable regression.

The failing hostile-input subtest was repeated three more times and failed all
three. Its measured analysis times were 4.326 s, 4.399 s, and 4.455 s against a
strict `<4.0 s` budget. The failure is therefore reproducible locally rather than
a single-suite anomaly.

## Findings

### F-01 — command scanner exceeds its hostile-input budget

- **Status:** Resolved in this change.
- **Severity:** Major
- **Surface:** Harness operability
- **Evidence:** The PowerShell deeply nested-brace case exceeds its four-second
  assertion in the full hook suite and in three of three focused reruns.
- **Impact:** A pre-tool hook is latency-sensitive. Even though hooks deliberately
  fail open on internal faults, multi-second analysis delays the host action and
  makes the safety layer expensive to keep enabled.
- **Recommended action:** Profile `_ps_blocks` and its callers with the exact
  100,000-character fixture, bound repeated scanning, add a linear-time or explicit
  complexity invariant, and retain the current adversarial test as the acceptance
  check. Re-run the hook suite on every supported CI OS before changing the budget.

### F-02 — local hook enforcement is not activated

- **Status:** Resolved operationally on the audited host; no machine-specific
  configuration was committed.
- **Severity:** Minor (environment limitation)
- **Surface:** Harness deployment
- **Evidence:** Readiness reports Python and deterministic validators ready, but
  all three Codex hook registrations are absent and host firing is unverified.
- **Impact:** The implementation and tests exist, but entry routing, pre-tool
  protection, and post-tool observations are advisory-only in this checkout.
- **Recommended action:** Preview `repair_registration.py --host codex --scope
  project`, review the proposed host configuration, then apply only with owner
  authorization. Registration state must not be confused with implementation
  quality.

### F-03 — older-interpreter checks treat dormant pyenv shims as runnable

- **Status:** Resolved in this change.
- **Severity:** Minor (environment limitation; portability risk not proven)
- **Surface:** Skill-creator test operability
- **Evidence:** Four tests attempted `/root/.pyenv/shims/python3.10` and
  `python3.11`; pyenv reported that those versions exist but are not selected, and
  each process exited 127.
- **Impact:** Local suite results are noisy on a host with installed-but-inactive
  pyenv versions. The supported runtime contract itself begins at Python 3.13, so
  these failures do not contradict the declared catalog floor.
- **Recommended action:** Make interpreter discovery prove executability with a
  version probe before including a shim, or document the required pyenv selection
  for this compatibility-only suite. Confirm behavior in CI before classifying it
  as a code defect.

### F-04 — specification density raises change and onboarding cost

- **Status:** Resolved for the identified high-density skill entry points, with
  a regression check for future growth.
- **Severity:** Minor
- **Surface:** Skills, doctrines, and orchestrators
- **Evidence:** The largest skills are 458, 414, and 402 lines; the save protocol
  is 467 lines and the design and Taste doctrines are 447 and 436 lines. None
  breaches the 500-line skill ceiling, and extensive parity tests mitigate drift,
  but several entry and gate surfaces require substantial context before action.
- **Impact:** Dense contracts improve rigor while increasing prompt cost and the
  chance that operators miss a judgment-only clause that has no comparator.
- **Recommended action:** Preserve canonical rules while moving explanatory
  material and worked examples behind concise indexes. Explicitly inventory every
  `judgement` or `judgement_only` claim and prioritize mechanical enforcement for
  high-risk items such as stdlib-only imports and conditional-stage execution.

## Strengths by surface

- **Skills:** Complete roster, explicit triggers and boundaries, shared severity,
  failure modes, save behavior, and progressive disclosure. The catalog-wide
  review contract prevents a high score from being based on appearance alone.
- **Doctrines:** Clear precedence and canonical authority reduce ambiguity. The
  documents openly identify which statements are mechanically checked and which
  still require judgment, an important sign of evidence maturity.
- **Pipelines:** Machine-readable stage ownership, dependencies, conditional
  stages, fan-out, delegates, scripts, and closing boundaries provide unusually
  high traceability. Independent validators check the important mirrors.
- **Review gates:** Typed evidence, artifact hashes, sanctioned applicability
  records, traversal protections, revision-aware reuse, owner-grouped revision
  packets, and fail-loud behavior form the strongest part of the system.
- **Harness:** Broad adversarial coverage and explicit fail-open/fail-loud
  separation are strong. The reproducible scanner latency and absent local hook
  activation prevent a higher operational score.
- **Orchestrators:** Admiral primacy, session pinning, one-writer ownership,
  revision lineage, rewind rules, and bounded gate cycles are coherent. Their
  density and reliance on human judgment for some stage conditions are the main
  maintainability costs.

## Remediation verification

| Finding | Fix | Verification |
|---|---|---|
| F-01 | Deep PowerShell blocks stop recursive replay after the existing 64-level brace bound; the main lexer still exposes mutating commands. | The hostile-input budget test passes, and a new 1,000-level regression proves `Remove-Item` remains visible. |
| F-02 | Registered `PreToolUse`, `PostToolUse`, and `UserPromptSubmit` at Codex user scope through the sanctioned repair command. | `verify_registration.py --host codex` reports all three hooks `OK`, integrity matched, and status `REGISTERED`. Host firing remains observable only on a subsequent host event. |
| F-03 | Interpreter discovery now starts each candidate with a bounded version probe and ignores dormant or broken shims. | Discovery unit tests cover return codes 0 and 127; the suite passes locally and skips unavailable older runtimes instead of failing four launches. |
| F-04 | Added task-oriented operator indexes to the three skills over 400 lines and a catalog contract enforcing a 500-line ceiling plus navigation above 400 lines. | The frontmatter/catalog budget tests pass and future density regressions fail deterministically. |

After remediation, the complete hook suite passes 928 tests with two skips in
299.535 seconds, and the complete skill-creator suite passes 160 tests with
three skips in 2.259 seconds. The validation suite passes 254 tests with nine
skips. These are post-fix checks; the benchmark table above intentionally
retains the original observations.

## Verdict and next benchmark

**Verdict: APPROVED for the audited findings.** The initial score remains a dated
baseline rather than an inflated post-fix estimate. The fixes close the four
findings locally without weakening the scanner budget or committing host-specific
configuration. For a meaningful longitudinal benchmark, capture at least five
full suite samples per supported OS, report median and p95, and compare them to
this audit only after confirming equivalent hardware and Python/PyYAML variants.
