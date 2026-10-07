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
| `artifacts` | Hashed files produced by the run, including the retained raw scanner output, named relative to the directory of the manifest that will embed the record (`evidence/<stem>.stdout.txt` and `.stderr.txt` for a record under a run phase), so each name is a key of `artifact_hashes` and the record is embedded unchanged |
| `tool` | The scanner name (defaults to the first command token) |
| `command` | The scanner command as `shlex.join(argv)`, so an argument containing a space stays one argument when it is split back (POSIX quoting on every platform) |
| `argv` | The exact argument list the scanner was started with, unquoted |
| `version_command` | The `--version-command` argument list in the same quoting, or null; `tool_version` holds the first line it printed |
| `exit_code` | The scanner's own exit code, unmodified |
| `observed_at` | When the scan ran |
| `inputs` | `[{path, sha256}]` bound to the inspected manifests and lockfiles |
| `result.status` | One of `pass`, `fail`, `error`, `not-run`, `unavailable` |

Only `pass` satisfies the gate. `unavailable` and `error` are data gaps, never a
clean scan, and `fail` means the scanner ran correctly and reported findings.
The record is written by the script, never by hand: a hand-written record cannot
carry a truthful `exit_code` or a digest of output it did not observe. The gate
cannot tell the two apart, though: it checks the record's shape, its digests, and
that a `pass` does not sit beside a non-zero `exit_code`, and it never compares the
raw output with the record. It does read a `.txt` artifact for blocked phrases, as it
reads any text artifact, so a scanner that prints `TODO` or `100% complete` fails the
check mechanically. That the record is the script's own is a property of how it was made,
not of anything `check.py` verifies.

The one sanctioned fallback for the key is
`no dependency or source scan surface - scanner not engaged`. At manifest schema
2 a bare fallback string is rejected, so waiving the key takes an applicability
record `{applicable: false, reason, scope, decided_by}` whose `reason` is that
exact string; a record with any other reason fails as
`applicability reason not sanctioned`.

## `scan_record.py` Options

```bash
# Resolve the destination first; --out is never composed by hand.
python skills/scripts/output_paths.py --run-id <run-id> --phase security --kind evidence --name vulnerability-scan.json
# -> skillset-saves/runs/<run-id>/security/evidence/vulnerability-scan.json

python skills/scripts/scan_record.py --project-root . --out skillset-saves/runs/<run-id>/security/evidence/vulnerability-scan.json --input requirements.txt --input requirements.lock --version-command "pip-audit --version" --fail-exit-codes 1 --limitation "transitive dev dependencies not resolved in this environment" --timeout 300 -- pip-audit -r requirements.txt --strict
```

| Option | Purpose |
| --- | --- |
| `--out` | Path of the JSON record; the raw scanner output is retained beside it as `<stem>.stdout.txt` / `<stem>.stderr.txt`. Resolved against the process working directory, **not** `--project-root` — a bare relative value writes the one artifact this lens owns outside the run it belongs to (`../SKILL.md` Gate Evidence). |
| `--input` | Repeatable; binds an inspected manifest or lockfile by sha256 |
| `--tool` | Tool name override; defaults to the first token of the command |
| `--version-command` | Command that prints the scanner version, recorded on the result. Split with POSIX shell quoting rules and run as an argument list, never through a shell, so shell operators in the text are ordinary arguments and quoting is how an argument keeps a space. A backslash is an escape, so write a Windows path with `/` or doubled backslashes. An unparseable value is a wrapper error; a command that cannot start leaves `tool_version` null and is named in the record's `limitations` |
| `--fail-exit-codes` | Comma-separated integer exit codes that mean findings were reported rather than a broken run (default `1`). A non-integer is a wrapper error (exit 2) |
| `--fail-on-output` | Repeatable regular expression. An exit-0 run whose stdout or stderr matches it is recorded `fail`, with a limitation naming the pattern, for scanners that print findings and exit 0 |
| `--manifest-root` | Directory of the manifest that will embed the record; artifact names are written relative to it. The default is the run phase directory when `--out` sits inside `skillset-saves/runs/<run>/<phase>/`, else the record's own directory. A root that does not contain the record is a wrapper error |
| `--limitation` | Repeatable; records a known coverage gap on the record itself |
| `--timeout` | Bounds the scanner run |
| `--no-run` | Records the request as `not-run` without executing the scanner |
| `--project-root` | Root that `--input` paths resolve against (and that each must stay inside), and the working directory the scanner subprocess runs in. It does **not** govern `--out`: `scan_record.py` resolves the record destination against the *process* working directory, so a relative `--out` lands beside wherever you invoked the wrapper, not under this root. Pass `--out` the path `output_paths.py` resolved. |

The scanner command follows `--`. The wrapper exits 0 whenever the record was
written and 2 on wrapper error, so the wrapper's own exit code says whether
evidence exists — `result.status` says what the evidence shows. Reading the
wrapper's exit code as the scan verdict inverts the contract.

## Outcome Branches

| `result.status` | What happened | What to do |
| --- | --- | --- |
| `pass` | Scanner exited 0 and no `--fail-on-output` pattern matched | Report that the scanner exited 0 for the bound inputs and the declared limitations, and name both. Exit 0 is not proof of no findings: a scanner that prints findings and exits 0 (semgrep without `--error`, trivy without `--exit-code 1`) needs its own exit-code flag or a `--fail-on-output` pattern, and the scan is not reported as clean until one is in force |
| `fail` | Scanner exited on a declared `--fail-exit-codes` value, or exited 0 with output matching `--fail-on-output` | Triage the reported findings; the record stands as evidence the scan ran |
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
