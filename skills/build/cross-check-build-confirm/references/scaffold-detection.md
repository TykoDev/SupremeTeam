# Scaffold Detection Reference

## Exhaustive Pattern Catalog

### Category 1: Comment Markers

#### Primary Markers (BLOCKER)

| Pattern | Regex | Notes |
|---------|-------|-------|
| TODO | `(?i)\bTODO\b` | Any variation: TODO, Todo, todo |
| FIXME | `(?i)\bFIXME\b` | Marks known defects |
| HACK | `(?i)\bHACK\b` | Marks intentional shortcuts |
| XXX | `\bXXX\b` | Danger/problem marker |
| PLACEHOLDER | `(?i)\bPLACEHOLDER\b` | Explicit temporary content |
| STUB | `(?i)\bSTUB\b` | Stand-in implementation |
| NOT IMPLEMENTED | `(?i)not\s+implemented` | Explicit incompleteness |
| COMING SOON | `(?i)coming\s+soon` | Promised but missing feature |

#### Secondary Markers (WARNING)

| Pattern | Regex | Notes |
|---------|-------|-------|
| TEMP / TEMPORARY | `(?i)\bTEMP(ORARY)?\b` | May be intentional (temp file handling) — verify context |
| DUMMY | `(?i)\bDUMMY\b` | May be test-only — verify location |
| FAKE | `(?i)\bFAKE\b` | May be test factory — verify location |
| SAMPLE | `(?i)\bSAMPLE\b` | May be documentation — verify context |
| REMOVE | `(?i)\bREMOVE\s+(THIS|ME|BEFORE)\b` | Self-documenting removal request |
| CHANGE ME | `(?i)CHANGE\s*ME` | Default value placeholder |

#### False Positive Guidance

Acceptable contexts where these patterns are NOT findings:
- **Test files**: `MOCK` in test fixtures is expected (`*.test.ts`, `*.spec.py`, `tests/`)
- **Documentation**: `TODO` in a CONTRIBUTING.md roadmap section is acceptable
- **Comments explaining decisions**: "We do NOT use HACK X because..." is explaining, not marking
- **Variable names in domain code**: `sampleRate` in audio processing is a domain term, not a scaffold marker
- **Third-party code**: Patterns in `node_modules/`, `vendor/`, `.venv/` are excluded

---

### Category 2: Code Patterns

#### Empty or Minimal Implementations (BLOCKER)

| Pattern | Language | Regex/Detection |
|---------|----------|----------------|
| Empty function body | JavaScript/TypeScript | `function\s+\w+\([^)]*\)\s*\{\s*\}` |
| Empty function body | Python | `def\s+\w+\([^)]*\):\s*pass\s*$` |
| Empty function body | Go | `func\s+\w+\([^)]*\)\s*\{\s*\}` |
| Throw "not implemented" | JavaScript/TypeScript | `throw\s+new\s+Error\(["']not implemented` |
| Raise NotImplementedError | Python | `raise\s+NotImplementedError` |
| panic("not implemented") | Go | `panic\(["']not implemented` |
| todo!() macro | Rust | `todo!\(\)` |
| unimplemented!() macro | Rust | `unimplemented!\(\)` |

#### Hardcoded Return Values (BLOCKER — when computed values expected)

| Pattern | Detection | Context Check |
|---------|-----------|--------------|
| `return []` / `return {}` | Literal empty collection returns | Is this a default or should data be fetched? |
| `return null` / `return None` | Null returns in non-optional functions | Does the function type signature allow null? |
| `return "sample"` | String literal returns | Is this computed or truly static? |
| `return 0` / `return -1` | Numeric literal returns | Is this a sentinel value or placeholder? |

**Context is critical**: A function that returns `[]` as the initial state of an empty list is correct. A function named `getOrders()` that returns `[]` without querying the database is a scaffold.

#### Debug Statements (WARNING)

| Pattern | Language | Regex |
|---------|----------|-------|
| console.log | JavaScript/TypeScript | `console\.(log\|debug\|info\|warn\|error)\(` (verify not structured logging) |
| print() | Python | `(?<!\w)print\(` (verify not logging framework) |
| fmt.Println | Go | `fmt\.Print(ln\|f)?\(` (verify not intentional output) |
| dbg!() | Rust | `dbg!\(` |
| System.out.println | Java | `System\.out\.print` |

**Exclusion**: Structured logging through a logging framework (`logger.info()`, `log.Printf()`) is NOT a debug statement.

#### Empty Error Handling (BLOCKER)

| Pattern | Language | Regex |
|---------|----------|-------|
| Empty catch | JavaScript/TypeScript | `catch\s*\([^)]*\)\s*\{\s*\}` |
| Bare except | Python | `except:\s*pass` or `except\s+\w+:\s*pass` |
| Empty recover | Go | `recover\(\)` without handling |
| Ignored Result | Rust | `let\s+_\s*=\s*` on Result type (verify intentional) |

---

### Category 3: Data Patterns

#### Placeholder Text (BLOCKER in production paths)

| Pattern | Regex | Notes |
|---------|-------|-------|
| Lorem ipsum | `(?i)lorem\s+ipsum` | Filler text in any context |
| Dolor sit amet | `(?i)dolor\s+sit\s+amet` | Extended lorem ipsum |
| Foo/Bar/Baz | `(?i)\b(foo\|bar\|baz)\b` as variable values | Common placeholder values (verify not variable names) |

#### Placeholder Domains and Emails (BLOCKER in production config)

| Pattern | Regex | Notes |
|---------|-------|-------|
| example.com | `example\.(com\|org\|net)` | RFC 2606 reserved domain |
| test.com | `test\.(com\|org\|net)` in production config | May be legitimate in test files |
| test@test.com | `test@test\.\w+` | Placeholder email |
| user@example.com | `user@example\.\w+` | Placeholder email |
| admin@admin.com | `admin@admin\.\w+` | Default admin email |

#### Placeholder Addresses and IDs (WARNING)

| Pattern | Example | Notes |
|---------|---------|-------|
| Sequential IDs | `12345`, `99999`, `00000` | Hardcoded where generated expected |
| Placeholder phone | `555-`, `000-000-0000`, `+1234567890` | US placeholder phone patterns |
| Placeholder address | `123 Main St`, `Anytown` | Common test address |
| Placeholder names | `John Doe`, `Jane Smith`, `Acme Corp` | Only in production data, not test factories |

#### Localhost in Production (BLOCKER)

| Pattern | Regex | Notes |
|---------|-------|-------|
| 127.0.0.1 | `127\.0\.0\.1` in non-dev config | Should be env variable |
| localhost | `localhost` in production config | Should be env variable |
| 0.0.0.0 | `0\.0\.0\.0` in non-Docker config | Verify intentional binding |

---

### Category 4: Structural Patterns

#### Empty Directories (WARNING)

| Pattern | Detection |
|---------|-----------|
| Directory with only .gitkeep | `find -name .gitkeep` — verify planned content exists |
| Empty src/ subdirectories | Directories in source tree with no implementation files |

#### Stub Files (BLOCKER)

| Pattern | Detection |
|---------|-----------|
| File with only imports | File that imports modules but has no exports or logic |
| File with only type declarations | File that defines types but no functions (may be intentional — verify) |
| Boilerplate-only file | File containing only auto-generated template code without customization |

---

### Category 5: Configuration Patterns

#### Debug and Development Settings (BLOCKER in production config)

| Pattern | Regex | Notes |
|---------|-------|-------|
| DEBUG=true | `DEBUG\s*=\s*true` | Must be false or removed in production |
| NODE_ENV=development | `NODE_ENV\s*=\s*development` in committed config | Should be set by environment |
| VERBOSE=true | `VERBOSE\s*=\s*true` | Verify not in production config |

#### Default Secrets (BLOCKER)

| Pattern | Regex | Notes |
|---------|-------|-------|
| password=password | `password\s*=\s*["']?password` | Default credential |
| secret=secret | `secret\s*=\s*["']?secret` | Default secret |
| key=changeme | `key\s*=\s*["']?changeme` | Placeholder key |
| token=xxx | `token\s*=\s*["']?(xxx\|yyy\|placeholder)` | Placeholder token |

#### Missing Configuration (BLOCKER)

| Check | Detection |
|-------|-----------|
| No .env.example | File search — must exist if code references env vars |
| Missing env vars | Compare `process.env.X` / `os.environ["X"]` references against .env.example |
| Hardcoded URLs | `https?://` in source files outside config/ directory |

---

## Language-Specific Detection

### JavaScript/TypeScript

```regex
# TODO markers
(?i)(\/\/|\/\*)\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB)

# Empty functions
(async\s+)?function\s+\w+\([^)]*\)\s*\{\s*\}
\w+\s*=\s*(async\s+)?\([^)]*\)\s*=>\s*\{\s*\}

# Debug statements
console\.(log|debug|info|warn|error)\(

# Not implemented
throw\s+new\s+Error\(["']not\s+implemented

# Empty catch
catch\s*\([^)]*\)\s*\{\s*\}
```

### Python

```regex
# TODO markers
#\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB)

# Empty functions
def\s+\w+\([^)]*\):\s*(pass|\.\.\.)

# Debug statements
(?<!\w)print\(

# Not implemented
raise\s+NotImplementedError

# Bare except
except(\s+\w+)?:\s*pass
```

### Go

```regex
# TODO markers
//\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB)

# Empty functions
func\s+\w+\([^)]*\)\s*(\([^)]*\)\s*)?\{\s*\}

# Debug statements
fmt\.Print(ln|f)?\(

# Not implemented
panic\(["']not\s+implemented
```

### Rust

```regex
# TODO markers
//\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB)

# Not implemented
todo!\(\)
unimplemented!\(\)

# Debug macro
dbg!\(
```

---

## Detection Confidence Levels

| Confidence | Meaning | Action |
|------------|---------|--------|
| **High** | Pattern is almost certainly scaffold code | Report as BLOCKER without further context analysis |
| **Medium** | Pattern could be scaffold or legitimate | Report as WARNING; provide context for manual review |
| **Low** | Pattern is likely legitimate but worth flagging | Report as INFO; note the pattern and location |

| Pattern | Confidence |
|---------|-----------|
| `// TODO:` in production code | High |
| `throw new Error("not implemented")` | High |
| `console.log` in source (not test) | Medium |
| `MOCK` in non-test file | High |
| `SAMPLE` in config file | Medium |
| `return []` in a getter function | Medium (needs context) |
| `example.com` in test fixture | Low (likely acceptable) |
