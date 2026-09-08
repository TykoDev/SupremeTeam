# Calling Skills Directly

Short version: standalone tools you call whenever you want. Pipeline skills you
can also name directly, they just start at `admiral` first. Small reversible work
skips all of it and just gets done.

The rules behind that are in [routing.md](routing.md).

## Standalone tools

Out of routing scope. No pipeline, no intake, no gate. Just call them.

| You want | Skill | Say something like |
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

## Pipeline work

You do not have to say "admiral". Say what you want; routing handles it.

| You want | Goes to | Say something like |
|---|---|---|
| The whole thing, idea to reviewed code | `admiral` | `Use the admiral skill to design, build, and review [your idea].` |
| A design | `admiral`, delegating `commander` | `Design [your idea].` |
| Code from an approved plan | `admiral`, delegating `build-management` | `Implement this approved design.` |
| A review | `admiral`, delegating `code-chief` | `Review this codebase.` |
| To find out why something broke | `admiral`, delegating `investigate` | `Find the root cause of this failure.` |
| A security audit | `admiral`, delegating `cso` | `Audit this codebase for security issues.` |
| Product testing | `admiral`, delegating `qa` | `Test this product and fix what's broken.` |
| A new skill or team | `skill-maker` | `Create a skill that [behavior].` |
| To save or resume | `session-memory` | `Save where we are.` / `Resume from saved state.` |

Naming a pipeline skill directly is fine. "Design this thing" is honored, it just
initiates through admiral so the run gets one intake, one persisted state, and one
cross-stage gate. Naming admiral explicitly is never wrong, and never required.

Every one of these closes at its own gate boundary. The boundary table and the
evidence each needs is in [gatekeepers.md](gatekeepers.md).

## Internal specialists

`architect`, `bob-the-builder`, `mr-robot`, the stage gatekeepers, and the rest of
the skills under `design/`, `build/`, and `review/` are reached through their
owning sub-orchestrator. They are not user entry points, and calling one cold will
route you back through the front door.

## If your tool has no skill routing

Provide `AGENTS.md` and the specific `SKILL.md` as context, then ask:

```text
Provide AGENTS.md and skills/admiral/SKILL.md, then ask: "Run the full pipeline for [description]."
Provide AGENTS.md and skills/review/code-chief/SKILL.md, then ask: "Review this codebase."
Provide AGENTS.md and skills/skill-maker/SKILL.md, then ask: "Create a skill that [behavior]."
```
