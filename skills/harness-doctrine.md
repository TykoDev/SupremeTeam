# Runtime Harness Doctrine

Binding rules for how every skill adapts the interface between the model and its
environment, not the model itself. The harness adds five layers without changing
the pipeline: entry routing, persistent context, phase trajectory, evidence
gates, and action guardrails. Skills and gates cite this doctrine by section
number.

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
| Environment Contract | `design-doctrine.md`, `grill-me-doctrine.md`, `mcp-tools.md`, `tech-stacks/registry.yaml`, `execution-contract.md`, per-skill `intake-brief.yaml` | doctrine plus gate review |
| Procedural Skill | the skill library, `pipelines.yaml`, `session-memory` learnings | doctrine plus authoring |
| Action Realization | `safety-guardrails/*`, the save write probe, gate pre-checks, `harness/hooks/pre_tool_use.py` | advisory plus deterministic hook |
| Trajectory Regulation | gatekeepers, checkpoints, rewind rules, the revision cap, `harness/hooks/post_tool_use.py` | per boundary plus per step |

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

## Hooks

`harness/hooks/pre_tool_use.py` enforces valid guarded write boundaries and
denies edit-tool writes to core run files. `post_tool_use.py` records trajectory
observations and refreshes the pinned run's heartbeat from real host activity.
`user_prompt_submit.py` advises front-door and session-pin routing.
`save_run.py` is the only writer of the run record. `verify_registration.py`
inspects native host configuration without mutating it;
`repair_registration.py` previews a scoped repair and applies it only with
explicit approval; `check_readiness.py` reports Python, hooks, and save state as
independent capability facts and never claims a hook fired from config
inspection alone. Registration requires explicit user approval.

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

Resolve runtime state beneath `SUPREMETEAM_PROJECT_DIR` when set, then the
verified project root, then an isolated temporary harness state directory. Do not
read or honor legacy aliases.
