# Example Invocations

## Example 1

**User request:** review the developer experience of the new CLI release

**Output:**
- Scope: install guide, auth flow, first command, and troubleshooting section for the CLI.
- Blocking issue: the published quick start omits the required environment variable, so the first command fails with an unhelpful auth error.
- Fix direction: update the quick start and improve the CLI error message to name the missing variable.

## Example 2

**User request:** audit onboarding for the SDK sample app

**Output:**
- Scope: package install, sample app boot, credential setup, and first API request.
- Major friction: the sample app assumes an already-provisioned callback URL, which new integrators do not have when following the README.
- Delivery: developer-experience packet with the broken onboarding step, affected persona, and the smallest docs or sample change that resolves it.

## Example 3

**User request:** check the docs and tooling for the local dev stack

**Output:**
- Scope: local bootstrap script, environment setup docs, and the health-check command.
- Finding set: the docs target Node 22 while the bootstrap script still enforces Node 20, which creates a version-mismatch trap during first run.
- Handoff: ask `review/code-review` to confirm whether the script behavior itself should block merge or whether the docs drift is the primary issue.
