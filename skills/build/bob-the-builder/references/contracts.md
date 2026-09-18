# Contract Reference

The full normative text of every contract `SKILL.md` lists under Required
Contracts. `SKILL.md` carries the operative rule so it binds at load time; this
file carries the reasoning, the refusal cases, and the escalation path each rule
depends on. Read it before the first edit of a pass that touches paths,
credentials, migrations, or non-first-party surfaces.

## Contents

1. Write boundary
2. Secrets handling
3. Migration execution boundary
4. Atomic commit per fix
5. Vendoring detection
6. Shared severity
7. Save-protocol adherence

## Write Boundary

Enumerate the approved change list before the first edit and treat it as the
complete set of writable destinations. Resolve every write path against the
repository root and confirm the resolved path still sits inside the working tree
— the same containment rule `build/gatekeeper-build` already enforces in code,
where `../../gatekeeper-build/scripts/check.py` `_validate_package_dir` resolves the
path and refuses anything outside the tree.

Refuse each of these outright, before the write rather than after:

| Destination | Why it is refused |
| --- | --- |
| An absolute path (`/etc/...`, `C:\...`) | It resolves against the host, not the assignment; no build scope reaches outside the checkout. |
| A UNC path (`\\server\share\...`) | It writes to another machine, which no build delegation can authorize. |
| A symlinked destination whose target leaves the tree | The path looks contained and the write is not; containment is checked after resolution for exactly this case. |
| Any `../` segment that escapes the repository root | Same class as the absolute path, arrived at by arithmetic. |
| A file inside the tree that the change list does not name | Contained but unapproved. The gate reads a diff, not an intent. |

When the implementation genuinely needs a surface outside the declared list,
stop and escalate the amendment to `build/build-management` instead of widening
the change set silently, because by the time the gate reads the diff an
unannounced write is indistinguishable from scope drift. The escalation names
the path, the reason it is needed, and whether the surface is first-party.

Generated roots are the one asymmetry worth stating explicitly. Product source
belongs to the application's own layout; everything this pass generates for the
run — logs, evidence, reports — belongs under the phase directory the handoff
assigns, resolved through `skills/scripts/output_paths.py`
(`../../../save-ownership.yaml`, `generated_roots_rule`). Composing either path by
hand is how a build artifact ends up outside every policy that governs it.

## Secrets Handling

Credential-shaped surfaces — `.env` files and their samples, settings modules,
deployment manifests, CI configuration — are edited by key name only. Add,
rename, or document the key and leave the value to the environment; no real
secret, token, API key, or connection string is committed into first-party
source, and none is echoed into the change list, the diff summary, or the
returned package.

A live credential already present in a touched file is reported as a Critical
finding by location and type with the value withheld, and routed to
`build/security-builder` for rotation rather than carried forward quietly. The
change set is not clean until rotation is confirmed. Removing the line without
rotating is worse than leaving it: it hides the exposure from the next reader
while the credential stays valid in history and in whatever already read it.

## Migration Execution Boundary

**This section is the canonical statement of the migration rule.** `../SKILL.md`
Failure Modes and `workflow.md` both point here rather than restating it; when
any of the three appear to differ, this text governs.

A change set containing a migration is proven by executing it, and proving the
rollback path means executing the down-migration too. Run both directions only
against a disposable local schema that can be dropped and rebuilt from scratch.

A migration is never run, in either direction, against a shared, staging, or
production target without explicit owner approval recorded in the handoff,
because a down-migration destroys data and a shared schema has no owner-visible
undo. Absent that approval, verify locally, state in the returned package that
the non-local run was not performed, and hand that run to the owner who controls
the target.

## Atomic Commit Per Fix

Keep each fix isolated, explain what changed, and preserve easy rollback
boundaries even when several issues are found. One commit that carries three
unrelated repairs cannot be reverted for the one that turned out wrong, and a
reviewer reading it has to separate the three by hand before judging any of
them.

## Vendoring Detection

Detect generated, vendored, or third-party imported content and treat it with
tighter review rules than first-party changes. Generated output is regenerated,
not hand-edited; a hand-edit to it is lost at the next generation and reads as a
first-party change until then. Vendored and third-party files are isolated in
the change list and named as non-first-party in the returned package, so the
gate and `build/security-builder` can apply the scrutiny that surface actually
needs.

## Shared Severity

Grade every finding Critical | Major | Minor | Info — the four-tier model
clause 3 of `../../../execution-contract.md` defines, and the same vocabulary
`../../../gates.yaml` `finding_policy` enforces mechanically at the boundary.
Critical blocks every gate until a verified fix or an explicit not-applicable
reason. Major blocks unless verified, not-applicable with a reason, or
explicitly deferred with a named owner and a reopen trigger. Minor is recorded
and Info is preserved as context. Using a local severity scale here means the
downstream package reads this pass's risk differently from every sibling's.

## Save-Protocol Adherence

When a Save Context block arrives with `Persistence active: yes`, deliverables
are written to the provided save path; saving is mandatory, not optional.
Resolve each destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind <evidence|reports> --name <file>`
rather than composing it, and never create nested per-specialist directories or
phase-state files — no declared path class covers them
(`../../../save-ownership.yaml`). When Save Context is absent or persistence is
inactive, the same deliverables are returned inline.
