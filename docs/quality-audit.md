# Quality audit

Open findings only. Fixed findings are in the [changelog](../CHANGELOG.md).
Scores are in [BENCHMARK.md](../BENCHMARK.md).

## Major

| Id | Area | Finding |
|---|---|---|
| N-1 | Harness | Archive extract (`--strip-components`, `--transform`, `-P`, symlink) reaches guard records |
| N-2 | Harness | `cp -rT backup .` copies over the root unread |
| N-3 | Harness | `git clean` pathspecs `:/`, `'*'`, `-e` patterns slip through |
| N-5 | Harness | Root `unzip` outside a run can overwrite hook files |
| G-3 | Gates | Weakening `gates.yaml` passes every validator |
| P-1 | Pipelines | Repeat deploy cannot pass `deploy-readiness` |
| P-2 | Pipelines | `security_seed` refuses its prescribed applicability record |
| O-3 | Orchestrators | No stage produces `taste_snapshot` for a design run |
| O-4 | Protocol | State machine: unreachable Taste state, no investigation COMPLETE |
| D-2 | Protocol | Run phase states are not mapped to protocol states |

## Minor

| Id | Area | Finding |
|---|---|---|
| H-7 | Harness | Read-only runs allow destructive git ref commands |
| H-9 | Harness | Read-only interpreter access to frozen paths is denied |
| H-10 | Harness | Bash `apply_patch` into a frozen path is allowed |
| N-6 | Harness | Root `rsync --delete` exclude edge cases unread |
| N-8 | Harness | Unknown extractors and runtime-built destinations unseen |
| N-9 | Harness | `cd sub && git clean` falsely denied as root-aimed |
| G-7 | Gates | Typed-record `inputs` follow symlinks out of project |
| G-8 | Gates | Manifest with BOM is misparsed |
| G-9 | Gates | `candidate_ids` not cross-checked against the diff |
| G-10 | Gates | Record checks test shape, not nested values |
| G-11 | Gates | `human_go_required` record is untyped |
| G-13 | Gates | `unchecked_fields` overstates; `cycle_cap` never read |
| P-3 | Pipelines | `qa-review` requires keys only conditional stages produce |
| P-4 | Pipelines | Validators miss four pipeline mutations |
| P-5 | Pipelines | `requires`/`produces` declared only in `design` |
| P-6 | Pipelines | Release and investigation stages precede their guard |
| O-6 | Orchestrators | State names split between runs and protocol |
| O-8 | Orchestrators | Delegation names the Agent tool; none grant it |
| O-9 | Orchestrators | Commander grills the user from a sub-agent |
| O-13 | Orchestrators | `skills_engaged` stored as a JSON string |
| O-14 | Orchestrators | Startup `status` needs a run id first |
| O-15 | Orchestrators | Shipped `mcp-tools.md` timestamp forces intake pause |
| O-16 | Orchestrators | Revision-cap wording and counter sharing unclear |
| O-17 | Orchestrators | Copilot precedence drops Tier 0 |
| D-4 | Doctrine | Loop guard accepts a stale pinned lock |
| D-5 | Doctrine | `_probe-*.tmp` has no ownership class |
| D-6 | Doctrine | Judgement labels deny comparators that exist |
| D-9 | Doctrine | A skill-reviewer duty has no backing |
| D-14 | Doctrine | Delivery example uses Tier 1 for a gated edit |
| D-16 | Doctrine | Taste unreadable-profile fallback contradicts its rule |
| D-17 | Doctrine | `_LAYER_CITATION` accepts any `§1`–`§5` |
| D-19 | Doctrine | Info: dual-verdict, clause-3, TTL, `/exit-admiral` |

## Limits

- Hooks fail open: they prevent accidents, not attacks.
- Hashed evidence proves byte identity, not truth.
