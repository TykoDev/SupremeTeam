# Contributing

Supreme Team checks its own prose: tests compare documents against code and
against each other (counts, table rows, the six execution-contract clauses
copied verbatim). A change that alters behaviour a document describes has to
update that document in the same commit, and the suites will say so when it
does not.

## Requirements

- Python 3.13 or newer. The hooks, gate validators and scripts use the standard
  library only.
- PyYAML is optional. Every suite has to pass with it installed and without it,
  because the catalog parses its own YAML subset
  (`skills/scripts/data_formats.py`) on a clean host.
- Run everything from the repository root, in a checkout. The installer tests
  (`scripts/`) and the CI workflow are not part of an installed copy.

## Run the suites

Seven suites, then the validators. These are the commands CI runs, copied from
`commands` in `skills/runtime-manifest.yaml`:

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"
python -m unittest discover -s skills/validation -p "test_*.py"
python -m unittest discover -s skills/scripts -p "test_*.py"
python -m unittest discover -s skills/taste -p "test_*.py"
python -m unittest discover -s scripts -p "test_*.py"
python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"
python skills/scripts/check_runtime.py
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
```

Lint is a separate CI job. Install the version pinned in `.github/workflows/ci.yml`
(`python -m pip install ruff==0.16.9` today) and run `ruff check .`; the rules and why
each is on are in `ruff.toml`, and `skills/validation/test_lint_config.py` keeps the CI job
and that file in step.

On Windows use `py -3` for `python`. To run one module, pass its file name as the
pattern, for example `-s skills/scripts -p "test_validate_manifests.py"`.

To run without PyYAML, use an environment that does not have it:

```bash
python -m venv .venv
.venv/bin/python -m unittest discover -s skills/validation -p "test_*.py"
```

(`.venv\Scripts\python` on Windows.) A bare virtual environment has no
third-party packages, which is the supported baseline. CI sets
`SUPREMETEAM_PYYAML` to `with` or `without`, and the validation suite fails a
leg whose interpreter disagrees, so a broken install cannot turn tests into
skips. Leave it unset on your machine.

The validation tests read the catalog with `skills/scripts/data_formats.py`, the
parser production uses, through `skills/validation/_catalog.py`. A test that
needs PyYAML says so in its skip message.

## Continuous integration

`.github/workflows/ci.yml` runs the list above on Windows, macOS and Linux, on
every supported Python version, with and without PyYAML. The workflow
implements the `ci_matrix` and `ci` blocks of `skills/runtime-manifest.yaml`,
and `validate_manifests.py` fails when the workflow stops covering a declared
platform, Python version, PyYAML variant or command. Change the manifest and the
workflow together.

A new command goes into `commands` in the manifest, and into either
`ci.commands` (and the workflow) or `ci.not_run` with the reason CI cannot run
it.

## Fail-open and fail-loud

Two rules are policy, not style:

- Hooks fail open. A bug or an unexpected input inside a hook must never lock
  the host, so an internal fault lets the action through. A deny decision stays a
  deny.
- Gate validators fail loud. A gate that cannot prove a package clean never
  approves it: an unreadable record, an unknown evidence kind or a missing file is
  a failure, never a pass.

Do not weaken, skip or delete a test to get a suite green. If a test encodes
behaviour you are changing on purpose, change the test in the same commit and
say so in the message.

## Commits and pull requests

- Subject line `area: what changed`, for example `check_runtime: read a UTF-8
  byte order mark as part of the text`. Add the finding or issue id in
  parentheses when there is one.
- Give a body to every change that alters behaviour. Say why, not what.
- Keep moves and edits in separate commits. A commit that moves code and changes
  what it does hides the second inside the first.
- Land changes through a pull request into `dev`, not by pushing to it.
- Never commit runtime state (`skillset-saves/`, `.harness-state/`) or anything
  shaped like a credential, not even a fake one in a test fixture.

## Skill versions

Every `SKILL.md` carries a `version` in its frontmatter. Bump it when the
skill's behaviour or contract changes: what it does, what it accepts or returns,
the evidence keys it owns, the gate boundary it submits at, the handoff fields it
needs. Use a major bump for a change that breaks a caller, a minor bump for new
behaviour, a patch for a fix. Leave the version alone for edits that change
neither, such as fixing a typo or rewording an example.

Record the change under Unreleased in [CHANGELOG.md](CHANGELOG.md).

## License

By contributing you agree that your contribution is released under the
[MIT License](LICENSE) that covers the repository.
