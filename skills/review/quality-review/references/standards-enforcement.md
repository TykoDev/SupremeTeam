# Standards Enforcement — Language-Specific Guides and Tooling

This reference provides detailed language-specific standards, tool configurations, and the three-layer automation stack implementation.

---

## The Three-Layer Automation Stack

### Layer 1: Baseline Hygiene

Every PR must pass formatters, linters, and type checkers before human review begins. This eliminates style debates, catches common mistakes, and frees human reviewers for design and logic review.

**Implementation pattern:**
1. Configure tools in the project root (config files committed to repo)
2. Add pre-commit hooks for fast local feedback
3. Add CI jobs that fail the build on violations
4. Use auto-fix where possible (formatters, some lint rules) to reduce developer friction

### Layer 2: Semantic Analysis

Deep analysis engines that understand code meaning beyond syntax:
- Quality gate tools (SonarQube) that aggregate multiple quality dimensions
- Inter-procedural analyzers (Infer) that trace bugs across function boundaries
- Semantic pattern matchers (CodeQL, Semgrep) that understand code structure

**Implementation pattern:**
1. Configure quality gates with pass/fail thresholds on new code
2. Integrate into CI with SARIF output for unified triage
3. Suppress false positives with documented justifications
4. Review new findings weekly, feed recurring patterns into Layer 1 rules

### Layer 3: AI-Assisted Review

Contextual analysis that evaluates design, intent, and cross-file dependencies:
- AI code review tools (CodeRabbit, GitHub Copilot Code Review, Cursor BugBot)
- Intent analysis comparing the change against its PR description
- Change risk scoring based on historical defect patterns

**Implementation pattern:**
1. Deploy as non-blocking CI check initially
2. Track acceptance rate of AI suggestions
3. Promote high-confidence categories to blocking checks as trust builds
4. Maintain human review for design, architecture, and business logic

---

## JavaScript / TypeScript

### Style Guide: Airbnb JavaScript Style Guide

The most widely adopted JavaScript style guide. Key rules:

**Variables:**
- Use `const` for all references that are not reassigned. Use `let` for reassigned references. Never use `var`.
- Block scoping via `let`/`const` prevents hoisting bugs and scope leakage.

**Objects and Arrays:**
- Use object shorthand (`{ name }` instead of `{ name: name }`)
- Use computed property names when creating objects with dynamic keys
- Use array spreads `[...items]` to copy arrays

**Functions:**
- Use arrow functions for anonymous functions (lexical `this`)
- Use default parameters instead of mutating arguments
- Never use `arguments` object — use rest params `(...args)`

**Modules:**
- Always use ES modules (`import`/`export`), not CommonJS (`require`)
- Use named exports over default exports for discoverability

### Formatters and Linters

**Prettier (Formatter):**
- Config: `.prettierrc` with `printWidth: 80`, `singleQuote: true`, `trailingComma: 'all'`
- Run on save in IDE and as CI gate
- Eliminates all formatting debates

**ESLint v10 (Linter):**
- Multi-threaded execution for faster CI runs
- Extended beyond JS to CSS, HTML, JSON, Markdown
- Configure with `eslint-config-airbnb` for Airbnb rules
- Integrate with Prettier via `eslint-config-prettier` to avoid conflicts

**Oxlint (Alternative Linter):**
- Rust-powered, 50–100x faster than ESLint
- Use for extremely large monorepos where ESLint CI time exceeds 5 minutes
- Covers most common ESLint rules with zero configuration

### Type Checking

**TypeScript Strict Mode:**
- Enable `strict: true` in `tsconfig.json` (gold standard)
- Includes: `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`
- Catches type errors at compile time that would otherwise surface as runtime bugs

---

## Python

### Style Guide: PEP 8

The official Python style guide. Enforced automatically via Ruff.

### Formatters and Linters

**Ruff (Formatter + Linter):**
- Rust-based, 10–100x faster than Flake8/Pylint combined
- Single binary replaces: Flake8, Black, isort, pydocstyle, pyupgrade, autoflake
- Adopted by major projects: FastAPI, Pandas, Apache Airflow
- Config: `pyproject.toml` with `[tool.ruff]` section
- Key settings:
  ```toml
  [tool.ruff]
  line-length = 88
  target-version = "py312"

  [tool.ruff.lint]
  select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "SIM"]
  ```

### Type Checking

**mypy:** Most widely used (58% of Python developers). Strict mode: `--strict` flag.

**Pyright:** 3–5x faster than mypy. Powers VS Code's Pylance extension. Better for incremental checking during development.

**ty (Astral):** Beta. 80x faster than Pyright on incremental checks (4.7ms vs 386ms on PyTorch). From the creators of Ruff. Watch for production readiness.

**The enforcement gap:** Only 41% of Python developers run type checkers in CI, despite 73% using type hints. Enforce type checking in CI to close this gap.

---

## C# / .NET

### Style Guide: .editorconfig

Microsoft enforces code style natively through `.editorconfig` files integrated into Visual Studio and the .NET SDK.

**Key rules to enforce:**
- `dotnet_style_object_initializer = true` (IDE0017) — Use object initializers
- `csharp_style_inlined_variable_declaration = true` (IDE0018) — Inline variable declarations
- `csharp_style_throw_expression = true` (IDE0016) — Use throw expressions
- `dotnet_style_prefer_auto_properties = true` (IDE0032)

**Enforcement levels:** Set to `warning` or `error` in CI builds:
```editorconfig
[*.cs]
dotnet_style_object_initializer = true:warning
csharp_style_inlined_variable_declaration = true:warning
```

**CI Integration:** Use `dotnet format --verify-no-changes` to fail builds on style violations.

---

## Rust

### Style Guide: The Rust Style Guide

Establishes default formatting to lower the barrier to entry and reduce cognitive overhead.

### Tooling

**rustfmt (Formatter):** Canonical Rust formatter. Configure via `rustfmt.toml`. Run as part of CI.

**clippy (Linter):** Official Rust linter with 600+ lint rules. Categories:
- `correctness`: Likely bugs (highest priority)
- `suspicious`: Code that is probably wrong
- `style`: Non-idiomatic code
- `complexity`: Unnecessarily complex code
- `perf`: Performance anti-patterns

**AI-Generated Rust Concerns:** AI coding agents frequently generate Rust code that passes tests but is highly non-idiomatic. Common issues:
- Unnecessary `clone()` calls instead of proper borrowing
- Using `unwrap()` throughout instead of error propagation with `?`
- Ignoring lifetime annotations by boxing everything
- Missing `#[derive(...)]` attributes
- Manual implementations of traits that exist in std

Enforce strict clippy checks (`-D warnings`) in CI and require manual review of AI-generated Rust for idiomatic quality.

---

## Go

### Style Guide: Effective Go + Go Code Review Comments

Go's style is largely dictated by `gofmt` (no debates) supplemented by `Effective Go` and the Go Code Review Comments wiki.

### Tooling

**gofmt:** Non-negotiable. All Go code is `gofmt`-formatted. Refuse PRs that aren't.

**golangci-lint:** Meta-linter that runs 100+ Go linters with unified config (`.golangci.yml`). Key linters to enable:
- `errcheck`: Verify error returns are checked
- `govet`: Report suspicious constructs
- `staticcheck`: Advanced static analysis
- `gosec`: Security-focused analysis
- `exhaustive`: Enforce exhaustive enum switches

**`go vet`:** Built-in static analysis. Always enable in CI.

**`go test -race`:** Race detector. Always enable for test runs in CI. Catches data races at runtime.

---

## Cross-Language Quality Patterns

### Common Anti-Patterns to Flag

Regardless of language, flag these quality anti-patterns:

1. **Copy-paste duplication:** Same logic repeated in 3+ locations without extraction
2. **God functions/classes:** Single units exceeding 200 LOC or 10 dependencies
3. **Primitive obsession:** Using strings/ints where domain types are needed (e.g., `string email` vs `Email email`)
4. **Missing error handling at system boundaries:** Errors from external APIs, file I/O, network calls not handled
5. **Hardcoded configuration:** Values that should be configurable embedded in code
6. **Mixed abstraction levels:** High-level orchestration mixed with low-level implementation in the same function
7. **Dead code:** Commented-out code, unreachable branches, unused imports/variables
8. **Inconsistent patterns:** Different approaches to the same problem in the same codebase

### Universal Quality Gate Configuration

Minimum CI quality gate for any language:
1. Formatter passes (zero formatting changes needed)
2. Linter passes (zero violations at configured severity)
3. Type checker passes (if applicable)
4. Test suite passes with coverage threshold maintained
5. No new critical/major static analysis findings
