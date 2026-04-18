# DX Scorecard — Calibration Anchors & Evidence Methods

## Calibration Anchors by Dimension

### Getting Started (TTHW Focus)

| Score | Calibration Example |
|-------|-------------------|
| 10 | Stripe: `pip install stripe` → 3 lines of code → working API call. <2 min. |
| 8 | Vercel: `npx create-next-app` → deployed. <5 min. One decision point (TypeScript?). |
| 6 | AWS SDK: Install → configure credentials → find the right service client → working call. ~10 min. |
| 4 | Kubernetes: Install kubectl → configure cluster → write YAML → deploy. ~20 min. Many concepts. |
| 2 | Legacy enterprise: Download installer → license key → configure XML → restart → pray. >30 min. |
| 0 | Cannot complete without calling support or reading a 50-page PDF. |

### API/CLI/SDK Ergonomics

| Score | Calibration Example |
|-------|-------------------|
| 10 | Stripe API: `customer.create()`, `invoice.pay()` — verb-noun, consistent, discoverable |
| 8 | GitHub CLI: `gh repo create`, `gh pr list` — consistent subcommand pattern |
| 6 | AWS CLI: Consistent but verbose. `aws s3api put-bucket-versioning` is discoverable but wordy. |
| 4 | Mixed patterns: some endpoints are REST, some are RPC, naming inconsistent |
| 2 | Undiscoverable: need to read source code to find the right method |
| 0 | No public API surface, or API changes without versioning |

### Error Messages

| Score | Calibration Example |
|-------|-------------------|
| 10 | Elm/Rust compiler: Shows what went wrong, where, why, and suggests fixes with code examples |
| 8 | TypeScript: Clear error with source location, type mismatch explanation |
| 6 | Python: Traceback is readable, error message is descriptive |
| 4 | Generic messages: "Invalid input" without specifying which input or why |
| 2 | Error codes only: "Error E4502" with no inline explanation |
| 0 | Raw stack traces, internal exceptions, or silent failures |

### Documentation

| Score | Calibration Example |
|-------|-------------------|
| 10 | Stripe docs: Searchable, versioned, copy-paste examples, language switcher, interactive |
| 8 | MDN Web Docs: Comprehensive, well-organized, good examples, community-maintained |
| 6 | Most framework docs: Getting started exists, API reference exists, some gaps in advanced topics |
| 4 | README-only: Basic usage in README, no separate docs site, incomplete examples |
| 2 | Outdated docs: Documentation exists but describes a prior version |
| 0 | No documentation, or auto-generated docs with no human curation |

### Upgrade Path

| Score | Calibration Example |
|-------|-------------------|
| 10 | Angular: Major version upgrade guide, automated migration schematics, deprecation warnings 2 versions ahead |
| 8 | React: Clear CHANGELOG, migration guide for breaking changes, codemods available |
| 6 | Most libraries: CHANGELOG exists, breaking changes noted, but no automated migration |
| 4 | CHANGELOG exists but is developer-facing (commit messages), no migration guidance |
| 2 | No CHANGELOG, breaking changes discovered by users |
| 0 | No versioning strategy, changes break without warning |

### Developer Environment

| Score | Calibration Example |
|-------|-------------------|
| 10 | Single command setup (`make dev`), CI mirrors local, full type coverage, rich test utilities |
| 8 | Clear README setup, CI exists, types exist, basic test setup |
| 6 | Setup works but requires manual steps, CI exists but is basic |
| 4 | Setup requires tribal knowledge, CI is flaky, types are incomplete |
| 2 | "Works on my machine" — no documented setup, no CI |
| 0 | Cannot set up development environment without help from the team |

### Community & Ecosystem

| Score | Calibration Example |
|-------|-------------------|
| 10 | Active Discord/forum, issue templates, fast response time, contributor guide, RFC process |
| 8 | GitHub Discussions active, issue templates exist, most issues get response within a week |
| 6 | Issues are tracked, contributing guide exists, community channels exist but are quiet |
| 4 | Issues are tracked but response is slow, no contributing guide |
| 2 | Issues pile up with no response, no community channels |
| 0 | No public issue tracker, no way to report bugs or contribute |

---

## Evidence Collection Methods

| Method | When to Use | How to Record |
|--------|------------|--------------|
| **TESTED** | Live surfaces (web docs, CLI, API playground) | Screenshots, command output, timing |
| **PARTIAL** | Mix of live and file-based | Screenshots for live, file references for inferred |
| **INFERRED** | File-based only (README, CHANGELOG, config) | File path and relevant content excerpt |

### Screenshot Best Practices

- Capture the full viewport, not just a cropped section
- Include the URL bar when testing web surfaces
- Annotate screenshots with callouts for specific issues
- Name files descriptively: `getting-started-step3-error.png`

### CLI Output Best Practices

- Capture the full command and output
- Include the exit code
- Truncate output at 50 lines if longer (note "truncated, N total lines")

---

## Composite Score Calculation

The overall DX score is a weighted average:

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| Getting Started | 25% | First impression, adoption driver |
| API/CLI/SDK | 20% | Daily usage quality |
| Error Messages | 15% | Debugging experience |
| Documentation | 15% | Self-service resolution |
| Upgrade Path | 10% | Long-term maintenance |
| Dev Environment | 10% | Contributor experience |
| Community | 5% | Support ecosystem |

```
overall = Σ(dimension_score × dimension_weight)
```

**Rounding:** Round to one decimal place.
