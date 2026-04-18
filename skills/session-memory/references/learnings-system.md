# Learnings System — Schema & Integration Guide

## JSONL Schema

Each line in `learnings.jsonl` is a self-contained JSON object:

```json
{
  "key": "zod-api-boundaries",
  "type": "pattern",
  "insight": "Use Zod schemas at all API boundaries for runtime type validation",
  "confidence": 8,
  "source": "session-memory",
  "files": ["src/api/validators.ts", "src/schemas/"],
  "tags": ["validation", "api", "typescript"],
  "created": "2026-04-14T16:30:00Z",
  "updated": "2026-04-14T16:30:00Z"
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | Yes | Unique kebab-case identifier. Max 50 chars. |
| `type` | enum | Yes | One of: `pattern`, `pitfall`, `preference`, `architecture`, `tool` |
| `insight` | string | Yes | The learning itself. One clear sentence. Max 200 chars. |
| `confidence` | integer | Yes | 1-10. How confident is this learning? |
| `source` | string | Yes | Which skill or user logged this learning |
| `files` | string[] | No | Related file paths (relative to workspace root) |
| `tags` | string[] | No | Categorization tags for search |
| `created` | ISO 8601 | Yes | When first logged |
| `updated` | ISO 8601 | Yes | When last updated or reconfirmed |

### Confidence Scale

| Score | Meaning |
|-------|---------|
| 1-2 | Hypothesis — observed once, not verified |
| 3-4 | Likely — observed multiple times or has supporting evidence |
| 5-6 | Confident — verified through testing or documentation |
| 7-8 | Strong — verified repeatedly, central to the project |
| 9-10 | Certain — foundational constraint, explicitly documented |

### Type Definitions

| Type | When to Use | Example |
|------|------------|---------|
| `pattern` | A code pattern that works well in this project | "State updates use immer for immutable transforms" |
| `pitfall` | Something to avoid — has caused bugs or confusion | "Do not use `any` in service layer — breaks type inference downstream" |
| `preference` | User or team stylistic preference | "Prefer named exports over default exports" |
| `architecture` | Architectural constraint or decision | "Auth service uses JWT with RS256, no session cookies" |
| `tool` | Tool configuration or workflow | "Run `bun test --bail` for fast feedback during development" |

---

## Deduplication Rules

Before appending a new learning:

1. **Key match:** Search existing entries for the same `key`
   - If found: update `insight` (if changed), bump `confidence` by 1 (max 10), update `updated` timestamp
   - If not found: proceed to semantic match

2. **Semantic match:** Search for entries with ≥2 overlapping `tags` and similar `insight` text

   **Similarity algorithm (pseudo-code):**
   ```
   function is_similar(existing, candidate):
     shared_tags = intersection(existing.tags, candidate.tags)
     if len(shared_tags) < 2: return false

     existing_words = significant_words(existing.insight)  # strip stop words, lowercase
     candidate_words = significant_words(candidate.insight)
     overlap = intersection(existing_words, candidate_words)
     similarity = len(overlap) / max(len(existing_words), len(candidate_words))

     return similarity >= 0.70
   ```

   - If a near-duplicate exists: present both to the user and ask whether to merge, supersede, or keep both
   - Do NOT auto-merge semantic matches — false positives are worse than duplicates

3. **No match:** Append as a new entry

---

## Learning Lifecycle States

Each entry may include a `status` field (default: `active`):

| State | Included in Search | Meaning |
|-------|-------------------|---------|
| `active` | Yes | Current, applicable knowledge |
| `superseded` | No (unless `--all`) | Replaced by a newer learning; field `superseded_by` contains the new key |
| `deprecated` | No (unless `--all`) | No longer applicable; field `deprecated_reason` explains why |
| `archived` | No (unless `--all`) | User chose to retain for history only |

When a learning transitions from `active`, add the transition fields and update `updated` timestamp. Never physically delete entries — mark them instead.

---

## Staleness Detection

A learning is **stale** when:
1. All files in its `files` array have been deleted from the workspace
2. The learning was created more than 90 days ago AND has never been updated (confidence never bumped)
3. The learning contradicts a more recent learning with the same tags

Stale entries are flagged, not deleted. Present them to the user during prune operations.

---

## Integration Patterns for Pipeline Skills

### Pre-Work Query (Recommended for all skills)

Before starting a task, skills should query relevant learnings:

```
Session-memory, search learnings:
- Files: {files I will modify}
- Tags: {my domain tags}
- Type: pitfall (defensive)
```

### Post-Work Logging (Recommended for all skills)

After completing a task, skills should log any new learnings:

```
Session-memory, log learning:
- Key: {descriptive-key}
- Type: {pattern|pitfall|preference|architecture|tool}
- Insight: {what was learned}
- Confidence: {1-10}
- Files: {related files}
- Tags: {relevant tags}
```

### Skill-Specific Query Patterns

| Skill | Recommended Query |
|-------|------------------|
| bob-the-builder | Search by files to modify + tags: implementation, coding-standards |
| test-builder | Search by files to test + tags: testing, test-patterns |
| security-builder | Search tags: security, auth, encryption |
| debugger | Search by affected files + tags: debugging, pitfall |
| architect | Search tags: architecture, infrastructure |
| designer | Search tags: frontend, design, ui |

---

## File Location & Format

**Primary storage:** `{workspace-root}/skillset-saves/learnings/learnings.jsonl`

**Format requirements:**
- One JSON object per line (JSONL format)
- UTF-8 encoding
- No trailing commas
- Each line is independently parseable (no multi-line JSON)
- File is append-only during normal operation (pruning rewrites the file)

**Backup:** Before any prune operation, copy the current file to `learnings.jsonl.bak`
