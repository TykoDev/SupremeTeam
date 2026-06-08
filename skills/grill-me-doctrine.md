# Grill-Me Intake Doctrine

Binding interview rules for every initial intake and planning step in the catalog. Any skill that takes a fresh request, confirms scope, or produces a first plan/design MUST run this protocol before delegating work or committing to a deliverable. A plan that was accepted without this interview is not gate-eligible — downstream gatekeepers may reject it for skipped intake.

Skills bound by this doctrine: `admiral`, `commander`, `skill-maker`, `researcher`, `planner`, `architect`, and `architect`'s frontend/UI design step.

## 1. Core Mandate

Interview the user relentlessly about every aspect of the plan or design until you reach a **shared understanding**. Do not accept a vague request and start building. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one until no load-bearing ambiguity remains.

## 2. The Five Rules

1. **Resolve every branch.** Treat the plan as a decision tree. For each node, surface the decision that must be made, resolve it, and only then descend into the branches that decision unlocks. Do not leave a branch unresolved because it is uncomfortable or far away.

2. **One question at a time.** Ask a single question, wait for the answer, then ask the next. Never dump a numbered wall of questions. Each answer reshapes the tree, so the next question depends on the last. This rule governs how *you ask*, not how the user may *answer* — a user is free to resolve several branches in one message, and you absorb that without complaint (see §5).

3. **Resolve dependencies in order.** Order questions so that a decision is only asked once its prerequisites are settled. Do not ask about rollout cadence before the release shape is known, or about component boundaries before the scope is agreed.

4. **Always recommend an answer.** Every question carries your recommended answer plus a one-line rationale. The user can accept, override, or refine — but they are never handed a blank prompt. A question without a recommendation is incomplete.

5. **Explore the codebase instead of asking.** If a question can be answered by reading the code, configs, existing artifacts, or git history, go find the answer yourself. Only ask the user about things the codebase cannot tell you: intent, priorities, constraints, and tradeoff preferences. Reserve the user's attention for genuine judgment calls.

## 3. When the Interview Ends

The interview is complete only when:

- Every branch of the decision tree that affects the deliverable is resolved or explicitly deferred with a recorded reason.
- No assumption material to the plan remains unstated.
- The user has confirmed the shared understanding back, or has explicitly delegated remaining calls to your recommendations.

Record the resolved decisions and any explicitly deferred branches in the intake/plan artifact so downstream phases inherit the shared understanding rather than re-deriving it.

## 4. Planning Mode Decision Prompt Contract

When the host exposes a planning-mode or structured user-input primitive, bound skills MUST use it for unresolved design and configuration decisions. In Codex this means `request_user_input` when it is available; in other hosts it means the closest native choice prompt. If no native prompt exists, ask the same decision as a concise plain-text question.

This contract is automatic. The user does not need to request "planning mode" or "ask me decisions." Any fresh intake, plan, architecture, frontend design, deployment setup, security posture, data model, API contract, or configuration surface must run this decision prompt loop before the deliverable is generated or delegated.

Prompt rules:

1. **One decision per prompt.** Ask exactly one load-bearing design/configuration decision at a time. Do not bundle unrelated choices into one "topic group."
2. **Recommended option first.** Provide 2-3 mutually exclusive options, put the recommended one first, and include a one-line rationale tied to the current project evidence.
3. **Auto-resolve discoverable configuration.** If files, package manifests, environment config, prior artifacts, or saved state prove the answer, record it as resolved without asking. If the discovered evidence conflicts, ask the user to choose which source wins.
4. **Ask judgment calls without delay.** Decisions about product behavior, API compatibility, authentication model, data retention, billing/limits, deployment target, rollout risk, UI personality, density, accessibility tradeoffs, and other non-discoverable preferences must be prompted automatically.
5. **Offer delegation as a valid answer.** When appropriate, one option may let the user delegate the decision to the recommended default. Record delegated defaults explicitly so downstream gates can see that the user accepted the recommendation.
6. **Block generation on unresolved decisions.** Do not produce a plan/design/configuration package that depends on an unasked, unresolved decision. Either resolve it, record a deliberate deferral with owner and deadline, or narrow the package so the decision is no longer load-bearing.

Every planning artifact includes a **Decision Register** with:

- Resolved decisions, their source (`user`, `codebase`, `prior-artifact`, or `delegated-default`), and the chosen option.
- Deferred decisions, why they are safe to defer, who owns them, and which downstream phase must reopen them.
- Rejected options for material tradeoffs, with one-line rationale.

## 5. Scaling the Interview

- **Trivial, fully-specified requests** still get at least one confirmation pass: restate your understanding, state your recommended approach, and give the user a chance to correct before proceeding.
- **Ambiguous or high-stakes requests** get the full relentless treatment — keep grilling until rule 3's end conditions are genuinely met, not until the user seems tired.
- **Resumed runs** re-confirm only the branches whose inputs changed; do not re-grill settled decisions, but do verify the prior shared understanding still holds.
- **Front-loaded / multi-branch answers.** When a user answers several branches in one message or supplies a comprehensive brief up front, map each answer to its decision node, record the resolved decisions, and resume the interview at the next *unresolved* branch — never re-ask a settled decision, and never reject the input for arriving out of "one question at a time" order. Rule 2 governs how you *ask*, not how the user may *answer*; the zero-load-bearing-ambiguity standard (§1) is unchanged — any branch the message leaves unresolved is still grilled normally. This is always-on behavior, not a mode the user must request.

## 6. Integration Contract

Each bound skill references this doctrine from its initial intake/planning step and runs the protocol before producing or delegating any deliverable. The interview output (resolved decisions, deferred branches, stated assumptions) becomes part of the intake brief or plan that the skill hands downstream.
