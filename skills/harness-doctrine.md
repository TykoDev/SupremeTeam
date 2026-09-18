# Runtime Harness Doctrine

Binding rules for how every skill adapts the interface between the model and its
environment, not the model itself. The harness adds five layers without changing
the pipeline: entry routing, persistent context, phase trajectory, evidence
gates, and action guardrails. Skills and gates cite this doctrine by section
number.

This file is canonical for the four-layer model, the failure taxonomy and its
priority order, the engineering non-negotiables every intervention must satisfy,
and the structural rule gatekeepers apply to a package that touches a runtime
intervention. It is not canonical for the hooks' own behavior
(`skills/harness/hooks/README.md`), for gate boundaries and evidence
([gates.yaml](gates.yaml)), or for entry routing
([routing-doctrine.md](routing-doctrine.md)).

## Contents

- [Enforcement status](#enforcement-status)
- [0. Thesis and the model-agnostic principle](#0-thesis-and-the-model-agnostic-principle)
- [1. The four lifecycle layers](#1-the-four-lifecycle-layers)
- [2. Failure taxonomy and priority order](#2-failure-taxonomy-and-priority-order)
- [3. Engineering discipline (non-negotiables)](#3-engineering-discipline-non-negotiables)
- [4. Author checklist](#4-author-checklist)
- [5. Gate behavior](#5-gate-behavior)
- [Hooks](#hooks)
- [Gates](#gates)
- [State safety](#state-safety)
- [Failure paths](#failure-paths)

## Enforcement status

This doctrine is unusual in the catalog: a larger share of it is mechanically
enforced than in any sibling, because its subject is the deterministic layer
itself. The split still has to be stated, because §3 and §4 read like checks and
are not.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| §5: a package touching a runtime intervention names its lifecycle layer and carries a regression note | machine-checked | `skills/harness/gatekeeper/_gatecheck.py`, `check_harness_doctrine()`; see §5 for the exact markers |
| §0 and §3 *inert on the strong case*, for the gate engine | machine-checked by construction | `_gatecheck.py` fires only on mechanically certain signals and emits `NO_RUNTIME_INTERVENTION` otherwise |
| §1 Layer 3: guarded, frozen, read-only, single-writer, and destructive write boundaries | machine-checked where hooks are registered | `skills/harness/hooks/pre_tool_use.py`, against `.harness-state/guard-state.json` |
| §1 Layer 4: repeated-failure, empty-output, and oscillation trajectory patterns | machine-checked where hooks are registered | `skills/harness/hooks/post_tool_use.py` |
| Single-writer ownership of the run record and the guard boundary record | machine-checked | `skills/validation/test_catalog_contracts.py`, `GuardWriterTests`, with [save-ownership.yaml](save-ownership.yaml) |
| Fail-open behavior of every hook, and fail-loud behavior of the gate engine | machine-checked | `skills/harness/hooks/test_hooks*.py` and `skills/harness/gatekeeper/test_gatecheck.py` |
| A gate spec that is missing or malformed is an engine error, never a pass | machine-checked | `skills/harness/gatekeeper/check.py`, exit code 2 |
| §2: that a failure was classified into the *correct* category | judgement | nothing |
| §2: that a constraint sits at the earliest layer where it is enforceable | judgement | nothing |
| §3 beyond the gate check: local and minimal, evidence-triggered, no oracle | judgement | nothing |
| §4: the author checklist | judgement | nothing — it is a checklist for a human author, not a validator |
| §5 substance: that the cited layer is the right layer, and that the intervention is genuinely inert on a competent model | judgement | the engine reports `DOCTRINE_NOTE_PRESENT` as `UNCHECKED` precisely so a reviewer resolves it |
| This document itself | **judgement** | nothing — no comparator opens this file, and the §5 row above is not a counter-example. `skills/harness/gatekeeper/test_gatecheck.py` pins the *codes* `_gatecheck.py` emits (`NO_RUNTIME_INTERVENTION`, `DOCTRINE_NOTE_PRESENT`, `DOCTRINE_GAP`), and `_gatecheck.py` matches the literal token `harness-doctrine` inside a *submitted package*. Both read the engine and the package; neither reads this text, so the §5 check keeps working while any sentence here could change with no suite failing. |

## 0. Thesis and the model-agnostic principle

An agent's behavior is shaped not only by its model but by the runtime harness
that mediates how it observes, calls tools, realizes actions, interprets
feedback, and regulates multi-step trajectories. Supreme Team adapts that harness
through doctrine, contracts, hooks, and gate specs, leaving the model and the
host environment unchanged.

**Model-agnostic principle (non-negotiable).** Supreme Team runs on whatever
backbone the host provides. Every harness intervention must rescue a weak
backbone without degrading a strong one. An intervention that helps a small model
but interferes with a competent model's correct action is a defect, not a
feature. When in doubt, the intervention does nothing.

Operating principles that follow from it:

- Keep prose advisory and validators deterministic.
- Make hooks fail open on internal errors so tooling cannot brick the host, and
  report the degradation clearly.
- Block an action only when a valid guard or freeze record proves the boundary.
- Treat gate engine failure as `ESCALATE`, never as approval.
- Keep one run owner and one revision lineage across all phases.
- Re-check mode, save state, hook readiness, and tool freshness at boundaries.

## 1. The four lifecycle layers

Every cross-cutting constraint belongs to exactly one layer. Authors name the
layer when they add a constraint; gates check that the constraint sits at the
earliest layer where it is reliably enforceable.

| # | Layer | When it acts | What it does |
| --- | --- | --- | --- |
| 1 | **Environment Contract** | before interaction | Make stable tool, policy, and format constraints explicit so generic priors do not collide with environment rules. |
| 2 | **Procedural Skill** | task conditioning | Surface a compact, reusable procedure for the current task before work starts. |
| 3 | **Action Realization** | before execution | Validate, canonicalize, or block a generated action before it touches the environment. |
| 4 | **Trajectory Regulation** | after execution | Detect degenerate patterns (loops, stagnation, empty-output streaks, budget exhaustion) and inject recovery. |

### 1.1 Where each layer already lives

| Layer | Where it lives | Enforcement |
| --- | --- | --- |
| Environment Contract | `design-doctrine.md`, `grill-me-doctrine.md`, `mcp-tools.md`, `tech-stacks/registry.yaml`, per-skill `intake-brief.yaml` | doctrine plus gate review |
| Environment Contract | `execution-contract.md` | deterministic comparator: `skills/validation/test_catalog_contracts.py` compares the six canonical clauses against the fifteen skills that restate them |
| Procedural Skill | the skill library, `pipelines.yaml`, `session-memory` learnings | doctrine plus authoring |
| Action Realization | `careful`, `freeze`, `guard`, `unfreeze`, the save write probe, gate pre-checks, `harness/hooks/pre_tool_use.py` | advisory plus deterministic hook |
| Trajectory Regulation | gatekeepers, checkpoints, rewind rules, the revision cap, `harness/hooks/post_tool_use.py` | per boundary plus per step |

`execution-contract.md` is listed on its own row because its enforcement changed:
it was doctrine plus gate review until a comparator was added, and it is now the
one Environment Contract entry with a deterministic text check behind it. That
check covers the clause text only. Whether a run honored a clause remains gate
review, exactly as the other Environment Contract row says.

Skills are instructions running inside the host loop and do not own that loop, so
the only deterministic interception point is a host hook or plugin lifecycle.
Layers 3 and 4 therefore have both an advisory expression (skill prose) and,
where the host supports it, a deterministic expression under `harness/hooks/`.

## 2. Failure taxonomy and priority order

Classify a recurring failure by the earliest matching category. The order stops a
downstream symptom from masking the root interface failure.

1. **Action-realization failure**: intent was reasonable but not submitted in an
   executable form (a plain-text "tool call", invalid arguments, malformed
   schema). Layer 3.
2. **Environment-contract mismatch**: the call is executable but violates tool
   bounds, calling order, or argument semantics. Layer 1.
3. **Trajectory degeneration**: actions are valid but the episode loops,
   stagnates, retries the same failing command, or exhausts budget. Layer 4.
4. **Residual reasoning failure**: the protocol is followed but the logic,
   computation, or value selection is wrong. Out of scope for the harness.

Categories 1 to 3 are harness-addressable. Routing a reasoning failure to a
harness intervention is itself a doctrine violation.

**Worked example (category 4).** A well-formed command exits zero, but a unit
test afterwards fails because the logic is wrong. `post_tool_use.py` deliberately
does not fire: it triggers only on three or more identical failing actions, an
empty-output streak, or A,B,A,B oscillation, never on a single
valid-but-semantically-wrong action. Concluding "this edit caused that test
failure" would require correlating two tool calls by causal inference, which §3
forbids. A failing test is a well-formed signal the model can act on.

## 3. Engineering discipline (non-negotiables)

Every intervention (a doctrine clause, a hook rule, a guard boundary, a gate key)
must satisfy all of:

- **Local and minimal.** Address one precise failure pattern. No broad rewrites.
- **Evidence-triggered.** Fire only on a precise, mechanically detectable signal,
  never on a hunch about intent.
- **Never override ambiguous reasoning.** If the correct action is ambiguous, do
  nothing and let the model decide.
- **No oracle or hidden labels.** An intervention may expose stable
  environment-side structure; it must never use evaluation answers, success
  labels, or anything unobservable at runtime.
- **Regression check is mandatory.** Confirm the intervention does not block a
  valid action, inject misleading guidance, or degrade a working path. Hook
  changes run `python -m unittest discover -s skills/harness/hooks -p "test_*.py"`
  or add an equivalent case; gate changes run the suites under
  `skills/harness/gatekeeper/` and `skills/validation/`.
- **Fail open.** A harness mechanism that errors lets the underlying action
  proceed, never crashing or hard-blocking the host.

## 4. Author checklist

When adding or changing a cross-cutting constraint, confirm:

- [ ] The constraint is assigned to exactly one of the four layers (§1).
- [ ] It sits at the earliest layer where it is reliably enforceable (§2).
- [ ] It targets a harness-addressable failure, not residual reasoning (§2.4).
- [ ] It satisfies every non-negotiable in §3, especially inert on the strong
      case (§0).
- [ ] If deterministically enforceable, it is a hook or gate rule, not only
      prose (§1.1). If it cannot be, the advisory home is named.
- [ ] A regression note records what was checked for over-triggering.
- [ ] Hook and gate changes include an automated test, or state why the existing
      suite already covers the changed behavior.

## 5. Gate behavior

Gatekeepers (`gatekeeper-admiral`, `gatekeeper-design`, `gatekeeper-build`,
`gatekeeper-code`) and `skill-reviewer` reject a package or skill that:

- Adds a cross-cutting constraint without naming its lifecycle layer (§1).
- Places a constraint later than where it is enforceable (§2).
- Routes a residual reasoning failure to a harness intervention (§2.4).
- Ships an intervention that can fire on a competent model's correct action
  (§0, §3).
- Omits the regression note for a new or changed intervention (§3).

Reviewers cite this doctrine by section number when issuing findings.

**The mechanical half of §5.** The last two bullets are not prose assertions:
`skills/harness/gatekeeper/_gatecheck.py`, function `check_harness_doctrine()`,
scans every file in the package and enforces them. It works in three steps, and
each is worth knowing because they decide when the check fires:

1. *Does the package touch a runtime intervention?* The `_INTERVENTION_MARKERS`
   regex looks for `PreToolUse`, `PostToolUse`, `pre_tool_use`, `post_tool_use`,
   `runtime hook`, `tool-use hook`, `action realization`, `trajectory
   regulation`, `guard boundary`, or `freeze boundary`. No match anywhere in the
   package emits `NO_RUNTIME_INTERVENTION` as an informational pass and the
   check ends. This is §0 applied to the engine itself: a package that does not
   touch the harness is never asked to justify one.
2. *Is a lifecycle layer cited?* The `_LAYER_CITATION` regex accepts
   `Layer 1`-`Layer 4`, `§1`-`§5`, or the literal `harness-doctrine`.
3. *Is a regression note present?* The `_REGRESSION_NOTE` regex looks for the
   word `regression`.

Missing either 2 or 3 emits `DOCTRINE_GAP`, a Major failure that names which of
the two is absent and where the intervention markers were found. Having both
emits `DOCTRINE_NOTE_PRESENT` as `UNCHECKED`, not as a pass, which is the
engine's way of saying it verified the shape and cannot verify the substance:
whether the cited layer is the right one, and whether the intervention is truly
inert on a competent model, are judgements the gatekeeper still owes. The three
other bullets in this section are judgement throughout, and the gatekeepers that
run this engine are `gatekeeper-admiral`, `gatekeeper-design`,
`gatekeeper-build`, and `gatekeeper-code`, each through its own
`scripts/check.py`.

## Hooks

`harness/hooks/pre_tool_use.py` enforces valid guarded write boundaries and
denies direct writes to the single-writer records: core run files, durable Taste
state, and the guard boundary record itself. `post_tool_use.py` records
trajectory observations. `user_prompt_submit.py` advises front-door and
session-pin routing. `save_run.py` is the only writer of the run record, and
`guard_state.py` the only writer of the guard/freeze boundary record.
`verify_registration.py` inspects native host configuration without mutating it;
`repair_registration.py` previews a scoped repair and applies it only with
explicit approval; `check_readiness.py` reports Python, hooks, and save state as
independent capability facts and never claims a hook fired from config
inspection alone. Registration requires explicit user approval.

All three lifecycle hooks — `pre_tool_use.py`, `post_tool_use.py`, and
`user_prompt_submit.py` — call `_state.record_observation()` and then
`_state.refresh_run_heartbeat()`, so both the observation record and the
heartbeat refresh come from every hook and neither is post-tool only.
`harness/hooks/README.md` § Heartbeat refresh is canonical for the refresh
conditions and states the same set: a payload carrying a host session id,
exactly one coherent run, a lock that is held, pinned, uninterrupted and not
yet stale, a heartbeat older than the refresh interval, and a write made through
`save_run.py heartbeat` as the recorded lock owner. The hook never revives a
stale lock; reclaiming one goes through `save_run.py recover --reason` so the
reclaim leaves audit evidence.

Hooks fail open. The gate validators fail loud: a gate that cannot prove a
package clean must never approve it.

## Gates

Boundary validators check artifact presence, revision consistency, hashes,
required evidence, typed evidence records, and idempotency against a prior
verdict. [gates.yaml](gates.yaml) is the single source of truth for every
boundary; `harness/gatekeeper/check.py` loads it, and a missing or malformed spec
is an engine error, never a pass. Human judgment remains responsible for semantic
quality. When upstream evidence changes, rewind to the earliest affected
boundary.

## State safety

Resolve runtime state in this order, which is what `harness/hooks/_state.py`
implements — `_PROJECT_ENV` at `:48` for the variables, `_ROOT_MARKERS` at `:47`
for the markers, `state_dir()` for the fallback:

1. `SUPREMETEAM_PROJECT_DIR`, the catalog's own variable.
2. The host's project-directory variable, tried in order: `CLAUDE_PROJECT_DIR`,
   `CODEX_WORKSPACE_DIR`, `GITHUB_WORKSPACE`. These exist so the harness lands in
   the right tree when it runs inside a host that already knows the workspace, and
   the first one set wins — none of them is a legacy alias for the first.
3. The verified project root: the nearest ancestor of the working directory
   holding `skillset-saves/`, `.harness-state/`, or `.git`.
4. The working directory itself.
5. A *project-namespaced* directory under the OS temp root — never one temp
   directory shared across unrelated projects.

State lives at `<resolved base>/.harness-state`. No other variable is read: there
is no deprecated or renamed spelling of any of the four that the harness still
honours, so a variable outside this list has no effect rather than a
quietly-supported one.

## Failure paths

The harness exists to behave predictably when something is missing, so its own
degradation paths are normative rather than incidental. Two rules split the
whole space: **a hook that cannot do its job lets the action through, and a gate
that cannot do its job refuses to approve.** Everything below follows from that
asymmetry — an advisory layer failing open costs nothing, an evidence layer
failing open costs the guarantee.

- **A hook errors internally.** It exits without output and the underlying
  action proceeds (§3, *fail open*). Report the degradation where it is
  observable; never convert a hook fault into a block.
- **The host has no hook lifecycle, or hooks are not registered.** Layers 3 and
  4 fall back to their advisory expression in skill prose (§1.1). State that the
  deterministic expression is absent rather than implying it ran, and do not
  record a guard check as performed. `check_readiness.py` reports
  `hooks_observed: unverified` until a hook actually runs, and configuration
  inspection alone never upgrades that.
- **The guard boundary record is absent, empty, or malformed.** Boundary rules
  are inert and only the built-in destructive-pattern guard applies — except for
  `allow_dangerous`, where the direction reverses: an expired or malformed grant
  leaves the block in force, because a guard that cannot read its own grant
  stays closed.
- **The gate engine cannot load or parse its spec.** That is an engine error,
  exit code 2, never a pass and never a verdict. Treat it as `ESCALATE` (§0).
- **A required evidence check is unavailable.** An unavailable or errored typed
  record is a data gap, not a clean result. The verdict is `REVISE` or
  `ESCALATE` with the gap named.
- **A constraint has no reliable enforcement point at its layer.** Name the
  advisory home explicitly (§4) rather than asserting an enforcement that does
  not exist. An overstated guarantee is a worse defect than an admitted gap,
  because a reader stops looking.
- **Two interventions disagree, or one would block a plausibly correct action.**
  §0 decides: the intervention does nothing. An intervention that can fire on a
  competent model's correct action is a defect and is removed or narrowed, not
  documented around.
- **A failure resists classification under §2.** Classify it at the earliest
  category that plainly matches; if none does, it is category 4, residual
  reasoning, and out of scope for the harness. Routing it to an intervention
  anyway is itself a doctrine violation (§2.4).
- **Runtime state cannot be resolved to a writable location.** Fall through the
  order in [State safety](#state-safety) to the isolated temporary directory and
  say that state is transient. Do not scatter state into a subdirectory and do
  not honor a legacy alias to find a writable path.
