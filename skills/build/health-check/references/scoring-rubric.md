# Health Check Scoring Rubric

## Tool Output Parsing

### TypeScript (tsc --noEmit)

Count lines matching `error TS` in output.

| Error Count | Score |
|------------|-------|
| 0 | 10 |
| 1-3 | 9 |
| 4-9 | 8 |
| 10-19 | 7 |
| 20-34 | 5 |
| 35-49 | 4 |
| 50-99 | 2 |
| 100+ | 0 |

### Biome / ESLint / Ruff

Count lines matching error/warning patterns. Parse the summary line if available.

| Warning/Error Count | Score |
|--------------------|-------|
| 0 | 10 |
| 1-2 | 9 |
| 3-4 | 8 |
| 5-9 | 7 |
| 10-14 | 5 |
| 15-19 | 4 |
| 20-49 | 2 |
| 50+ | 0 |

### Test Runner

Parse pass/fail counts from the test runner output. If the runner only reports exit code:
- Exit 0 → score 10
- Exit non-zero → score 4 (assume some failures)

| Pass Rate | Score |
|----------|-------|
| 100% | 10 |
| 98-99% | 9 |
| 95-97% | 8 |
| 90-94% | 7 |
| 85-89% | 5 |
| 80-84% | 4 |
| 70-79% | 2 |
| <70% | 0 |

### Knip (Dead Code)

Count lines reporting unused exports, files, or dependencies.

| Unused Count | Score |
|-------------|-------|
| 0 | 10 |
| 1-2 | 9 |
| 3-4 | 8 |
| 5-9 | 7 |
| 10-14 | 5 |
| 15-19 | 4 |
| 20+ | 2 |

### ShellCheck

Count distinct findings (lines starting with "In ... line").

| Finding Count | Score |
|--------------|-------|
| 0 | 10 |
| 1-2 | 9 |
| 3-4 | 8 |
| 5-9 | 5 |
| 10+ | 2 |

---

## Weight Redistribution

When a category is skipped, redistribute its weight proportionally:

```
adjusted_weight(category) = original_weight / (1 - sum_of_skipped_weights)
```

Example: If shell lint (10%) is skipped, the remaining categories redistribute among 90%:
- Type check: 25/90 = 27.8%
- Lint: 20/90 = 22.2%
- Tests: 30/90 = 33.3%
- Dead code: 15/90 = 16.7%

---

## Trend Delta Interpretation

| Delta | Interpretation |
|-------|---------------|
| +2 or more | Significant improvement |
| +0.5 to +1.9 | Modest improvement |
| -0.5 to +0.4 | Stable |
| -0.5 to -1.9 | Slight regression — investigate |
| -2 or more | Significant regression — prioritize fixes |
