# Guard — Deterministic Enforcement Reference

How the advisory guard is backed by a deterministic host-compatible hook: the
`guard-state.json` schema, activation steps, the `allow_dangerous` override
protocol, and the fail-open semantics. Read this when activating hook-level
enforcement or diagnosing why a guarded write was or was not blocked.

## Action Realization layer

The guard is the advisory expression of the Action Realization layer
(`../../harness-doctrine.md` §1). When the host supports compatible runtime hooks, the
guarded boundary is also deterministically enforced by
`../../harness/hooks/pre_tool_use.py`, which blocks writes into the guarded paths
before they execute — so the guard is no longer advice the model can ignore. When
the state file is absent the hook is inert and the guard remains advisory only.
See `../../harness/hooks/README.md`.

## guard-state.json

To activate enforcement, record the boundary in `.harness-state/guard-state.json`
(under `SUPREMETEAM_PROJECT_DIR`, a host workspace variable, the current working directory, or the OS temp fallback):

```json
{
  "frozen_globs":  ["src/payments/**"],
  "blocked_globs": ["**/secrets/**"],
  "allow_dangerous": false
}
```

- `frozen_globs` — paths the freeze layer locks against writes.
- `blocked_globs` — paths the guard forbids outright.
- `allow_dangerous` — when `true`, lifts the built-in destructive-command block.

## allow_dangerous override protocol

Setting `allow_dangerous: true` requires explicit owner confirmation before the
guard-state file is written. Obtain the owner's named approval, record the scope
and the reason the dangerous operation requires it, and treat the override as
temporary: revert `allow_dangerous` to `false` as soon as the dangerous operation
completes. It must never be the default value and must never be enabled silently.

## Fail-open semantics (advisory-grade, not a hard control)

Per harness-doctrine §3 the hook *fails open*: any internal error — a malformed
`guard-state.json`, an unreadable path, or a host that does not run the hook at
all — exits silently and lets the action proceed. A guard fault therefore means a
write into `blocked_globs` is *allowed*, not denied. Treat the boundary as a
discipline aid that catches honest mistakes — do not rely on it to stop a
determined or adversarial actor, and never use `blocked_globs` as the sole
protection for secrets or production paths. For real isolation, use OS/filesystem
permissions or a sandbox in addition to the guard.
