# Health Check Tool Detection

## Goal

Detect the project's existing quality toolchain before running any checks. The
health-check skill wraps the repo's own tools, it does not invent substitute
commands or score the codebase against tools the team has not configured.

## Detection Order

Detect tools in this order so the report stays predictable:

1. Project manifest and lock-in files
2. Dedicated tool configuration files
3. Package scripts or task definitions
4. Executable availability in the environment
5. Explicit overrides in project documentation

If multiple tools could satisfy the same category, prefer the one explicitly
configured by the repo over a generic fallback.

## Category Heuristics

### Type Checking

Use the strongest repo-native type check:

- `tsconfig.json` or `tsconfig.*.json` with TypeScript sources: `tsc --noEmit`
- `pyproject.toml` with `mypy` config: `mypy .`
- `pyrightconfig.json`: `pyright`
- Mixed JS/TS monorepo: use the package-level typecheck script if it exists

If the repo exposes a `typecheck` or `check-types` script, prefer that command
over reconstructing one by hand.

### Linting

Detect linting from explicit config first:

- `biome.json` or `biome.jsonc`: `biome check .`
- `eslint.config.*` or `.eslintrc.*`: `eslint .`
- `pyproject.toml` with Ruff: `ruff check .`
- `oxlint.json` or package script for Oxlint: use the script if present

If the repo has both Biome and ESLint, use the tool the team wired into its
scripts or CI. Do not run both unless the project clearly treats them as
separate required gates.

### Test Runner

Prefer the canonical test script when available:

- `package.json` `scripts.test`
- `pytest` config in `pyproject.toml`
- `Cargo.toml`: `cargo test`
- `go.mod`: `go test ./...`
- multi-package monorepo: use the documented root test command instead of
  guessing a package subset

If the repo exposes multiple test tiers, choose the default suite first and
mention the narrower or slower suites in recommendations rather than blending
them into one score.

### Dead Code Detection

Dead code tools are optional. Detect them conservatively:

- `knip.json`, `knip.ts`, or package dependency on `knip`: `npx knip`
- Python dead-code tooling only if it is explicitly configured

If no dead-code tool is configured, mark the category as `SKIPPED` with reason
`not configured` rather than penalizing the score.

### Shell Linting

Enable shell lint only when both conditions hold:

- `.sh` files or shell entrypoints exist
- `shellcheck` is installed or documented by the repo

For Windows-heavy repos, skip shell lint unless shell scripts are still part of
the supported toolchain.

## Project Type Detection

Use these signals to explain why a category was selected or skipped:

| Signal | Interpretation |
|--------|----------------|
| `package.json` | Node/Bun/JS workspace |
| `pyproject.toml` | Python project |
| `Cargo.toml` | Rust project |
| `go.mod` | Go project |
| Monorepo workspace files | Prefer root scripts over guessed subcommands |

If multiple ecosystems are present, prefer the root orchestrated command so the
dashboard matches how the team actually runs checks.

## Skip Rules

A category is `SKIPPED`, not failed, when:

- the repo has no configuration for that category
- the config exists but the executable is missing
- the category does not apply to the project type

Always record the reason exactly:

- `not configured`
- `configured but tool not installed`
- `not applicable to this project`

## Confirmation Rules

Before execution, show the detected stack and ask for confirmation when the
selection is ambiguous, such as:

- both `eslint` and `biome` are present without a clear primary tool
- multiple test scripts exist with no default documented path
- monorepo root and package-level checks conflict

If the selection is unambiguous, proceed and document the chosen command in the
dashboard.