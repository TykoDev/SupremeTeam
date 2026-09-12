# Taste stub contract

## Ownership

Taste is the pipeline owner, sole semantic owner, canonical record writer, handoff
writer, and `taste-review` submitter. Delegated analysts may report candidates,
conflicts, and accessibility concerns but cannot approve meaning or write state.

## Persistence

All canonical mutation goes through `taste_prefs.py` with atomic replacement.
Malformed current records fail closed. Project values override global values only
by stable ID; source records remain independently revisioned.

## Confirmation

Inferred and scope-widening changes require confirmation. Promotion to global,
global reset, bulk import, and bulk revocation always require fresh explicit
confirmation and can never arise from casual product feedback.

## Consumer handoff

The handoff includes source revisions, effective preferences, precedence,
provenance, accessibility constraints, conflict decisions, target consumers, and
unresolved questions. Consumers treat it as read-only and route requested
semantic changes back to Taste.

## Gate

Taste submits the package to `taste-review`. Approval attests that scope, diff,
effective profile, policy checks, required confirmation, and consumer handoff are
complete; it does not authorize a later destructive operation.
