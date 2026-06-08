# Example Invocations

## Example 1

**User request:** freeze this area around the payment hotfix

**Output:**
- Boundary: `services/payments/**` and the deployment pipeline that promotes payment changes.
- Freeze state: no edits or deploys inside that boundary until the incident owner clears the hotfix window.
- Safe work: continue log analysis and test work outside the frozen payment surface.

## Example 2

**User request:** protect this path from edits during the migration

**Output:**
- Boundary: migration scripts and the schema history directory.
- Exception handling: the in-flight rollback verification may finish, but no new migration files can be added after that bounded step.
- Release condition: complete rollback verification and attach the checksum evidence before unfreezing.

## Example 3

**User request:** lock the boundary while we stabilize release candidates

**Output:**
- Boundary: release manifests, version files, and the publish workflow.
- Freeze record: block direct edits and require any exception to cite release-owner approval.
- Next safe action: continue changelog drafting and artifact verification outside the locked files.
