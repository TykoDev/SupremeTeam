# Example Invocations

Four passes, each rendered in the full packet shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate (`../../../execution-contract.md`,
clause 6). The graded passes carry the shape too, not just the clean one — a
deferred Major is only tracked debt once its owner and reopen trigger travel in
the finding row, and an example that abbreviates the row loses exactly that. Every
row also carries a status drawn from `open | in-progress | resolved | verified |
deferred | not-applicable`, because graded items merge into the gate's `findings`
as `{id, severity, status}` and the gatekeeper rejects an item missing any of the
three.
Severities are the shared four tiers — `Critical | Major | Minor | Info` — and
nothing else.

## Example 1

**User request:** review code quality of the service-layer refactor

**Output:**
- Outcome: quality-review, r3, 2 findings: 0 Critical, 1 Major, 1 Minor, 0 Info.
- Evidence: the service layer, the repository adapter, and the new mapper used by three endpoints, walked against the layering rules in the approved design package; the import graph read for direction and cycles across `services/`, `http/controllers/`, and `mappers/`. The legacy billing package was excluded by the handoff's scope.
- Findings:
  - `QR-01` | Major | `services/` and `http/controllers/` | status `open` | the refactor removes local duplication but adds a second orchestration layer, so business rules now live in two places and every future rule change costs two edits and one decision about where it belongs | consolidate orchestration into one layer before any naming cleanup | not deferred: it blocks the cleanup that follows it.
  - `QR-02` | Minor | `mappers/` | status `open` | the mapper names invert the direction convention used elsewhere, which is friction on reading rather than cost on changing | rename to the established direction convention | not deferred.
- Open risks: the three endpoints in scope are the ones the diff touches; whether the older endpoints already call the second orchestration layer is outside this slice, and a repository-wide call graph would show it.
- Next action: `review/code-chief` routes `QR-01` to the owning build skill before any naming work is scheduled.
- Revision: r3.

## Example 2

**User request:** check maintainability of the job runner

**Output:**
- Outcome: quality-review, r1, 2 findings: 0 Critical, 1 Major, 0 Minor, 1 Info.
- Evidence: the job runner, its queue configuration, and the retry-policy helpers, walked across `jobs/` and `workers/`; the timeout and retry constants traced to every module that declares them; the documented backoff policy read against the implemented curve.
- Findings:
  - `QR-03` | Major (deferred) | `jobs/config.py`, `jobs/queue.py`, `workers/settings.py` | status `deferred` | timeout and retry values are duplicated across three modules, so changing either safely means finding all three | one source of truth, read by the other two | owner: platform team; reopen trigger: the next change to retry behavior.
  - `QR-04` | Info | `workers/backoff.py` | status `verified` | the runner's backoff curve matches the documented policy | recorded so the next round does not re-derive it | not deferred.
- Open risks: the deferral rests on retry behavior staying still; nothing mechanical enforces the reopen trigger, so it holds only as long as the owning team honors it.
- Next action: `review/code-chief` carries `QR-03` into the gate as tracked debt with its owner and trigger intact.
- Revision: r1.

## Example 3

**User request:** measure technical debt in the feature-flag subsystem

**Output:**
- Outcome: quality-review, r2, 2 findings: 0 Critical, 1 Major, 1 Minor, 0 Info.
- Evidence: flag evaluation, environment overrides, and rollout configuration, walked across `middleware/flags.py` and `shared/flag_helper.py` with every call site of both read; the two default-handling branches compared directly; flag definitions read for recorded removal dates.
- Findings:
  - `QR-05` | Major | `middleware/flags.py` and `shared/flag_helper.py` | status `open` | ownership is split between request middleware and a shared helper, so every new rollout path repeats the same branching, and the two copies have already diverged on default handling | move evaluation behind the helper and leave middleware a caller | not deferred: the divergence is already live.
  - `QR-06` | Minor | flag definitions in `config/flags.yaml` | status `open` | three flags have no removal date recorded, so each will outlive its rollout | record a removal date per flag at definition time | not deferred.
- Open risks: the divergence was found by comparing the two default branches; whether any caller already depends on the divergent behavior is a correctness question this lens does not settle.
- Next action: `review/code-review` confirms whether the same split already blocks the diff in flight; `review/code-chief` routes both.
- Revision: r2.

## Example 4 — clean pass

**User request:** is this codebase getting harder to work in — the notifications module

**Output:**
- Outcome: quality-review clean — 0 findings across `notifications/` and its two dependents.
- Evidence: module boundaries walked against the layering rules in the design package; the dependency direction is inward with no cycles; configuration lives in one module; no migration residue or unreferenced abstraction found.
- Findings: (none).
- Open risks: the delivery adapters are behind an interface this scope does not include, so drift on the far side of that seam was not visible to this pass.
- Next action: none from this lens.
- Revision: r4.
