# run-audit

Audit the saved-run history and harness observations of a Supreme Team
checkout. Zero dependencies beyond the Python standard library (>= 3.13).

## Usage

```
python run_audit.py --project-root <checkout> --out <dir> [--format json|html|both]
                    [--fail-on none|high|any]
python run_audit.py --version
```

- Reads `skillset-saves/runs/` (audit trails, run state, phase manifests, gate
  verdicts, declared artifact hashes) and `.harness-state/` (hook observations,
  trajectories). Reads only; never writes under either root.
- Writes `report.json` and `report.html` under `--out` and nothing else.
- Exit codes (IF-4): 0 scan completed and threshold not reached; 1 threshold
  reached; 2 usage or engine error. Malformed saved records are findings, never
  crashes.

## Follow-up scope

After a change, audit only the affected run, phase and evidence:

```bash
python run_audit.py --project-root <checkout> --run-id <run> --phase build \
  --artifact evidence/changed-test.log --out <report-dir> --fail-on high
```

Repeat `--run-id`, `--phase` or `--artifact` as needed. Artifact selection requires
one phase; phase selection requires a run. A missing selection is a finding,
not a clean empty audit. Scoped runs omit global harness observations unless
`--include-harness` is passed. The report records its scope; other artifacts
are not hashed or represented as freshly audited. Omit selectors for an initial
full audit or an explicitly requested full audit. Cycle-history sidecars are
not counted as additional gate verdicts.

## What it reports

- Every run with its revision count, terminal state, and event history.
- Every gate verdict with its boundary, gate, verdict, mechanical pass, and
  whether it was produced against the shipped gate spec.
- Evidence drift: any `artifact_hashes` entry whose file is missing or whose
  content hash differs from the manifest (the line-ending-agnostic digest the
  gates use).
- Harness hook observation counters and trajectory volume.

## Report surface

The HTML report is one self-contained document: no external scripts, styles,
fonts, or images; every value escaped; light and dark themes following system
preference with a manual toggle; breakpoints at 960px and 640px.

## Tests

```
python -m unittest discover -s tools/run-audit/tests -p "test_*.py"
```
