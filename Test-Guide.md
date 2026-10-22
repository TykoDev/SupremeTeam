# Test-Guide

How to run the SupremeTeam end-to-end test session: drive a delivery pipeline
all the way to deploy under live gatekeeping, then audit the log history to
verify that skills, gates, doctrines, hooks, Taste, skill-maker, and
self-improvement behave as specified.

This guide reproduces the session recorded as run `pi-deploy-02`
(`skillset-saves/runs/pi-deploy-02/`). Every procedure below has a worked
example in that run's evidence; when a command has a gotcha, it is collected in
[§15](#15-gotchas-table) rather than hidden in prose.

---

## 0. Before you start

### Prerequisites

- Python 3.13+ on PATH (`python`; on Windows `py -3` works too).
- A checkout of the skillset, run from the project root (the directory holding
  `skills/`, `skillset-saves/`, `.harness-state/`).
- Hook registration is optional but recommended: without it the guard probes in
  §11 cannot run. Register with the host installer (`scripts/install_hooks.py`),
  then confirm with `python skills/harness/hooks/verify_registration.py`.
- The `claude` CLI is optional; only §8 (model-backed trigger eval) needs it.

### The two state roots and who may write

| Root | Holds | Who writes |
| --- | --- | --- |
| `skillset-saves/` | run state, phase artifacts, evidence, verdicts, preferences | `save_run.py` owns `_state.md`, `_lock.md`, `_audit-trail.md`, `_latest.md`; phase leads own their phase files; `taste_prefs.py` owns preferences |
| `.harness-state/` | guard record, trajectories, observations, test scratch, packages | `guard_state.py` owns the guard record; hooks own observations and trajectories |

Everything else you create goes in the application's own layout (for this
session: `tools/run-audit/`) or in git-ignored scratch (`harness-test-work/`).

### Evidence discipline (the rules that make the audit possible later)

1. Never hand-edit a save record. If the writer refuses, the refusal is the
   contract working — fix the input, do not edit the state.
2. Hash every artifact you will later cite: `python skills/scripts/content_hash.py <paths>`.
3. A claim in a report names the log that proves it; a number without a log
   does not go in the report.
4. Where a check cannot run, record it as unavailable with its reason. Do not
   estimate around it.
5. Re-verify before you close: re-run the gate checker over every package at
   delivery time and record the result (evidence is valid at read time).

### Vocabulary you must use

- Findings: `Critical | Major | Minor | Info`. Critical blocks; Major must be
  `verified`, `not-applicable`, or `deferred` with an owner and a reopen
  trigger before a gate will pass.
- Verdicts: `APPROVED | REVISE | ESCALATE`. A REVISE is one packet per round,
  cycle cap 3, then escalate to the user.
- Gate results come in pairs at phase-gated boundaries: the phase gatekeeper's
  record and the cross-stage record, each written only by
  `skills/harness/gatekeeper/check.py --verdict-out`.

---

## 1. Phase A — Intake (about 30 minutes)

```bash
# 1. classify the save directory before creating anything
python skills/harness/hooks/save_run.py status

# 2. the four intake contracts
python skills/harness/hooks/verify_registration.py     # hook registration
python skills/harness/hooks/check_readiness.py         # runtime readiness
python skills/scripts/mcp_registry.py --host claude    # registry freshness

# 3. resolve the grilling destination
python skills/scripts/output_paths.py --kind phase_report --phase intake \
    --name report_grilling.md --run-id <run> --mkdir
```

Write the grilling log (`intake/report_grilling.md`) with exactly four tables:
**Resolved decisions**, **Deferred decisions**, **Rejected options**,
**Non-goals and YAGNI deferrals**. Every row id is `D-<n>`, unique across all
four tables (yes, the deferred and rejected rows also use `D-` ids). The
`Source` column accepts only `user`, `codebase`, `prior-artifact`,
`delegated-default`.

```bash
# 4. self-check the log before anything depends on it
python skills/harness/gatekeeper/check.py --intake-log skillset-saves/runs/<run>/intake/report_grilling.md

# 5. create the run (one writer, one record)
python skills/harness/hooks/save_run.py create --run-id <run> --owner admiral \
    --evidence skillset-saves/runs/<run>/intake/report_grilling.md \
    --execution-mode skill --set hook_registration_status=REGISTERED \
    --set runtime_readiness_check=ready --next-action "<what you wait for>"
```

Checkpoint before every later delegation:
`save_run.py checkpoint --run-id <run> --owner admiral --expect-revision <n> --set delegated_to=<lead> --next-action "<...>"`.

---

## 2. Phase B — Design package and its two gates

Write the design artifacts (one directory, `skillset-saves/runs/<run>/design/`):
`research.md`, `architecture.md`, `interfaces.md`, `plan.md`,
`implementation-spec.md`, `taste-snapshot.md`, `stack-lock.md`,
`design-system.md` (if a user-facing surface exists), plus `manifest.json`.

`plan.md` must contain a `## Acceptance criteria` table with columns
`ID | Slice | Observable condition | Check that proves it | Acceptor`, ids `AC-<n>`.
`interfaces.md` items are `IF-<n>`. `research.md` should carry a
harness-doctrine §5 note (lifecycle layer citation plus a regression note) if
anything in the package mentions hook machinery, or the phase gate will fail.

### Manifest skeleton (schema 2, inside a run)

```json
{
  "schema_version": 2,
  "boundary": "design-to-build",
  "owner": "commander",
  "run_id": "<run>",
  "revision": 2,
  "revisions": [2],
  "submission_id": "<run>-design-r2",
  "artifact_hashes": { "plan.md": "<content sha256>", "../intake/report_grilling.md": "<...>" },
  "evidence": {
    "decisions":  { "artifacts": ["../intake/report_grilling.md"] },
    "interfaces": { "artifacts": ["interfaces.md"], "change": "changed",
                    "items": [{"id": "IF-1", "kind": "cli-contract", "name": "..."}] },
    "acceptance": { "artifacts": ["plan.md"] },
    "security_seed": { "applicable": true, "architecture_revision": "1", "decided_by": "security-builder",
                       "scope": "...", "reason": "...", "boundaries": [{"id": "SB-1", "control": "..."}] },
    "stack_lock": { "applicable": false, "decided_by": "commander",
                    "reason": "no new runtime or framework - existing stack unchanged", "scope": "..." }
  }
}
```

Rules the checker enforces: `owner` must equal the boundary's submitter; the
manifest needs `revision` **and** a one-value `revisions` array; every
artifact-backed key names hashed artifacts; a waived key at schema 2 is an
applicability record `{applicable, reason, scope, decided_by}` whose `reason`
exactly matches a sanctioned wording in `skills/gates.yaml`; `IF-` ids must
appear in their artifacts; blocked phrases (see §15) fail the package.

### Run the two gates

```bash
# self-check first (never submit a mechanically failing package)
python skills/harness/gatekeeper/check.py --boundary design-to-build \
    --package skillset-saves/runs/<run>/design/manifest.json

# phase gatekeeper: facts only, PASS / FAIL / UNCHECKED
python skills/design/gatekeeper-design/scripts/check.py skillset-saves/runs/<run>/design --json

# phase verdict: write the judgment record, then have check.py record the verdict
python skills/harness/gatekeeper/check.py --boundary design-to-build \
    --package skillset-saves/runs/<run>/design/manifest.json \
    --judgment skillset-saves/runs/<run>/design/verdict_design-to-build.judgment.json \
    --verdict-out skillset-saves/runs/<run>/design/verdict_design-to-build.json

# cross-stage verdict: --prior is the phase record; the judgment gate is gatekeeper-admiral
python skills/harness/gatekeeper/check.py --boundary design-to-build \
    --package skillset-saves/runs/<run>/design/manifest.json \
    --prior skillset-saves/runs/<run>/design/verdict_design-to-build.json \
    --judgment skillset-saves/runs/<run>/design/verdict_design-to-build.cross-stage.judgment.json \
    --verdict-out skillset-saves/runs/<run>/design/verdict_design-to-build.cross-stage.json
```

Judgment record shape: `{boundary, submission_id, revision, gate, verdict,
findings[], statement}`. `submission_id` and `revision` must equal the
manifest's. A finding stands on a basis: `{kind: decision|acceptance, ref:
"D-3"/"AC-2", artifact}` (the artifact must be one of *this* package's hashed
artifacts and must contain the id), `{kind: contract, source, ref}` (source must
be an existing `.md`/`.yaml` under `skills/`), or `{kind: contradiction}` with
two hashed artifacts. Info findings never block; Critical and Major do.

---

## 3. Phase C — Build, tests evidence, and the rewind drill

Build evidence for `build-to-review`:
`approved_design_revision` (a `{revision, verdict}` record pointing at the
design cross-stage verdict), `implementation` (change_set: diff artifact +
`changed_files` with `path`, `sha256`, `status`), `tests` and `runtime`
(probes: `artifacts`, `exit_code`, `inputs` with path+sha256, `result.status`),
`traceability` (trace_map), `security_evidence` (findings record).

- The test log must contain each test name **verbatim** as
  `module.Class.test_method`, because the trace map checks test names against
  the log text. Run with `-v`.
- Every approved `AC-<n>` gets a trace row; every changed file appears in some
  row's `changes` or `supporting`.
- `changed_files[].path` is re-hashed at gate time against the working tree:
  freeze the code before submitting, or the gate reports drift.

### Rewind drill (do this on purpose once)

1. Submit and approve a build package.
2. Introduce a deliberate defect in the product's core claim and find it with a
   review-stage probe (not with the unit tests — the point is that probes catch
   what tests miss).
3. Rewind: `save_run.py checkpoint ... --set rewind_to=build-to-review --set rewind_reason="<why>"`.
4. Fix with a regression test, archive the superseded verdict files under
   `build/evidence/` with names that do **not** start with `verdict_`, and
   resubmit with `--prior <superseded record>` so delta review names exactly the
   changed evidence keys.

Worked example: `delivery/evidence/history-audit.log` and the `verdict_build-to-review*.json`
pair in run `pi-deploy-02` (revision 3 superseded by revision 5).

---

## 4. Phase D — Review and its two gates

Six lenses at `review-to-delivery`; the three unconditional ones plus whatever
your change set activates (security, frontend, visual, devex). Each lens packet
markdown file must carry two field lines or the phase gate rejects it as a
missing artifact:

```markdown
Outcome: one line stating the lens verdict.
Findings: pointer to the findings table below.
```

(the engine matches `Outcome:` / `Findings:` at the start of a line — a heading
`## Outcome` does not count.)

The manifest needs `review_verdict` (`{recommendation: "APPROVED"}`), `findings`
(items with `id`, `severity`, `status`, and `owner` + `reopen_trigger` for any
deferred Major), `executed_probes` (probe record over a real log),
`rendered_verification`, `residual_risk`, `revision_lineage`.

Render record when you have a surface but no browser:

```json
{
  "artifacts": ["evidence/render-report.html", "evidence/render-check.log"],
  "result": { "status": "inferred" },
  "limitation": "no browser session exists on this host; verification is structural ...",
  "breakpoints": [1280, 960, 640],
  "themes": ["light", "dark"],
  "inputs": [{"path": "tools/.../render_source.py", "sha256": "<...>"}]
}
```

A render record binds `inputs`; `status: "inferred"` requires the `limitation`.
Then run gatekeeper-code's `scripts/check.py` and the two `check.py` verdict
passes exactly as in §2.

---

## 5. Phase E — Release, gate, deploy

`deploy-readiness` evidence: `approved_delivery` (revision_ref to the review
cross-stage verdict), `deploy_config`, `verification_plan`, `rollback_plan`
(hashed artifacts), `human_go_required` (human_go record):

```json
{
  "approver": "<who authorized it>",
  "approval_reference": "<the instruction, quoted>",
  "revision": "6",
  "decided_at": "2026-10-11T20:32:42+00:00",
  "decision": "go"
}
```

`revision` must be a **string** matching `approved_delivery.revision`, and the
release pipeline has no phase gatekeeper: one `check.py` pass with a
gatekeeper-admiral judgment writes `verdict_deploy-readiness.json`.

Rollout with a written verification plan (V1 version, V2 scan, V3 hashes,
V4 counts, V5 tests) against the **deployed copy**, logging every command and
exit code into `release/evidence/rollout.log`. Rollback must be one reversible
action you can state in a sentence.

---

## 6. Sweep F — catalog suites and deterministic validators

```bash
for suite in skills/harness/hooks skills/harness/gatekeeper skills/validation \
             skills/scripts skills/taste scripts skills/skill-maker/skill-creator; do
  python -m unittest discover -s "$suite" -p "test_*.py"
done
python skills/scripts/check_runtime.py
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
```

Expected on a healthy host: seven green suites (about 2,500 tests) and three
exit-0 validators. Save the whole transcript to a hashed log; a prior run's
claim of host-environment failures should be re-checked before you believe it.

---

## 7. Sweep G — trigger routing and lexical echo

```bash
# online: advertised mode measures lexical echo (a skill's own words routed back at it)
python skills/validation/trigger_eval.py --pilot --per-skill 1 --mode advertised \
    --out .harness-state/eval-reports/echo.json

# online: --paraphrase is the only mode that measures more than lexical echo
python skills/validation/trigger_eval.py --pilot --per-skill 1 --mode advertised --paraphrase \
    --out .harness-state/eval-reports/paraphrase.json

# offline proxy: collisions, reachability, routing classes
python -m unittest discover -s skills/validation -p "test_trigger_routing.py" -v
```

The comparison you want is `accuracy(advertised) - accuracy(paraphrased)`; a
small delta means the catalog routes meaning rather than vocabulary. If the
model CLI is quota-limited the eval reports `accuracy is undefined` and writes
the failure into its output file — record that honestly and re-run later. `--out`
must be a **file** path whose parent exists.

---

## 8. Sweep H — Taste lifecycle

Exercise the store, then restore it (test traffic must not become a
preference):

```bash
python skills/taste/taste_prefs.py status
python skills/taste/taste_prefs.py propose --scope project --expect-revision <n> \
    --id "selftest.<name>" --value '{"category": "density", "normalized_rule": "...", "strength": "soft", "source": "explicit"}'
python skills/taste/taste_prefs.py confirm --scope project --expect-revision <n+1> --id "selftest.<name>" --value '{...}'
python skills/taste/taste_prefs.py effective
python skills/taste/taste_prefs.py revoke --scope project --expect-revision <n+2> --id "selftest.<name>"
python skills/taste/taste_prefs.py status
```

- The typed entry requires doctrine identifiers: `category` from
  {visual-style, typography, color-behavior, density, motion, layout,
  component-behavior, content-tone, interaction-patterns,
  technology-ergonomics, anti-preference}, `strength` from {hard, strong, soft},
  `source` from {explicit, imported, confirmed-inference}.
- Every mutation on an existing store needs `--expect-revision`; stale revisions
  are refused. Expect refusals the first time through — they are the contract.
- Restoration is content-identical, not revision-identical (the counter
  advances). Say so in your evidence.

To gate it, build a `taste-review` package with all keys: `scope`, `intent`,
`before_revision` (applicability record if there was no prior store),
`preference_diff` (with `added`, `updated`, `deprecated`, `revoked`,
`unchanged` lists and `before_digest`/`after_digest`), `confirmation`
(`candidate_ids` must equal the changed ids exactly), `conflict_analysis`,
`policy_check`, `persistence_result`, `effective_profile`, `consumer_handoff`
(digest must equal the effective profile digest), `taste_review_record`,
`residual_uncertainty`.

---

## 9. Sweep I — skill-maker

Keep the lab skill in scratch so catalog parity tests never see it:

```bash
mkdir -p harness-test-work/skill-maker-lab/<skill-name>
# write SKILL.md with Skills-spec frontmatter (name matches the directory)
cd skills/skill-maker/skill-creator
python -m scripts.quick_validate "<abs path to the skill folder>"
python -m scripts.package_skill  "<abs path to the skill folder>" "<abs output dir>"
```

Both must run with `skills/skill-maker/skill-creator` as the working directory.
Gate the exercise at `skill-maker-to-delivery` with `skills`, `team_manifest`
(applicability record `single skill - no team manifest produced` for one skill),
`link_report`, `validation_report`. Model-driven scoring is optional; if you
skip it, say so instead of implying a score.

---

## 10. Sweep J — live guard probes (requires registered hooks)

Each probe is its own command: the guard judges whole commands, so one denied
probe must not hide the others. Target scratch paths or nonexistent names —
never a real record.

| Probe | Command shape | Expected |
| --- | --- | --- |
| Rule C, core save file | `echo x >> <run-shaped path>/_state.md` (nonexistent run) | denied: only `save_run.py` writes core save files |
| Rule C, audit trail | `echo x >> skillset-saves/runs/<nonexistent>/_audit-trail.md` | denied |
| Rule C, scratch contrast | same filename under `harness-test-work/` | **allowed** — scratch is an owned class |
| Rule C, verdict records | `cp anything <any>/verdict_*.json` | denied: verdicts are written only by `check.py --verdict-out` |
| Rule F, hook files | `echo x >> skills/harness/hooks/pre_tool_use.py` | denied while the guard is in use |
| Rule B, frozen boundary | `guard_state.py freeze --glob "..." --owner ...`, then write inside it | denied until release |
| Release authority | `guard_state.py release --glob "..." --requester <who> --reason "<why>"` | `--requester` is mandatory |

Record each denial verbatim in your evidence; they are the strongest proof the
guardrail layer works.

---

## 11. Sweep K — self-improvement and history audit

```bash
python skills/harness/hooks/audit_improve.py --run --project-root .
```

Read the JSON: audit-event census (create/checkpoint/refused/recover counts),
empty trajectory steps, hook observation counters. Refused events are good
news — they are the writer enforcing its contract.

History audit (read-only):

```bash
# trail census per run: event types, refusals and their reasons, revisions seen
python -c "import json; from collections import Counter; \
 e=[json.loads(l) for l in open('skillset-saves/runs/<run>/_audit-trail.md') if l.strip()]; \
 print(Counter(x['event'] for x in e))"

# post-hoc integrity: re-run the gate checker over every stored package
python skills/harness/gatekeeper/check.py --boundary <boundary> \
    --package skillset-saves/runs/<old-run>/<phase>/manifest.json
```

A package that passed at submission but fails a fresh read is a finding about
evidence longevity, not necessarily about the run: verify independently with
`content_hash.py` before you accuse anyone. When you enumerate verdict files
from Python, use a neutral glob (`*/*.json` filtered on the `verdict_id` key) —
a literal `verdict_*.json` glob in a command may trip the guard's scanner.

---

## 12. Gap-closure drills

- **Post-release re-scan**: run the deployed copy again later and compare run
  sets and finding sets with the release-time report. Equal sets = the
  verification plan's follow-up is satisfied.
- **Performance**: build a synthetic history in scratch (the pattern is in
  `harness-test-work/bench_build_and_run.py`) and time `build_model` over it;
  report runs/second, not vibes.
- **Model-eval numbers**: one `claude -p "ok"` probe tells you whether the
  quota allows §7; if not, write the re-run date into the gap list.

---

## 13. Reporting

1. **Audit report** (`delivery/reports/harness-audit.md`): what was exercised
   (table), what was verified (with counts), findings table with owner and
   reopen trigger, and a recommendation naming who takes what next.
2. **Delivery record** (`delivery/reports/delivery-package.md`): follow
   `skills/contracts/delivery-template.md` field for field — run identity,
   goal, scope, traceability, stack lock, changed artifacts with hashes, tests
   and proof (including `unavailable` rows), claims/gaps/proof, gate verdicts
   with verdict ids, disputes, residual risks, next action, return.
3. **Release documentation package**: notes draft (audience-facing, redacted),
   operational follow-up (internal), redaction log, publication-approval record
   (the approver is never the drafter), documentation-gap list. See
   `skills/document-release/SKILL.md`.
4. **Animated dashboard** (optional, in the lineage of the run dashboards in
   `skillset-saves/runs/*/delivery/artifacts/`): self-contained HTML, numbers
   copied from hashed logs only, gaps said out loud.

Close the run through the writer only:
`save_run.py checkpoint --set phase_state=RUN_COMPLETE ...` then
`save_run.py complete --run-id <run> --owner admiral`.

---

## 14. Time budget

| Phase | Roughly |
| --- | --- |
| Intake | 30 min |
| Design + both gates | 1–2 h |
| Build + evidence + both gates | 2–4 h |
| Review + both gates | 1–2 h |
| Release + rollout | 1 h |
| Sweeps F–K | 1–2 h (hooks suite alone runs about 4.5 min) |
| Reporting | 1–2 h |

---

## 15. Gotchas table

| Trap | Symptom | Fix |
| --- | --- | --- |
| Manifest without `revisions` | `revisions must contain exactly one value` | add `"revisions": [<n>]` beside `"revision"` |
| Wrong `owner` | `submitter mismatch` | owner is the boundary's submitter from `gates.yaml`, not the skill you are |
| Bare fallback string at schema 2 | `bare fallback string not accepted` | applicability record `{applicable, reason, scope, decided_by}` |
| Waiver `reason` wording | `applicability reason not sanctioned` | copy the exact wording from `gates.yaml` |
| `human_go.revision` as integer | `human_go_required requires revision` | quote it: `"revision": "6"` |
| Grilling ids `DD-1`, `R-1`, `N-1` | `id 'DD-1' is not D-<n>` | all four tables use `D-<n>`, globally unique |
| Lens packet headings | `ARTIFACT_MISSING ... near misses` | add `Outcome:` and `Findings:` field lines (colon at line start) |
| Missing `policy_check` at taste-review | `missing evidence: policy_check` | it is required; write the scope-rule check as prose |
| `preference_diff` without `unchanged` | `record requires list field unchanged` | add the empty list |
| Judgment basis pointing outside the package | `basis artifact is not a correctly hashed package artifact` | cite one of *this* manifest's hashed artifacts, or use a `contract` basis |
| Test names in trace map not in the log | `test ... does not appear in the tests log` | run `unittest -v`; the qualified `module.Class.test` name must appear verbatim |
| Changed file edited after evidence | `hash drift: the file changed after the build evidence was taken` | freeze the change set before submitting; re-gate after any edit |
| Blocked phrases in artifacts | `blocked phrase: <file>` | no TODO / FIXME / XXX / HACK, "trust me", "100% complete", "lorem ipsum", "placeholder content", etc. in prose |
| Custom digest folding | false `hash-drift` findings | mirror `data_formats.content_sha256`: fold CRLF only, and only when the first 8 KiB has no NUL |
| `>` inside inline Python | `unplaced write target` denial | avoid `>` and runtime-built writes in `python -c`; use a script file |
| `cp` to `verdict_*.json` | guard denial | verdicts are written only via `check.py --verdict-out`; archive under other names |
| Unknown `phase_state` | writer refusal | the enum is closed; audit-shaped work runs under `DELIVERY_ACTIVE` |
| `trigger_eval.py --out dir/` | `FileNotFoundError` on write | pass a file path; the parent directory must exist |
| skill-creator tools from the wrong cwd | `No module named 'scripts'` | `cd skills/skill-maker/skill-creator` first |
| `unittest` a module by dotted name | `No module named '_catalog'` | use `discover -s <dir>`, which puts the directory on the path |

---

## 16. Command sheet

```bash
# ---- intake
python skills/harness/hooks/save_run.py status
python skills/harness/hooks/verify_registration.py
python skills/harness/hooks/check_readiness.py
python skills/harness/gatekeeper/check.py --intake-log skillset-saves/runs/<run>/intake/report_grilling.md
python skills/harness/hooks/save_run.py create --run-id <run> --owner admiral \
    --evidence skillset-saves/runs/<run>/intake/report_grilling.md

# ---- gates (repeat per boundary)
python skills/harness/gatekeeper/check.py --boundary <b> --package <manifest>   # self-check
python skills/<category>/gatekeeper-<name>/scripts/check.py <phase-dir> --json  # phase facts
python skills/harness/gatekeeper/check.py --boundary <b> --package <manifest> \
    --judgment <judgment.json> --verdict-out <phase>/verdict_<b>.json
python skills/harness/gatekeeper/check.py --boundary <b> --package <manifest> \
    --prior <phase>/verdict_<b>.json --judgment <cross>.judgment.json \
    --verdict-out <phase>/verdict_<b>.cross-stage.json

# ---- evidence
python skills/scripts/content_hash.py <paths...>

# ---- sweeps
for s in skills/harness/hooks skills/harness/gatekeeper skills/validation \
         skills/scripts skills/taste scripts skills/skill-maker/skill-creator; do
  python -m unittest discover -s "$s" -p "test_*.py"; done
python skills/scripts/check_runtime.py && python skills/scripts/validate_manifests.py
python skills/validation/trigger_eval.py --pilot --mode advertised --paraphrase --out <file.json>
python skills/taste/taste_prefs.py status
cd skills/skill-maker/skill-creator && python -m scripts.quick_validate <skill>
python skills/harness/hooks/audit_improve.py --run --project-root .

# ---- close
python skills/harness/hooks/save_run.py checkpoint --run-id <run> --owner admiral \
    --expect-revision <n> --set phase_state=RUN_COMPLETE --next-action "terminal"
python skills/harness/hooks/save_run.py complete --run-id <run> --owner admiral
```

Worked example run: `skillset-saves/runs/pi-deploy-02/` — every log this guide
tells you to produce exists there, including the rewind (§3), the live probes
(§10), and the gap-closure measurements (§12).
