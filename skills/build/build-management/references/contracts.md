# Contracts Reference

The full normative text of every contract `../SKILL.md` binds the build phase to.
The SKILL.md section of the same name carries one decision line per contract and
points here; this file is the single statement of the procedure behind each, so
neither document paraphrases the other.

## Contents

1. Vendoring detection — the mechanical rule that classifies a changed path, and the tighter rules that follow
2. Coverage destination — where a delegated test step sends its coverage output
3. Save-Protocol Adherence — what to persist and what to propagate

## The Contracts

- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes. The rule is mechanical rather than a judgment call. A changed path is non-first-party when it sits under a vendor or generated root (`vendor/`, `third_party/`, `node_modules/`, `dist/`, or any directory the generated-root policy declares), when its name or header marks it as machine-produced (a "do not edit" or generated banner, `*.generated.*`, `*_pb2.py`, `*.lock`), or when it entered the diff through a package manager or codegen step rather than an authored edit. Each such path is then listed with its upstream source and version, the owner who accepted it, and its scan note; it is excluded from first-party coverage and completeness claims rather than counted toward them; and it is never hand-edited, because an edit the next regeneration erases is not a fix — change the generator and regenerate.
- **Coverage destination**: Coverage data files and coverage reports are run evidence, never project-root residue, and the delegation says so. Every `### Save Context` block for a step that runs tests names `skillset-saves/runs/<run-id>/build/evidence/coverage/` — resolved with `python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind coverage --name .coverage --mkdir` — as the coverage destination alongside the `evidence/` log path. The delegate points `COVERAGE_FILE` / `--data-file`, `--cov-report=<fmt>:<dest>/...`, `--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir` at it, never runs coverage in parallel or per-process mode (`-p`, `--parallel-mode`, `parallel = True`) without finishing the same command with `coverage combine` into that destination, and never loops a coverage run per test file. A step hands back with nothing named `.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`, or `.nyc_output/` at the project root; one observed run left a `.coverage` tree of over three thousand files there in under two minutes. The build owner treats such residue as an unfinished step, not a cosmetic issue — `harness/hooks/post_tool_use.py` relocates it into the run, but a sweep that had to run means the destination was never named.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.
