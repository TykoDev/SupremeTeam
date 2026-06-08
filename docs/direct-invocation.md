# Direct Skill Invocation

How a skill is reached depends on its routing tier (see
[routing.md](routing.md) and `skills/routing-doctrine.md`):

- **Standalone tools** (`safety-guardrails/*`, `browser-automation/*`,
  `release-and-deployment/*`, `testing-and-qa/*`) are out of routing scope and
  can be invoked directly at any time.
- **In-scope pipeline skills** (`design/commander`, `build/build-management`,
  `review/code-chief`, `skill-maker`, `investigate`, `session-memory`,
  `gatekeeper-admiral`) are components of the Admiral pipeline. When reached cold
  — without an active Admiral handoff — they hand off to `admiral` first so the
  run gets one intake, one persisted state, and one cross-stage gate. They still
  run their specialist work; they just route through admiral to start it.
- **Internal specialists** (e.g. `architect`, `bob-the-builder`, `mr-robot`, the
  stage gatekeepers) are reached via their owning sub-orchestrator, not as a
  user entry point.

If your tool supports native skill routing, invoke a skill by name. Otherwise,
reference the matching `skills/.../SKILL.md` file explicitly.

## Standalone Tools (invoke directly)

| Task | Skill | Example Prompt |
|------|-------|----------------|
| Open a visible browser | `open-browser` | "Use the open-browser skill to launch a browser workspace" |
| Drive a live page | `browse` | "Use the browse skill to click through the app and capture evidence" |
| Authenticate a browser | `setup-browser-cookies` | "Use the setup-browser-cookies skill to log the browser into our app" |
| Share a browser session | `pair-agent` | "Use the pair-agent skill to let my teammate drive this browser" |
| Run a release | `ship` | "Use the ship skill to coordinate this release" |
| Merge & deploy | `land-and-deploy` | "Use the land-and-deploy skill to get this branch live" |
| Configure deploys | `setup-deploy` | "Use the setup-deploy skill to set up the deploy config" |
| Write release notes | `document-release` | "Use the document-release skill to write up what shipped" |
| Lock a path | `freeze` | "Use the freeze skill to protect src/payments from edits" |
| Combined guard | `guard` | "Use the guard skill to lock things down while we work" |
| Confirm before risk | `careful` | "Use the careful skill before this destructive step" |
| Lift a lock | `unfreeze` | "Use the unfreeze skill to open the area back up" |
| Test & fix | `qa` | "Use the qa skill to test this product and fix what's broken" |
| Test, report only | `qa-only` | "Use the qa-only skill — just tell me what's broken" |
| Measure performance | `benchmark` | "Use the benchmark skill to compare performance" |

## Pipeline Skills (route through admiral)

| What you need | Entry skill | Prompt |
|---------------|-------------|--------|
| Full pipeline (idea to reviewed code) | `admiral` | `Use the admiral skill to design, build, and review [your idea].` |
| Design a system | `admiral` (delegates `commander`) | `Design [your idea].` |
| Build from a plan | `admiral` (delegates `build-management`) | `Implement this approved design.` |
| Review existing code | `admiral` (delegates `code-chief`) | `Review this codebase.` |
| Investigate a bug | `admiral` (delegates `investigate`) | `Find the root cause of this failure.` |
| Create a skill / team | `skill-maker` | `Create a skill that [behavior].` |
| Checkpoint / resume | `session-memory` | `Save where we are.` / `Resume from saved state.` |

> A bare request to one of the in-scope skills (e.g. "Design [idea]") is honored
> — it just initiates through admiral first. Naming admiral explicitly is never
> wrong, but it is not required for the pipeline to engage.

## Fallback for Tools Without Skill Routing

If your assistant does not auto-route skills, provide `AGENTS.md` and the
specific `SKILL.md` file as context, then issue the task request:

```text
Provide AGENTS.md and skills/admiral/SKILL.md, then ask: "Run the full pipeline for [description]."
Provide AGENTS.md and skills/review/code-chief/SKILL.md, then ask: "Review this codebase."
Provide AGENTS.md and skills/skill-maker/SKILL.md, then ask: "Create a skill that [behavior]."
```
