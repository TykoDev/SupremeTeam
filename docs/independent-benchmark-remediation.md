# Independent benchmark remediation

| Finding | Status | Control |
|---|---|---|
| Install layout drift | Fixed | Both installers read `scripts/install-items.txt` |
| No CI | Fixed | `ci.yml`: 3 OSes × Python 3.13/3.14 × PyYAML on/off |
| Weak gate schema | Fixed | Run manifests must be schema 2 |
| Freeze overclaim | Fixed | Documented as advisory; use OS permissions for hard limits |
| Concurrent checkpoints | Fixed | `_write.lock` held across read-compare-write |
| Engineer circular prerequisite | Fixed | Pipeline `requires`/`produces`; forward dependencies rejected |
| Benchmark overclaim | Fixed | `BENCHMARK.md` states what each figure covers |

## Limits

- Hooks fail open; they prevent accidents, not attacks.
- Hashed evidence proves byte identity, not truth.
- Branch protection and host hook firing are outside the repo.
