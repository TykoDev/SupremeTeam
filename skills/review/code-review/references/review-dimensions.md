# The 8 Review Dimensions — Detailed Guidance

This reference provides in-depth guidance for each of Google's 8 code review dimensions. For each dimension: what to evaluate, questions to ask, common mistakes, and example review comments.

---

## 1. Design

Design is the highest-impact dimension. A wrong design decision affects every line of implementation built on top of it. Evaluate design first — if the approach is fundamentally wrong, line-level feedback is wasted effort.

**What to evaluate:**
- Does this change belong in this location within the codebase?
- Is the overall approach sound? Are there simpler alternatives?
- Are the right abstractions used? Is there unnecessary indirection?
- Does the change respect separation of concerns and existing module boundaries?
- Is the change consistent with the project's architectural patterns?
- Will this design support the next likely change, or will it need to be rewritten?

**Questions to ask:**
- "What were the alternatives considered, and why was this approach chosen?"
- "Does this introduce a new pattern, or follow an existing one?"
- "Could this be achieved by extending an existing abstraction instead of creating a new one?"
- "Does this change affect the system's public API surface?"

**Common mistakes:**
- Introducing a new abstraction layer when the existing one handles the use case
- Creating god objects or god functions that violate single responsibility
- Tight coupling between modules that should be independent
- Designing for hypothetical future requirements instead of current needs
- Moving logic to the wrong layer (business logic in the controller, presentation logic in the model)

**Example review comments:**
- **Blocking:** "This adds a new caching layer, but we already have `CacheManager` in `pkg/cache` that handles this pattern. Let's extend the existing abstraction to avoid two competing caching mechanisms."
- **Question:** "This introduces a direct dependency from `orders` to `notifications`. Should this go through the event bus instead to maintain the decoupling we established in ADR-012?"

---

## 2. Functionality

Verify that the code actually does what the developer intended for all inputs, not just the test cases they wrote.

**What to evaluate:**
- Does the code produce correct results for typical inputs?
- Does it handle edge cases: empty inputs, maximum values, concurrent access?
- What happens with invalid or unexpected input?
- Are there off-by-one errors in loops or conditionals?
- Does the code handle all branches of conditional logic?
- For user-facing changes: is the behavior what users expect?

**Questions to ask:**
- "What happens when `users` is an empty list?"
- "What's the behavior if this API call returns a 500?"
- "Is this function safe to call from multiple goroutines?"
- "What does the user see if this operation fails halfway through?"

**Common mistakes:**
- Only testing the happy path
- Assuming external APIs always return expected data shapes
- Forgetting timezone handling in date operations
- Ignoring partial failure in batch operations
- Not considering what happens when a feature flag is toggled mid-request

**Example review comments:**
- **Blocking:** "When `items` is empty, `items[0]` will throw an IndexError. Need a guard clause before accessing the first element."
- **Nit:** "The comment says this handles both retry and timeout, but the timeout branch returns success instead of an error."

---

## 3. Complexity

"Too complex" means a future reader cannot understand the code quickly. Complexity is the leading cause of future bugs — code that is hard to understand is hard to modify correctly.

**What to evaluate:**
- Can the code be understood in a single reading pass?
- Is there over-engineering (premature abstractions, unnecessary generics)?
- Are there "clever" tricks that sacrifice readability for brevity?
- Is a single function doing too many things?
- Is the control flow straightforward, or does it require mental gymnastics?
- Could a competent developer modify this code without introducing a bug?

**Questions to ask:**
- "Would a new team member understand this in 5 minutes?"
- "Can this nested conditional be simplified with an early return?"
- "Does this abstraction earn its complexity?"
- "Is this generic type parameter needed, or would a concrete type suffice?"

**Common mistakes:**
- Creating utility classes for one-time operations
- Using design patterns (Strategy, Visitor, Abstract Factory) where a simple conditional suffices
- Nested callbacks or promise chains that could be flattened with async/await
- Magic numbers without named constants
- Boolean flags that change function behavior (should be separate functions)

**Example review comments:**
- **Blocking:** "This function is 150 lines with 6 levels of nesting. Could we extract the validation logic into a separate function and use early returns to reduce depth?"
- **Nit:** "The ternary `a ? (b ? c : d) : (e ? f : g)` is hard to parse. An if/else block would be clearer."

---

## 4. Tests

Tests are the safety net that allows confident modification. Evaluate test design, not just test existence. Tests do not test themselves — the reviewer must verify they exercise meaningful behavior.

**What to evaluate:**
- Do tests exist for the changed behavior?
- Do assertions validate actual behavior (not just that code runs without error)?
- Would the test fail if the change were reverted? (Regression value)
- Are error paths and boundary values tested?
- Is test isolation maintained (no shared state between tests)?
- Are tests fast enough to run on every commit?
- Are flaky tests identified and quarantined?

**Questions to ask:**
- "What happens if I remove the implementation — does this test fail?"
- "Is this testing the contract or the implementation detail?"
- "Why is this integration test here instead of a unit test?"
- "Are these mocks verifying behavior or just returning canned data?"

**Common mistakes:**
- Tests that pass when the implementation is empty (testing mocks instead of code)
- Snapshot tests without assertion of specific values
- Integration tests that depend on test execution order
- Tests that only cover the happy path, missing error handling and edge cases
- Excessive mocking that disconnects tests from actual behavior

**Example review comments:**
- **Blocking:** "The test calls `processOrder()` but only asserts the return value is not null. It should verify the order state, inventory update, and notification side effects."
- **Nit:** "This test name `test_1` doesn't describe the scenario. Consider `test_processOrder_withInvalidItem_returnsValidationError`."

---

## 5. Naming

Good names are the cheapest form of documentation. They reduce the need for comments and make code self-documenting.

**What to evaluate:**
- Are names descriptive and unambiguous?
- Do function names describe what the function does (verb-noun pattern)?
- Do variable names describe what they contain (noun pattern)?
- Is name length proportional to scope (short for tight scopes, descriptive for broader)?
- Are abbreviations avoided unless universally understood (e.g., `url`, `id`)?
- Are names consistent with existing conventions in the codebase?

**Questions to ask:**
- "Does `data` tell me what kind of data?"
- "Does `process()` tell me what processing happens?"
- "Is `mgr` clear, or should it be `manager`?"
- "Does this boolean name read naturally in conditionals? (`if isValid` vs `if valid`)"

**Common mistakes:**
- Single-letter variable names outside tight loops
- Generic names: `data`, `result`, `info`, `tmp`, `val`, `obj`
- Misleading names that describe what the code used to do, not what it does now
- Hungarian notation in languages that don't use it by convention
- Inconsistent naming (mixing `getUserById` and `fetchUser` for the same pattern)

**Example review comments:**
- **Nit:** "`handleData()` is vague. Since this validates and transforms the CSV import, `validateAndTransformCsvImport()` would make the purpose clear."
- **Nit:** "`x` in the outer scope at line 42 is used for 30 lines. A descriptive name like `retryCount` would help readability."

---

## 6. Comments

Comments should explain "why," not "what." The code itself shows what happens; comments should capture intent, constraints, trade-offs, and non-obvious decisions.

**What to evaluate:**
- Do comments explain reasoning and constraints, not restate the code?
- Are complex algorithms or non-obvious logic explained?
- Are TODOs tracked with issue references (not just "TODO: fix later")?
- Are comments accurate and up to date with the code?
- Are public API docs complete (parameters, return values, exceptions, examples)?

**Questions to ask:**
- "Does this comment add information that the code doesn't already express?"
- "Will this TODO still be here in 6 months?"
- "Is this docstring accurate after the parameter change?"

**Common mistakes:**
- `// increment i` next to `i++` (restating the obvious)
- Outdated comments that describe removed behavior
- `// HACK: ...` or `// FIXME: ...` without a tracking issue
- Commented-out code left "just in case" (version control handles this)
- Comments apologizing for complexity instead of simplifying the code

**Example review comments:**
- **Nit:** "The comment `// process the list` restates the code. If there's a reason we process items in reverse order, that would be worth commenting."
- **Blocking:** "This TODO has no issue reference. Could we either file a ticket or resolve it now?"

---

## 7. Style

Style is the dimension where human reviewers should spend the least time. Defer to the style guide and automated formatters.

**What to evaluate:**
- Does the code follow the project's official style guide?
- Is the code formatted consistently with the rest of the codebase?
- Are automated formatters and linters configured and passing?

**The absolute authority rule:** The project's style guide is the final word on style questions. If the style guide permits something, accept it — do not impose personal preferences. If the project has no style guide, follow the dominant convention already in the codebase.

**When to comment on style:**
- Only when the style guide is violated and the linter did not catch it
- When the code introduces a new pattern inconsistent with existing conventions
- When readability is significantly impacted (not just preference)

**When NOT to comment on style:**
- When automated formatters handle it (Prettier, Black, gofmt, rustfmt)
- When the style guide is ambiguous and the code is internally consistent
- When it is purely a matter of personal taste

**Example review comments:**
- **Nit:** "Our style guide specifies `const` for all non-reassigned variables. This `let` at line 23 is never reassigned."
- **Avoid:** "I prefer the braces on the same line." (Personal preference, not style guide)

---

## 8. Documentation

Documentation ensures that code changes are discoverable and understandable by future developers and users.

**What to evaluate:**
- Are READMEs updated to reflect new features, changed behavior, or setup requirements?
- Are API docs (OpenAPI/Swagger, JSDoc, pydoc) updated for changed endpoints or function signatures?
- Are changelog entries added for user-facing changes?
- Are migration guides provided for breaking changes?
- Are inline docs updated for changed function behavior?
- Are architecture docs (ADRs, C4 diagrams) updated for structural changes?

**Questions to ask:**
- "If I read the README, would I know about this new feature?"
- "Does the API doc reflect the new parameter?"
- "Will users know how to migrate from the old behavior?"

**Common mistakes:**
- Adding features without updating the README
- Changing function signatures without updating docstrings
- Breaking changes without migration guides
- Auto-generated docs that are never reviewed for accuracy
- Documentation that describes the old API version

**Example review comments:**
- **Blocking:** "This PR adds a required `--format` flag to the CLI but doesn't update the README usage examples."
- **Nit:** "The docstring for `calculateTax()` still says it takes two arguments, but the refactor changed it to three."
