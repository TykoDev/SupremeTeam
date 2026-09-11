---
name: taste
description: Manage explicit, reviewable project and global working preferences without silently learning from behavior.
version: 1.0.0
---

# Taste

Taste owns the preference pipeline and durable profile. It previews every
mutation, requires confirmation for destructive, cross-scope, import, migration,
and lifecycle operations, and stores immutable before/after evidence for an
active run under `skillset-saves/runs/<run>/preferences/`.

The canonical project record is `skillset-saves/preferences/taste.json`; the
canonical user record is `~/.supremeteam/preferences/taste.json`. The provisional
legacy format is accepted only when its first line is exactly
`# Supreme Team Taste Preferences (legacy v1)` and every remaining nonblank line
has the form `- safe-key: value`. Arbitrary Markdown is never a preference.

Use `python skills/taste/taste_prefs.py` for all durable writes. Explicit user
instructions outrank project preferences, which outrank inherited global
preferences. Equal-precedence disagreement remains unresolved for confirmation.
