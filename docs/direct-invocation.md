# Calling Skills Directly

Standalone tools run whenever you call them. Pipeline skills can be named too;
they start at `admiral` first. Small reversible work (Tier 0) skips all of it.
Rules: [routing.md](routing.md).

## Standalone tools

No pipeline, no intake, no gate.

| You want | Skill | Say |
|---|---|---|
| A visible browser | `open-browser` | "Use the open-browser skill to launch a browser workspace" |
| To drive a live page | `browse` | "Use the browse skill to click through the app and capture evidence" |
| An authenticated browser | `setup-browser-cookies` | "Use the setup-browser-cookies skill to log the browser into our app" |
| To share a browser session | `pair-agent` | "Use the pair-agent skill to let my teammate drive this browser" |
| To run a release | `ship` | "Use the ship skill to coordinate this release" |
| To merge and deploy | `land-and-deploy` | "Use the land-and-deploy skill to get this branch live" |
| Deploy config | `setup-deploy` | "Use the setup-deploy skill to set up the deploy config" |
| Release notes | `document-release` | "Use the document-release skill to write up what shipped" |
| To lock a path | `freeze` | "Use the freeze skill to protect src/payments from edits" |
| Locks plus intent checks | `guard` | "Use the guard skill to lock things down while we work" |
| A confirmation before something risky | `careful` | "Use the careful skill before this destructive step" |
| To unlock | `unfreeze` | "Use the unfreeze skill to open the area back up" |
| Testing with fixes | `qa` | "Use the qa skill to test this product and fix what's broken" |
| Testing without fixes | `qa-only` | "Use the qa-only skill, just tell me what's broken" |
| A performance comparison | `benchmark` | "Use the benchmark skill to compare performance" |
| A harness audit | `audit-improve` | "Use the audit-improve skill to audit the saved runs" |

## Pipeline work

Say what you want; routing handles it. Naming `admiral` is never wrong and never
required.

| You want | Goes to | Say |
|---|---|---|
| Idea to reviewed code | `admiral` | `Design, build, and review [your idea].` |
| A design | `admiral`, delegating `commander` | `Design [your idea].` |
| Code from an approved design | `admiral`, delegating `build-management` | `Implement this approved design.` |
| A review | `admiral`, delegating `code-chief` | `Review this codebase.` |
| A root cause | `admiral`, delegating `investigate` | `Find the root cause of this failure.` |
| A security audit | `admiral`, delegating `cso` | `Audit this codebase for security issues.` |
| Product testing | `admiral`, delegating `qa` | `Test this product and fix what's broken.` |
| A new skill or team | `skill-maker` | `Create a skill that [behavior].` |
| Save or resume | `session-memory` | `Save where we are.` / `Resume from saved state.` |

Each closes at its own boundary ([gatekeepers.md](gatekeepers.md)).

## Internal specialists

Skills under `design/`, `build/` and `review/`, plus `taste-review`,
`skill-creator` and `skill-reviewer`, are reached through their owning
sub-orchestrator. A host that scans one level deep never lists them.

## Without skill routing

From a checkout, provide `AGENTS.md` and the `SKILL.md` as context:

```text
Provide AGENTS.md and skills/admiral/SKILL.md, then ask: "Run the full pipeline for [description]."
Provide AGENTS.md and skills/review/code-chief/SKILL.md, then ask: "Review this codebase."
Provide AGENTS.md and skills/skill-maker/SKILL.md, then ask: "Create a skill that [behavior]."
```
