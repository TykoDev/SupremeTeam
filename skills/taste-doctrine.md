# Taste Doctrine

Canonical semantic contract for recording, resolving, and applying Taste in
Supreme Team. Taste is the user's authored or explicitly confirmed preferences
for presentation and interaction. It informs choices where more than one valid
implementation remains; it is not authority to weaken a requirement.

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

## 6. Operations

Implementations expose these semantic operations:

- **inspect**: list stored entries and provenance without changing them;
- **propose**: create a `proposed` candidate, including confidence when it came
  from inference;
- **confirm**: record explicit user acceptance and move a proposal to
  `confirmed`, optionally activating it when explicitly requested;
- **set**: create or supersede user-authored Taste and make it `active`;
- **import**: validate external entries, retain provenance, and require explicit
  confirmation for any inferred candidate before activation;
- **export**: serialize selected records with lifecycle and provenance intact;
- **diff**: compare stored or effective Taste across scopes or revisions;
- **promote project-to-global**: create a distinct global record linked to its
  project source; do not mutate the source's scope;
- **specialize global-to-project**: create a distinct project record linked to
  the global source and carrying the narrower selectors or rule;
- **deprecate**: retain an entry for history while excluding it from effective
  Taste;
- **revoke**: explicitly withdraw an entry and exclude it from resolution;
- **reset scope**: revoke or otherwise retire all entries in the named persisted
  scope without affecting the other scope; `both` performs the two resets;
- **explain effective Taste**: report each resolved rule, its producing source
  entry, shadowed or excluded entries, and unresolved conflicts.

Operations are auditable and update timestamps and lifecycle links atomically.
Promotion, specialization, and `both` always create distinct records rather than
changing inheritance semantics.

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

## 8. Use in the lifecycle

Admiral may inspect applicable Taste during intake and must preserve current
explicit instructions as highest-precedence inputs. Design applies effective
Taste only after filtering it through project conventions and mandatory
requirements. Review verifies both the chosen preferences and the constraints
that outrank them. Taste is a semantic input to those phases, not a new pipeline,
gate, stack lock, design-system owner, or session-memory namespace.
