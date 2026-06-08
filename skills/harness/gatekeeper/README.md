# Gatekeeper Deterministic Gate Engine

Shared, stdlib-only Python behind every `gatekeeper-*` skill's `scripts/check.py`.
It turns the *mechanically checkable* parts of a package validation into a
deterministic pass so the gatekeeper skills no longer re-derive them as prose
each run. It is the gate-side companion to `../hooks/` (Action Realization /
Trajectory Regulation), built on the same conventions in `../../harness-doctrine.md`.

| File | Purpose |
| --- | --- |
| `_gatecheck.py` | The engine: frontmatter parsing, package discovery, the six checks, the report model, and CLI rendering. |
| `test_gatecheck.py` | Stdlib `unittest` regression suite for every check. |

Each gatekeeper ships a thin `scripts/check.py` that declares **only** its
boundary's required-artifact manifest and calls `main_with_manifest`. The wrapper
locates this engine by walking up to the repo root (`harness/gatekeeper/_gatecheck.py`),
so the skills package independently of their directory depth.

## What is deterministic vs. what stays the model's job

By design (harness-doctrine §2.4: *residual reasoning is out of scope for the
harness*), the engine reports **facts**, never a verdict:

| Deterministic (engine) | Judgment (gatekeeper skill) |
| --- | --- |
| Required artifacts present for the boundary | Whether a present artifact is *substantively* adequate |
| Single-revision lineage; one submission id | Whether a contradiction across artifacts is real |
| Skip records carry the save-protocol §2 fields | Whether a skip is *justified* for the scope |
| Blocked-phrase / contamination markers absent | Whether prose overclaims completion |
| Idempotency vs. a prior verdict (drift detection) | Whether a scope change warrants ESCALATE |
| harness-doctrine §5 structure (layer + regression note) | Whether the intervention is correctly layered |
| `APPROVED` / `REVISE` / `ESCALATE` ← **never** the script | ✅ the skill decides, citing the report |

Each finding is `PASS` (condition held), `FAIL` (condition violated), or
`UNCHECKED` (could not be decided deterministically — the model must resolve it,
e.g. conditional artifacts, §5 substance). The report's `gate_status` summarizes:
`STRUCTURE_OK`, `NEEDS_JUDGMENT`, or `BLOCKERS_PRESENT`.

## Posture: fail loud, not fail open

`../hooks/` **fail open** — a hook that errors lets the action proceed. A gate is
the opposite: it must **fail loud**. A gate that cannot prove a package is clean
must never silently approve it. So an internal error becomes an `ERROR`
gate-status with exit code `2`, a missing/empty package is a `critical` `FAIL`,
and any blocking failure is a non-zero exit — a caller that only reads the return
code never mistakes a defect for a pass.

Severities use the shared four-tier model: `critical`, `major`, `minor`, `info`.

## Usage

```bash
python <gate>/scripts/check.py <package-dir> [--prior <verdict-file>] [--json] [--blocked-phrases <file>]
```

- `--prior` — a previous `gatekeeper-verdict.md` / handoff file for idempotency
  (drift) comparison. Keep it **outside** the package directory.
- `--json` — emit the structured report instead of markdown (for orchestrators).
- `--blocked-phrases` — extra phrases (one per line; a `re:` prefix marks a regex)
  appended to `DEFAULT_BLOCKED_PHRASES`.

Exit codes: `0` no blocking failure · `1` one or more blocking failures · `2`
the gate could not run (validate by hand).

## Blocked-phrase list

`gatekeeper-admiral` owns the scan; all gates run it. The default list targets
hollow-completion claims and contamination markers (`TODO`/`FIXME`/`XXX`/`HACK`,
`trust me`, `100% complete`, `lorem ipsum`, …). Per the doctrine, any hit is a
blocking package defect. Extend, don't fork, via `--blocked-phrases`.

## Tests

```bash
python -m unittest discover -s SupremeTeam/harness/gatekeeper -p "test_*.py"
```

Run after any change to the engine or a gate manifest. harness-doctrine §3
requires a regression check before a gate behavior change ships.
