# Checkpoint Format Specification

## File Naming

```
checkpoint_{YYYYMMDD}T{HHMMSS}Z.md
```

Example: `checkpoint_20260414T163000Z.md`

## YAML Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Always `"checkpoint"` |
| `version` | string | Yes | Schema version, currently `"1.0.0"` |
| `timestamp` | ISO 8601 | Yes | When the checkpoint was created |
| `branch` | string | Yes | Git branch name at checkpoint time |
| `head_commit` | string | Yes | Git HEAD commit hash (full 40-char) |
| `session_id` | string | No | Session identifier if in a pipeline run |
| `pipeline_context.run_id` | string | No | Run ID if in a pipeline run |
| `pipeline_context.pipeline_state` | string | No | Admiral state at checkpoint time |
| `pipeline_context.current_phase` | string | No | Active phase at checkpoint time |
| `auto_triggered` | boolean | No | `true` if auto-checkpoint, `false` if user-requested |
| `trigger_reason` | string | No | Why the auto-checkpoint was triggered (e.g., "tier_escalation", "gate_submission") |

## Markdown Body Sections

### Modified Files (Required)
List all files with uncommitted changes (staged + unstaged). Use relative paths.

```markdown
## Modified Files
- src/api/routes.ts (modified, staged)
- src/models/user.ts (modified, unstaged)
- tests/api.test.ts (new, staged)
```

### Decisions Made (Required)
Number each decision made in the session. Include the rationale.

```markdown
## Decisions Made
1. Chose PostgreSQL over MySQL for JSON column support (ADR-003)
2. Implemented rate limiting at the API gateway level, not per-service
3. Used Zod for runtime validation instead of class-validator
```

### Remaining Work (Required)
Number each remaining item. Be specific enough that a fresh session can pick up without re-reading the full conversation.

```markdown
## Remaining Work
1. Implement the `/users/:id/permissions` endpoint (spec in design-package §4.2)
2. Write integration tests for the auth middleware
3. Update the OpenAPI spec to match the implemented routes
```

### Context Notes (Optional)
Free-form notes that provide critical context a new session needs. This is the "handoff memo."

```markdown
## Context Notes
- The user prefers snake_case for database columns and camelCase for API responses
- There is a known issue with the test database seeding — run `bun db:seed` manually before tests
- The deployment pipeline uses GitHub Actions, not the CI/CD described in the design spec
```

## Storage Hierarchy

```
skillset-saves/
├── checkpoints/                    # Standalone checkpoints (outside pipeline runs)
│   ├── checkpoint_20260414T163000Z.md
│   └── checkpoint_20260414T180000Z.md
└── runs/
    └── run-001_2026-04-14_project/
        └── checkpoints/            # Pipeline run checkpoints
            ├── checkpoint_20260414T163000Z.md
            └── checkpoint_20260414T170000Z.md
```

## Resume Validation

On resume, validate in this order:

1. **Branch match:** Is the current branch the same as the checkpoint branch?
   - Same → proceed
   - Different → warn, show both branches, ask user
2. **Commit match:** Is HEAD the same as the checkpoint commit?
   - Same → proceed, nothing changed
   - Different → show the commits since checkpoint, warn about potential conflicts
3. **File existence:** Do the modified files listed in the checkpoint still exist?
   - All exist → proceed
   - Some missing → warn about missing files, they may have been committed or deleted
4. **Pipeline state (if applicable):** Does `_state.md` match the checkpoint's pipeline context?
   - Match → proceed
   - Mismatch → the pipeline advanced since checkpoint, use `_state.md` as authoritative
