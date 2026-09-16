# Scan Evidence Reference

Read this before recording a scan and again before interpreting any result other
than `pass`. `../SKILL.md` states which key this skill owns and shows the common
invocation; this file is the record shape, the option set, and the branch for
every outcome.

## Contents

1. The typed `scan` record
2. `scan_record.py` options
3. Outcome branches
4. Binding inputs correctly
5. Handing the record to `cso`

## The Typed `scan` Record

`../../../gates.yaml` `evidence_type_rules.scan` defines the shape the gate checks.
The record carries:

| Field | Content |
| --- | --- |
| `artifacts` | Hashed files produced by the run, including the retained raw scanner output |
| `tool` | The scanner name (defaults to the first command token) |
| `command` | The exact command executed, argv-preserved |
| `exit_code` | The scanner's own exit code, unmodified |
| `observed_at` | When the scan ran |
| `inputs` | `[{path, sha256}]` bound to the inspected manifests and lockfiles |
| `result.status` | One of `pass`, `fail`, `error`, `not-run`, `unavailable` |

Only `pass` satisfies the gate. `unavailable` and `error` are data gaps, never a
clean scan, and `fail` means the scanner ran correctly and reported findings.
The record is written by the script, never by hand: a hand-written record cannot
carry a truthful `exit_code` or a digest of output it did not observe.

The one sanctioned fallback for the key is
`no dependency or source scan surface - scanner not engaged`. At manifest schema
2 a bare fallback string is rejected, so waiving the key takes an applicability
record `{applicable: false, reason, scope, decided_by}`.

## `scan_record.py` Options

```bash
python skills/scripts/scan_record.py \
  --project-root . \
  --out <phase>/evidence/vulnerability-scan.json \
  --input requirements.txt \
  --input requirements.lock \
  --version-command "pip-audit --version" \
  --fail-exit-codes 1 \
  --limitation "transitive dev dependencies not resolved in this environment" \
  --timeout 300 \
  -- pip-audit -r requirements.txt --strict
```

| Option | Purpose |
| --- | --- |
| `--out` | Path of the JSON record; the raw scanner output is retained beside it |
| `--input` | Repeatable; binds an inspected manifest or lockfile by sha256 |
| `--tool` | Tool name override; defaults to the first token of the command |
| `--version-command` | Command that prints the scanner version, recorded on the result |
| `--fail-exit-codes` | Comma-separated exit codes that mean findings were reported rather than a broken run (default `1`) |
| `--limitation` | Repeatable; records a known coverage gap on the record itself |
| `--timeout` | Bounds the scanner run |
| `--no-run` | Records the request as `not-run` without executing the scanner |
| `--project-root` | Root the inputs and output resolve against |

The scanner command follows `--`. The wrapper exits 0 whenever the record was
written and 2 on wrapper error, so the wrapper's own exit code says whether
evidence exists — `result.status` says what the evidence shows. Reading the
wrapper's exit code as the scan verdict inverts the contract.

## Outcome Branches

| `result.status` | What happened | What to do |
| --- | --- | --- |
| `pass` | Scanner exited 0 | Report the scan as clean for the bound inputs and the declared limitations, and name both |
| `fail` | Scanner exited on a declared `--fail-exit-codes` value | Triage the reported findings; the record stands as evidence the scan ran |
| `error` | Scanner exited on an undeclared code, or crashed | Do not promote it to `fail` or `pass`. Add a `--limitation` naming the unclassified code, re-run with the code declared only when it genuinely means "findings reported", and report any printed findings as unconfirmed |
| `unavailable` | The scanner could not be found or run in this environment | Record it as a data gap, name the missing coverage, and either request the sanctioned applicability record or escalate |
| `not-run` | `--no-run` recorded the request honestly | Same as `unavailable`: a gap, with the reason on the record |

A timeout is an `error`, not a `pass` with fewer findings. State the timeout as a
limitation so the gap is attributable to the run rather than to the code.

## Binding Inputs Correctly

Bind **every** file the assessment depends on, not just the one passed to the
scanner. A manifest without its lockfile leaves the gate unable to detect that
the reviewed resolution is no longer the installed one.

When the manifest and the lockfile disagree, bind both, assess against the
lockfile because it is what installs, and raise the divergence itself as a
finding. Silently choosing one file produces a record that looks clean and
describes a tree nobody ships.

## Handing the Record to `cso`

`cso` submits the `security-review` boundary; this skill authors one key and
hands it over unchanged. On return, state:

- the record path and its digest;
- `result.status` verbatim, with the scanner's real exit code;
- every `--input` binding, so `cso` can see what the scan actually covered;
- every `--limitation`, because a limitation `cso` never sees becomes a coverage
  claim it did not make.

Before handing over, apply the secrets contract in `../SKILL.md`: the raw
scanner output retained beside the record may echo a credential back from a
manifest or an error message. Report the location, never the value, and flag the
retained file as secret-bearing rather than shipping it as routine evidence.
