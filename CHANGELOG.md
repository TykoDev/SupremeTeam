# Changelog

All notable changes to Supreme Team are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The catalog has no
release tags yet, so everything sits under Unreleased; each skill carries its own
`version`, and [CONTRIBUTING.md](CONTRIBUTING.md) says when to bump it.

## [Unreleased]

### Added

- Continuous integration. `.github/workflows/ci.yml` runs the seven test suites
  and the validators on Windows, macOS and Linux, on Python 3.13 and 3.14, with
  and without PyYAML. `skills/runtime-manifest.yaml` declares it (`ci_matrix`,
  `ci`) and `validate_manifests.py` fails when the workflow stops covering what
  the manifest declares.
- `LICENSE` (MIT, Copyright (c) 2026 TykoDev), `CONTRIBUTING.md` and this
  changelog.
- `skills/validation/_catalog.py`, shared test support that reads the catalog with
  the production parser, and a test that compares that parser with PyYAML on every
  YAML file and every skill frontmatter.

### Changed

- `commands` in `skills/runtime-manifest.yaml` lists all seven suites. README,
  docs/harness.md and CONTRIBUTING.md list them too and say they need Python 3.13
  or newer.
- `validate_manifests.py` checks the documentation mirrors as tables and counts
  derived from the specs rather than English sentences, resolves manifest paths
  inside the directory it validates, and skips its repository-only checks, saying
  so in its report, in an installed copy.
- The evidence-key documentation check needs the key in backticks, so an ordinary
  English word no longer counts as documenting it.
- The images in `docs/assets` are re-encoded (3.6 MB to 0.5 MB) with the same
  names and aspect ratios.
- `skills/taste/taste_prefs.py` is no longer the only executable file in the tree.
- `.gitignore` also ignores `.DS_Store`, `.env`, `.venv/` and `.claude/worktrees/`.

### Fixed

- `test_pipeline_workflows.py` ran no tests on a host without PyYAML while the
  suite still reported OK. It now reads its inputs the way the gate does.
- Running `test_catalog_contracts.py` directly silently dropped 8 of its tests.
- `runtime-manifest.yaml` listed PyYAML as used only by `quick_validate.py`;
  `validation/trigger_eval.py` requires it as well.
