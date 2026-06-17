# Runtime Harness Doctrine

Binding rules for how every skill in the catalog adapts the **interface** between the model
and its environment — not the model itself. This doctrine is the SupremeTeam adaptation of
*LIFE-HARNESS: Adapting the Interface, Not the Model* (Xu, Wen & Li, 2026). It gives skill
authors and gatekeepers a shared vocabulary, a failure taxonomy, and an enforcement
discipline. Skills and gates cite this doctrine by section number, exactly as frontend work
cites `design-doctrine.md`.

## 0. Thesis and the Model-Agnostic Principle

An agent's behavior is shaped not only by its model but by the **runtime harness** that
mediates how it observes, calls tools, realizes actions, interprets feedback, and regulates
multi-step trajectories. SupremeTeam adapts that harness — through doctrine, contracts, and
hooks — while leaving the model and the host environment unchanged.

**Model-Agnostic Principle (non-negotiable).** SupremeTeam runs across whatever backbone the
host provides. Every harness intervention must **rescue a weak backbone without degrading a
strong one.** An intervention that helps a small/local model but interferes with a competent
model's correct action is a defect, not a feature. When in doubt, the intervention does
nothing. This mirrors the paper's finding that gains are large on weak models and shrink
toward zero on strong ones — so interventions must be inert on the strong case.

## 1. The Four Lifecycle Layers

Every cross-cutting constraint in the catalog belongs to exactly one of these layers. Authors
must name the layer when they add a constraint; gates check that the constraint sits at the
earliest layer where it is reliably enforceable.

| # | Layer | When it acts | What it does |
| --- | --- | --- | --- |
| 1 | **Environment Contract** | before interaction | Make stable tool, policy, and format constraints explicit so generic priors don't collide with environment rules. |
| 2 | **Procedural Skill** | task conditioning | Retrieve a compact, reusable procedure for the current task and surface it before work starts. |
| 3 | **Action Realization** | before execution | Validate, canonicalize, or **block** a generated action before it touches the environment. |
| 4 | **Trajectory Regulation** | after execution | Detect degenerate patterns (loops, stagnation, empty-output streaks, budget exhaustion) and inject recovery. |

### 1.1 Mapping to existing SupremeTeam mechanisms

This doctrine is mostly a **renaming and tightening** of structure that already exists. New
work attaches to the right layer rather than inventing a parallel system.

| Layer | Where it already lives | Enforcement today |
| --- | --- | --- |
| Environment Contract | `design-doctrine.md`, `grill-me-doctrine.md` (intake interview), `mcp-tools.md` (`discovery_ttl_hours` freshness, default 480h), per-skill `intake-brief.yaml`, tool-description discipline | doctrine + gate review |
| Procedural Skill | the skill library itself, `session-memory` durable learnings, skill retrieval | doctrine + authoring |
| Action Realization | `safety-guardrails/guard|freeze|careful`, save-protocol write-capability probe, gatekeeper pre-checks, **`harness/hooks/pre_tool_use.py`** | advisory **+ deterministic hook** |
| Trajectory Regulation | gatekeepers, `session-memory` checkpoints, admiral rewind rule, max-2-revisions, context-tier escalation, **`harness/hooks/post_tool_use.py`** | per-boundary **+ per-step hook** |

The only place SupremeTeam can deterministically intercept a tool call is a
host-provided hook or plugin lifecycle, because skills are instructions running
*inside* the host loop and do not own that loop. Layers 3 and 4 therefore have
both an advisory expression (skill prose) and, where the host supports compatible
hooks, a deterministic expression (`harness/hooks/`) registered through the
host-native configuration. See `harness/hooks/README.md`.

## 2. Failure Taxonomy and Priority Order

When a recurring failure is observed, classify it by the **earliest** matching category. The
priority order prevents a downstream symptom (e.g. budget exhaustion) from masking the root
interface failure (e.g. a tool call emitted as plain text).

1. **Action-realization failure** — intent was reasonable but not submitted in an executable
   form (plain-text "tool call", invalid arguments, malformed schema). → Layer 3.
2. **Environment-contract mismatch** — the call is executable but violates tool bounds,
   calling order, or argument semantics (wrong tool, premature finish, bad format). → Layer 1.
3. **Trajectory degeneration** — actions are valid but the episode loops, stagnates, retries
   the same failing command, or exhausts budget without progress. → Layer 4.
4. **Residual reasoning failure** — protocol is followed but the logic, computation, or
   value selection is wrong. **Out of scope for the harness** — do not paper over reasoning
   errors with interface tricks.

Categories 1–3 are harness-addressable. Category 4 is not; routing a reasoning failure to a
harness intervention is itself a doctrine violation.

**Worked example (category 4 — not harness-addressable).** A well-formed command executes
cleanly (zero exit) but a unit test run afterward fails because the logic is wrong. This is a
**residual reasoning failure**, not an action-realization or trajectory failure — do **not**
route it to a Layer-4 recovery hint or a Layer-3 block. `harness/hooks/post_tool_use.py`
deliberately does not fire here: it triggers only on ≥3 identical *failing* actions, an
empty-output streak, or A,B,A,B oscillation — never on a single valid-but-semantically-wrong
action. Concluding "this edit caused that test failure" would require correlating two distinct
tool calls by causal inference, which is exactly the guess §3 ("evidence-triggered") forbids.
A failing test is itself a fresh, well-formed signal the model can read and act on; the harness
stays out of the way and lets the model reason about it.

## 3. Engineering Discipline (Non-Negotiables)

Lifted from the paper's harness-evolution constraints (Appendix A.2). Every harness
intervention — a doctrine clause, a hook rule, a guard boundary — must satisfy all of:

- **Local and minimal.** Address one precise failure pattern. No broad rewrites.
- **Evidence-triggered.** Fire only on precise, mechanically detectable environment or
  trajectory signals — never on a hunch or a guess about intent.
- **Never override ambiguous reasoning.** If the correct action is ambiguous, do nothing and
  let the model decide. (Direct corollary of §0.)
- **No oracle / hidden labels.** An intervention may expose stable environment-side structure;
  it must never use evaluation answers, success labels, or anything the agent could not
  legitimately observe at runtime.
- **Regression check is mandatory.** Before an intervention ships, confirm it does not block a
  valid action, inject misleading guidance, or degrade a path that previously worked. If it
  over-triggers, narrow it or roll it back. Hook changes must run the stdlib suite in
  `harness/hooks/test_hooks.py` or add an equivalent regression case for the changed rule.
- **Fail open.** A harness mechanism that errors must let the underlying action proceed, never
  crash or hard-block the host. (Same posture as the save-protocol probe: on failure, degrade
  to no-op and continue.)

## 4. Author Checklist

When adding or changing a cross-cutting constraint, confirm:

- [ ] The constraint is assigned to exactly one of the four layers (§1).
- [ ] It sits at the earliest layer where it is reliably enforceable (§2 priority order).
- [ ] It targets a harness-addressable failure (categories 1–3), not residual reasoning (§2.4).
- [ ] It satisfies every non-negotiable in §3 — especially *inert on the strong case* (§0).
- [ ] If it is deterministically enforceable, it is expressed as a hook rule, not only prose
      (§1.1). If it cannot be, the advisory home is named.
- [ ] A regression note records what was checked for over-triggering.
- [ ] Hook changes include an automated test or an explicit reason the existing suite already
      covers the changed behavior.

## 5. Gate Behavior

Gatekeepers (`gatekeeper-admiral`, `gatekeeper-design`, `gatekeeper-build`, `gatekeeper-code`)
and the skill-authoring review (`skill-reviewer`) must reject a package or skill that:

- Adds a cross-cutting constraint without naming its lifecycle layer (§1).
- Places a constraint at a later layer than where it is enforceable (§2).
- Routes a residual reasoning failure to a harness intervention (§2.4).
- Ships an intervention that can fire on a competent model's correct action (§0, §3).
- Omits the regression note for a new or changed intervention (§3).

Reviewers cite this doctrine by section number when issuing findings.
