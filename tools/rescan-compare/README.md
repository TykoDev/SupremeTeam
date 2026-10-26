# rescan-compare

Compare two re-scan reports and decide whether a later scan matches a release.

Post-release verification (Test-Guide section 12) needs to answer one
question: did the deployed copy change under us?  Run the deployed copy
again, produce a scan report, and compare it with the release-time
report.  Equal run sets and finding sets mean the verification plan's
follow-up is satisfied.

## Usage

```bash
python rescan_compare.py before.json after.json [--out report.json] [--version]
```

- `before.json` - the release-time scan report.
- `after.json` - the later re-scan report.
- `--out` - write the machine-readable comparison report (JSON).

Exit codes follow the catalog convention:

| Code | Meaning |
| ---- | ------- |
| 0 | the run sets and finding sets are equal |
| 1 | there is a difference (missing/extra runs or findings) |
| 2 | engine error: a report is unreadable or malformed |

## Report shape

```json
{
  "runs": ["run-a", "run-b"],
  "findings": [{"id": "F-1", "severity": "Major"}]
}
```

Finding severity must be one of `Critical`, `Major`, `Minor`, `Info`.
A finding is identified by what it says, `(severity, where, statement)`, when the report carries those fields (run-audit's reports do), and by `(id, severity)` otherwise. run-audit's `F-<n>` ids are positions in a sorted list, so one new finding renumbers every later one: compared by id, a different Major in the same slot would read as unchanged and an inserted finding as many changes. A severity change with the same text is a difference: the same finding at a different grade is not the same finding.

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
