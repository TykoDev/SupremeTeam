# Direct Skill Invocation

Every skill can be invoked directly in standalone mode for targeted work. If
your tool supports native skill routing, invoke the skill by name. Otherwise,
reference the matching `skills/.../SKILL.md` file explicitly.

## Examples

| Task | Skill | Example Prompt |
|------|-------|----------------|
| Find bugs in code | `bug-review` | "Use the bug-review skill on this module" |
| Security audit | `security-review` or `security-builder` | "Use the security-review skill to audit this code for vulnerabilities" |
| Penetration testing | `mr-robot` | "Use the mr-robot skill to adversarially test this API" |
| Frontend audit | `frontier` | "Use the frontier skill to audit the frontend for accessibility" |
| Visual QA | `design-qa` | "Use the design-qa skill to audit the UI for visual inconsistencies" |
| Developer experience | `devex-review` | "Use the devex-review skill to test the onboarding flow" |
| Write tests | `test-builder` | "Use the test-builder skill to create a test suite for this module" |
| Debug a failure | `debugger` | "Use the debugger skill to investigate this error" |
| Code health score | `health-check` | "Use the health-check skill to run a quality dashboard on this project" |
| Architecture design | `architect` | "Use the architect skill to design the system architecture" |
| Azure deployment | `azure-provisioner` | "Use the azure-provisioner skill to deploy this application to Azure" |
| Azure infra audit | `gatekeeper-azure` | "Use the gatekeeper-azure skill to adversarially validate Azure deployment deliverables" |
| Save progress | `session-memory` | "Use the session-memory skill to checkpoint the current state" |

## Fallback for Tools Without Skill Routing

If your assistant does not auto-route skills, provide `AGENTS.md` and the
specific `SKILL.md` file as context, then issue the task request:

```text
Provide AGENTS.md and skills/design/commander/SKILL.md, then ask: "Design a new application for [description]."
Provide AGENTS.md and skills/admiral/SKILL.md, then ask: "Run the full pipeline for [description]."
Provide AGENTS.md and skills/review/code-chief/SKILL.md, then ask: "Review this codebase."
Provide AGENTS.md and skills/azure/azure-provisioner/SKILL.md, then ask: "Deploy [description] to Azure."
```

## Pipeline Entry Points

For orchestrated multi-phase work, use these entry skills:

| What you need | Entry skill | Prompt |
|---------------|-------------|--------|
| Full pipeline (idea to reviewed code) | `admiral` | `Use the admiral skill to design, build, and review [your idea].` |
| Full pipeline + Azure | `admiral` | `Use the admiral skill to design, build, review, and deploy [your idea] to Azure.` |
| Design a system | `commander` | `Use the commander skill to design [your idea].` |
| Build from a plan | `build-management` | `Use the build-management skill to implement this approved design.` |
| Review existing code | `code-chief` | `Use the code-chief skill to do a full code review of this codebase.` |
| Deploy to Azure | `azure-provisioner` | `Use the azure-provisioner skill to deploy this application to Azure.` |
