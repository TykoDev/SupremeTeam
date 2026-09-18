# Taste Doctrine

Canonical semantic contract for recording, resolving, and applying Taste in
Supreme Team. Taste is the user's authored or explicitly confirmed preferences
for presentation and interaction. It informs choices where more than one valid
implementation remains; it is not authority to weaken a requirement.

This file is canonical for the meaning of Taste: its boundary, its scopes, its
category registry, the fields an entry carries, the lifecycle an entry moves
through, the operation set, and the resolution order. It is not canonical for
the storage format, the command surface, or the on-disk record shape — those
belong to `skills/taste/taste_prefs.py`, the single writer of durable Taste
state. Where this file and that writer describe the same thing in different
words, §6 maps one onto the other and the writer's names win.

## Contents

- [Enforcement status](#enforcement-status)
- [1. Boundary of Taste](#1-boundary-of-taste)
- [2. Scopes](#2-scopes)
- [3. Stable categories](#3-stable-categories)
- [4. Entry record and provenance](#4-entry-record-and-provenance)
- [5. Lifecycle](#5-lifecycle)
- [6. Operations](#6-operations)
- [7. Effective-preference resolution](#7-effective-preference-resolution)
- [8. Use in the lifecycle](#8-use-in-the-lifecycle)
- [Failure paths](#failure-paths)

## Enforcement status

Most of this doctrine is semantic and is applied by judgement. A narrow band is
mechanically checked, and it is checked at two different places: the writer
(`skills/taste/taste_prefs.py`) validates what is stored, and the gate
(`skills/harness/gatekeeper/check.py`, against [gates.yaml](gates.yaml))
validates the typed records a taste run submits at `taste-review`. Neither
validates the category registry in §3, the field list in §4, or the six
lifecycle states in §5.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| The stored record's schema, version, scope kind, required top-level keys, and self-consistent sha256 digest | machine-checked | `taste_prefs.py`, `validate()` |
| A corrupt or unreadable store is refused rather than repaired or silently replaced | machine-checked | `taste_prefs.py`, `load()` raising `corrupt_record` (§4) |
| A write to an existing store carries `--expect-revision`, and a stale revision is refused | machine-checked | `taste_prefs.py`, `expected_revisions()` and the `stale_revision` error |
| Only one writer mutates a store at a time | machine-checked | `taste_prefs.py`, `lock()` raising `locked` |
| A preference id is a stable lowercase identifier | machine-checked | `taste_prefs.py`, the `[a-z0-9][a-z0-9._-]{0,127}` pattern in `mutate()` |
| Secrets, credentials, and personal identifiers are refused or redacted; text and list sizes are bounded | machine-checked | `taste_prefs.py`, `validate_safe()` |
| `confirm` applies only to a `proposed` entry (§5) | machine-checked | `taste_prefs.py`, the `invalid_state` error in `mutate()` |
| `promote` writes global scope and `specialize` writes project scope (§6) | machine-checked | `taste_prefs.py`, the `invalid_scope` errors in `main()` |
| Writes to the durable Taste path go through the sanctioned writer only | machine-checked where hooks are registered | `skills/harness/hooks/pre_tool_use.py`, with [save-ownership.yaml](save-ownership.yaml) |
| At `taste-review`, the typed `preference_diff`, `confirmation`, `conflict_analysis`, `persistence_result`, `effective_profile`, and `consumer_handoff` records carry their required fields and sha256 digests | machine-checked | `skills/harness/gatekeeper/check.py`, driven by `evidence_type_rules` in [gates.yaml](gates.yaml) |
| The eleven category identifiers in §3 | **judgement** | nothing — the writer stores an opaque `value` and never inspects a category |
| The entry fields in §4 | **judgement** | nothing — see §4 |
| The six lifecycle states in §5 | **judgement** | nothing — the store persists three states plus tombstones; see §5 |
| The merge procedure in §7 | **judgement, partially implemented** | `taste_prefs.py` `effective` implements part of it; see §7 |
| The boundary in §1, including that Taste never outranks a mandatory requirement | judgement | nothing; `conflict_analysis` records the collision but does not adjudicate it |
| That an inference was genuinely confirmed by the user | judgement at the store; machine-checked at the gate | the `confirmation` typed record is required at `taste-review`, but the writer cannot tell an explicit `set` from a confirmed inference |
| This document itself | **judgement** | nothing — no comparator opens this file. `taste_prefs.py` validates the stored record and `check.py` validates the submitted typed records; neither resolves a rule to this text. Every mechanical row above holds because of the writer and [gates.yaml](gates.yaml), so a clause deleted here fails no suite. |

The practical consequence: a store that passes `taste_prefs.py` is well-formed,
not doctrinally correct. Category, provenance, and lifecycle correctness rest on
the skill that writes the entry and the reviewer at `taste-review`.

## 1. Boundary of Taste

Taste includes user-authored preferences and inferred candidates that the user
has explicitly confirmed. It is distinct from, and must not be used to encode:

- correctness or security requirements;
- accessibility requirements;
- project architecture constraints;
- technology selection or the project `stack_lock`;
- inferred behavioral telemetry; or
- general learnings retained by `session-memory`.

Technology ergonomics may express how the user prefers to work within an
already permitted and locked stack. It does not select, replace, or unlock the
stack. Mandatory accessibility, safety, security, legal, and gate requirements
always outrank Taste and cannot be overridden by it. Surface a conflict with any
such requirement to the user; never silently normalize, weaken, or reinterpret
the requirement or the conflicting preference.

Never derive sensitive traits or preferences from protected or personal
characteristics. Behavioral observation may produce a clearly labelled
inference candidate, but telemetry is not itself Taste, and no inference may
become `active` without explicit user confirmation.

This boundary is judgement. The one mechanical support is negative: the writer's
`validate_safe()` refuses fields and values that look like secrets, credentials,
or personal identifiers, so a store cannot quietly accumulate them. It cannot
tell an accessibility requirement from a preference.

## 2. Scopes

Every entry has exactly one persisted scope:

1. `global`: intended to apply across projects for the current user.
2. `project`: specific to the current project.
3. `both`: an operation target that writes two distinct entries, one `global`
   and one `project`. `both` is never stored as a scope and never creates a
   third inheritance tier.

The two records produced by `both` have distinct stable preference ids and
provenance. Their linkage may be recorded, but each remains independently
editable, supersedable, deprecatable, and revocable.

The writer enforces the scope vocabulary: every command takes
`--scope global|project|both`, mutations require it explicitly, and `both`
resolves to the two stores and commits them as a pair, rolling back both if
either write fails. What it does not enforce is that the two records carry
distinct ids: a `--scope both` mutation applies the same `--id` to both stores.
Giving the two records distinct ids is the caller's responsibility, and it is
judgement.

## 3. Stable categories

Every entry uses a stable, machine-readable category identifier from the
following registry rather than an arbitrary display heading:

| Identifier | Meaning |
| --- | --- |
| `visual-style` | Surface treatment, imagery, ornament, shape, and aesthetic direction |
| `typography` | Type families, scale, weight, measure, and typographic treatment |
| `color-behavior` | Palette tendencies, theme behavior, contrast beyond mandatory floors, and semantic color use |
| `density` | Spacing, information density, and control compactness |
| `motion` | Animation character, duration, frequency, and optional transitions |
| `layout` | Composition, hierarchy, alignment, content width, and responsive arrangement |
| `component-behavior` | Component variants, states, disclosure, and feedback behavior |
| `content-tone` | Voice, terminology, directness, and content presentation |
| `interaction-patterns` | Navigation, input, shortcuts, confirmation, undo, and task flow preferences |
| `technology-ergonomics` | User-facing workflow ergonomics within architecture and stack constraints |
| `anti-preference` | An explicit denial or presentation/interaction pattern to avoid |

Extensions require a documented, stable identifier with defined semantics and
must not duplicate an existing category. Display labels may vary, but stored
identifiers do not.

**No comparator checks this registry.** `taste_prefs.py` stores each entry's
content as an opaque `value` and never reads a `category` out of it, so an entry
carrying an invented or misspelled category is written without complaint. Two
other documents restate this list and must stay tied to it: the redesign
variant rule in [design-doctrine.md](design-doctrine.md) §9, which requires four
directions differing in at least three of these categories, and the taste
grilling in [grill-me-doctrine.md](grill-me-doctrine.md), whose prompt order is
a permutation of these eleven identifiers. Changing an identifier here means
changing both, and nothing will fail if that is forgotten.

## 4. Entry record and provenance

Every Taste entry records:

- `preference_id`: a stable, unique identifier;
- `scope`: persisted as `global` or `project`;
- `category`: a stable category identifier from §3;
- `normalized_rule`: an unambiguous, implementation-neutral statement;
- `strength`: `hard`, `strong`, or `soft`;
- `source`: `explicit`, `imported`, or `confirmed-inference`;
- `source_run` and source timestamp when available;
- `rationale`;
- `confidence` only for an inference candidate, and absent after the entry is
  confirmed as Taste;
- `applicability_selectors`: the projects, surfaces, contexts, modes, or other
  declared conditions to which the rule applies;
- `conflicts`: known conflicting entry ids or mandatory constraints;
- `supersedes` and `superseded_by` links;
- `state`: one lifecycle state from §5; and
- `created_at` and `updated_at` timestamps.

An entry that is time-bounded also records its expiry. Imports preserve their
original provenance when known and add import provenance; they do not masquerade
as explicit instructions from the current run.

For deterministic matching, normalize each entry to a category/selector key
composed from its category and canonicalized applicability selectors. Preserve
the original user wording separately when a storage implementation supports it;
the normalized rule remains the resolution input.

**What the writer actually persists.** `taste_prefs.py` stores each entry as
three keys — `state`, `value`, and `updated_at` — where `value` is the caller's
JSON blob. The fields above live inside `value` and are validated only for
safety and size, never for presence, type, or vocabulary. Two consequences
follow, and both are load-bearing:

- The field list above is a judgement contract on the skill that writes the
  entry. An entry missing `category`, `normalized_rule`, or `source` is stored
  successfully and is a doctrine violation the store cannot detect.
- `preference_id` and `scope` are the exceptions. The id is the entry's key and
  is pattern-checked; the scope is the store the entry lives in. Those two are
  mechanically real.

**Corrupt-record refusal.** When a canonical record exists but cannot be read or
fails validation, the writer refuses the whole operation with `corrupt_record`,
preserves the original bytes untouched, and reports that the file must be
repaired or moved explicitly before a retry. This is normative, not incidental:
a Taste store is never silently reinitialized, never partially repaired, and
never replaced by a blank record on a read failure. A missing store is a
different case and is treated as an empty store at revision 0; only an
unreadable or invalid one refuses. Callers surface the refusal rather than
retrying around it.

## 5. Lifecycle

The allowed states are:

- `proposed`: a candidate awaiting a user decision;
- `confirmed`: explicitly accepted by the user but not yet enabled;
- `active`: eligible for effective-Taste resolution;
- `superseded`: replaced by a linked newer entry;
- `deprecated`: retained for history but discouraged and excluded from
  resolution;
- `revoked`: explicitly withdrawn and excluded from resolution.

Only an explicit user action can confirm an inferred candidate. A
`confirmed-inference` records that confirmation; no automated process may move
an inference directly from `proposed` to `active`. Activation after confirmation
may occur in the same user-approved operation when that intent is clear.

**How the store represents these six.** The writer persists three `state`
values and one tombstone record, so four of the six states above are semantic
rather than stored. The correspondence is exact and worth stating, because a
reader inspecting a store will not find the vocabulary this section defines:

| §5 state | Stored as | Produced by |
| --- | --- | --- |
| `proposed` | `state: "proposed"` | `propose` |
| `confirmed` | not stored — `confirm` moves a `proposed` entry straight to `active`, which is the sanctioned "activation in the same user-approved operation" | `confirm` |
| `active` | `state: "active"` | `set`, `confirm`, `import`, `promote`, `specialize` |
| `superseded` | not stored — `set` on an existing id replaces it in place; the prior revision survives in the store's `_history/` snapshots and journal | `set` |
| `deprecated` | `state: "deprecated"` | `deprecate` |
| `revoked` | not a state — the entry is removed from `entries` and a `tombstones` record is written with `revoked_at` and `prior_entry_digest` | `revoke`, `reset` |

`confirmed` as a distinct resting state, and `supersedes`/`superseded_by` links
between entries, therefore have no representation in the current store. A skill
that needs either must carry it inside the entry's `value` and treat it as
judgement. The one lifecycle rule the writer does enforce is that `confirm`
rejects any entry not currently `proposed`.

## 6. Operations

The command surface is canonical, and it is the subcommand set
`skills/taste/taste_prefs.py` exposes. This doctrine's semantic names are the
meanings; the CLI names are what a run actually invokes. Earlier revisions of
this file named operations (`inspect`, `resolve`) that the writer does not
expose; the table below is the single authority on the correspondence, and where
the two differ the CLI name is the one to use.

| Semantic operation | CLI subcommand | Mutating | Notes |
| --- | --- | --- | --- |
| inspect stored entries and provenance | `list` | no | Returns every entry per selected scope, unchanged |
| inspect store identity and revision | `status` | no | Path, existence, revision, and canonical digest per scope |
| propose a candidate, with confidence when inferred | `propose` | yes | Writes `state: "proposed"` |
| confirm explicit user acceptance | `confirm` | yes | Refuses any entry that is not `proposed`; lands it `active` |
| create or supersede user-authored Taste and make it active | `set` | yes | Replaces an existing id in place (§5) |
| import external entries, retaining provenance | `import` | yes | Reads a JSON file, caps at 1000 entries, validates every id |
| export selected records with lifecycle and provenance intact | `export` | no | Writes a redacted JSON export carrying each store's digest as provenance |
| diff stored Taste across scopes | `diff` | no | Per-id differences between the project and global stores |
| promote project-to-global | `promote` | yes | Refuses unless the scope is `global` or `both` |
| specialize global-to-project | `specialize` | yes | Refuses unless the scope is `project` or `both` |
| deprecate | `deprecate` | yes | Writes `state: "deprecated"` |
| revoke | `revoke` | yes | Removes the entry and writes a tombstone |
| reset scope | `reset` | yes | Tombstones every entry in the named scope; `--scope both` resets both |
| explain effective Taste | `effective` | no | Returns active entries with `source_scope`; see §7 for what it does **not** do |

There is no `inspect` subcommand and no `resolve` subcommand. `list` plus
`status` is the inspection surface; `effective` is the resolution surface.

Operations are auditable and update timestamps and lifecycle links atomically.
The writer backs that up for the parts it owns: every mutation increments the
store revision, chains `previous_revision_digest`, snapshots the prior revision
under `_history/`, appends to the store journal, and commits the JSON and
rendered Markdown pair together, rolling both back on failure. Lifecycle *links*
between entries are content inside `value` and are not maintained by the writer.

Promotion, specialization, and `both` always create distinct records rather than
changing inheritance semantics. `promote` and `specialize` copy the source
entry into the target scope under the same id; giving the copy its own stable id
where §2 requires distinct ids is the caller's responsibility.

## 7. Effective-preference resolution

Resolve applicable presentation and interaction decisions in this order:

1. Current explicit user instruction.
2. Project-level deny, override, or preference.
3. Global deny, override, or preference.
4. Existing project design system and established conventions.
5. Tool defaults.

A current explicit instruction governs the current decision and should be
persisted only when the user asks to set it as Taste or explicitly confirms that
intent. Higher-ranked Taste may choose among valid design options, but the
non-overridable requirements in §1 remain outside and above this ordering.

Apply this deterministic merge procedure:

1. Exclude expired, `revoked`, `deprecated`, `superseded`, non-`active`, or
   selector-inapplicable entries.
2. Match entries first by stable `preference_id`; otherwise match by normalized
   category/selector key.
3. Within a persisted scope, a denial takes precedence over a matching positive
   preference. Strength describes intended adherence but does not reverse scope
   or denial precedence.
4. A matching project entry shadows the global entry, including when the
   project rule is a denial or a specialization.
5. Equal-precedence contradictions remain unresolved. Record the conflict,
   surface it, and obtain user confirmation; do not pick by timestamp, input
   order, strength, or arbitrary tie-breaking.
6. Fall through to the established project design system and conventions, then
   tool defaults, only where no higher-precedence resolved rule applies.

Every resolved preference records the exact source entry that produced it. An
effective-Taste explanation also identifies shadowed, excluded, and unresolved
entries, so resolution is reproducible rather than inferred from the output.

**How much of this the CLI implements.** `taste_prefs.py effective` performs
steps 1 and 4 in their narrow form and nothing else: it keeps entries whose
`state` is `active`, iterates global then project so a project entry with the
same id overwrites the global one, and tags each result with its `source_scope`.
It does not evaluate expiry, does not match by normalized category/selector key,
does not apply denial precedence, does not detect equal-precedence
contradictions, and does not report shadowed, excluded, or unresolved entries.

Steps 2, 3, 5, and 6, and the explanation requirement in the paragraph above,
are therefore performed by the `taste` skill, not by the store. The gate is
where they become checkable: at `taste-review`, `conflict_analysis` must carry
`conflicting_ids`, `precedence_decision`, `unresolved_conflicts`, and
`accessibility_policy_collisions`, and `effective_profile` must carry a sha256
digest and, for every entry, its `id`, `source_scope`, and `source_id`.
`skills/harness/gatekeeper/check.py` verifies those record shapes. It verifies
that the merge was *reported*, not that it was performed correctly.

## 8. Use in the lifecycle

Admiral may inspect applicable Taste during intake and must preserve current
explicit instructions as highest-precedence inputs. Design applies effective
Taste only after filtering it through project conventions and mandatory
requirements. Review verifies both the chosen preferences and the constraints
that outrank them. Consuming Taste in those phases opens no pipeline and no gate.
It is a semantic input those phases read inside the pipeline they are already
running. Mutating Taste is the separate case: an explicit preference lifecycle
request runs the `taste` pipeline under the operations of §5 and §6 and closes at
the `taste-review` boundary. Neither path makes Taste a stack lock, a
design-system owner, or a session-memory namespace.

The design phase consumes Taste as an immutable snapshot rather than as a live
store read: [design-doctrine.md](design-doctrine.md) §0 fixes the snapshot's
fields and §8 makes `taste_snapshot` a required, hashed evidence key at
`design-to-build` — required, but **waivable**: [gates.yaml](gates.yaml)
`fallback_values` sanctions the single reason `no saved Taste profile available`,
carried at schema 2 as a typed applicability record, for a project that has no
saved profile to snapshot. A run with no Taste history is not blocked at this
key; a run that *has* a profile and skips the snapshot is. That is the mechanism by which a design is reviewed against
the profile approved with it rather than against a later store revision.

The redesign pipeline's taste grilling ([grill-me-doctrine.md](grill-me-doctrine.md)
§ Taste grilling) is the one place Taste is elicited systematically rather than
captured from a passing request. `taste` runs it, and every confirmed answer
enters the normal lifecycle (§5, §6): nothing a grilling produces becomes
`active` without the confirmation the operations above require.

## Failure paths

- **The store is unreadable or fails validation.** The writer refuses with
  `corrupt_record` and preserves the original bytes (§4). Report the refusal and
  the path; do not reinitialize, do not retry with a blank record, and do not
  work around it by editing the file directly — direct writes to the Taste path
  are denied by `pre_tool_use.py` where hooks are registered, and are an
  ownership violation everywhere else.
- **The store is missing.** That is not corruption. It is an empty store at
  revision 0, and a first mutation creates it.
- **Another writer holds the lock.** The writer refuses with `locked` rather
  than waiting or forcing. Surface it; a second concurrent taste run is a
  routing problem, not a retry problem.
- **The expected revision does not match.** The writer refuses with
  `stale_revision`. Re-read the store with `status`, re-resolve the intended
  change against the current revision, and re-issue. Never drop
  `--expect-revision` to make the refusal go away; for an existing store the
  writer requires it.
- **A `--scope both` write fails on one store.** The pair commits atomically or
  rolls back to the prior bytes of both, reporting `write_failed`. Treat a
  reported rollback as the final state and verify with `status` before retrying.
- **Two entries contradict at equal precedence.** §7 step 5 governs: leave it
  unresolved, record it in `unresolved_conflicts`, surface it, and ask. Choosing
  by recency or strength is a doctrine violation even though nothing prevents
  it.
- **Taste collides with a mandatory accessibility, security, safety, legal, or
  gate requirement.** The requirement wins and the preference is not applied.
  Record the collision in `accessibility_policy_collisions` or the equivalent
  conflict field, surface it to the user, and change neither side silently.
- **An inference has no explicit confirmation.** It stays `proposed`. It is not
  activated, not exported as Taste, and not used in resolution. At
  `taste-review` the `confirmation` record makes this checkable; before the
  gate it is judgement.
- **The host cannot run `taste_prefs.py`** (no Python, no writable store root).
  Taste is unavailable, not empty. Say so, continue on project conventions and
  tool defaults per §7 steps 4 and 5, and carry the sanctioned
  `no saved Taste profile available` applicability record at `design-to-build`
  rather than shipping a snapshot that claims an empty profile was resolved.
