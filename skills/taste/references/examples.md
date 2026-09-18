# Taste examples

The command lines below are the exact invocations these scenarios run. An
existing store always needs `--expect-revision`, so the revision shown assumes
the store was at that revision when the write began. Scenarios without a command
block are routing and confirmation decisions, not writer calls, so they have
none.

`test_taste_prefs.py` is the writer's contract suite, not a transcript of this
file: its three tests exercise `set` (project, `both`, and the `--redact` path),
`deprecate`, `revoke`, `reset`, and `effective`, plus the `stale_revision`,
`sensitive_input`, and `corrupt_record` refusals. `status`, `list`, `diff`,
`export`, `confirm`, `import`, `promote`, `propose`, and `specialize` are
documented here and in `workflow.md` but are not covered by that suite — run
`--help` on any of them before composing a call.

## Contents

1. Project preference
2. Global preference
3. Consumption without mutation
4. Promotion and destructive work
5. Accessibility conflict

## Project preference

“Remember that I prefer compact tables in this project” routes through Admiral
to Taste. Taste selects project scope, records compact and spacious examples,
previews the project diff and effective profile, then writes the confirmed
explicit preference:

```bash
python skills/taste/taste_prefs.py status --scope project      # read revision + digest
python skills/taste/taste_prefs.py diff --scope both           # preview across scopes
python skills/taste/taste_prefs.py set --scope project --expect-revision 4 --id tables.density --value '"compact"'
python skills/taste/taste_prefs.py effective --scope both      # confirm the merged result
```

An inferred preference is `propose`d and only `confirm`ed on an explicit user
decision, never written straight to `active` with `set`.

## Global preference

“Save this style globally” is an explicit global target, but Taste still previews
what other projects will inherit. If the style was inferred from casual praise,
Taste asks the user to confirm the normalized rule before persisting it.

## Consumption without mutation

“Design this dashboard” runs the normal design pipeline. The architect consumes
the resolved Taste handoff if present; this does not open Taste or create new
preferences. Likewise, invoking a browser or QA utility does not interpret
feedback as a Taste mutation.

## Promotion and destructive work

“Promote this project preference” produces a global diff and requires explicit
confirmation. Promotion writes global scope (or both) — never `--scope project` —
and copies the confirmed project entry to global while leaving the project record
in place:

```bash
python skills/taste/taste_prefs.py promote --scope both --expect-revision project=6 --expect-revision global=2 --id tables.density
```

“I don't love this screen” is never interpreted as promotion, global reset, bulk
import, or bulk revocation. “Forget preference `density` in this project” may
revoke that one named project entry —
`revoke --scope project --expect-revision N --id density`, which tombstones it —
while ambiguous or batch removal is previewed and confirmed first. A global reset
(`reset --scope global`) always requires a fresh, operation-specific confirmation.

## Accessibility conflict

If “always use pale gray text” conflicts with readable contrast, Taste reports
the accessibility problem and does not normalize it into a binding visual rule.
It asks whether the user instead wants a low-emphasis hierarchy that continues
to meet the project's accessibility requirements.
