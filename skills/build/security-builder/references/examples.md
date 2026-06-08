# Example Invocations

## Example 1

**User request:** harden the build

**Output:**
- Finding: attachment uploads trust the client-supplied filename and content type.
- Remediation: sanitize filenames, enforce server-side content checks, and rerun the upload regression tests.
- Gate note: the build can advance only after the rerun evidence is attached to the same revision.

## Example 2

**User request:** review build security

**Output:**
- Scope: token issuance flow, admin endpoints, and a newly added dependency for document parsing.
- Risk: the document parser ships with a high-severity advisory in a transitive package, so the package is not security-clean.
- Next move: replace or pin the dependency before `cross-check-build-confirm` treats the build as complete.

## Example 3

**User request:** check dependency risk

**Output:**
- Result: first-party code is unchanged, but the build introduces generated SDK files and a third-party auth adapter.
- Handling: mark the non-first-party surfaces explicitly, attach the scan evidence, and narrow the security claim to the reviewed boundaries.
- Recommendation: if the auth adapter requires policy changes, route that back through design rather than hiding it as a dependency tweak.

## Example 4

**User request:** harden the build — critical CVE found in a transitive dependency with no available fix

**Context:** Dependency scan surfaces a Critical CVE in a transitive package (`xml-parse-core@2.1.0`) used by the document ingestion module. No patched version exists and the dependency cannot be dropped or replaced within the approved build scope.

**Output:**
- Finding: Critical CVE in `xml-parse-core@2.1.0`; exploit path is reachable through the document ingestion module's parse call.
- Fix boundary: no patched version is available upstream; replacing the dependency requires an architectural change outside the assigned build scope.
- Action taken: CVE documented as an open Critical finding; no speculative patch applied because the safe fix exceeds build authority.
- Escalation: returning an escalation packet to `build/build-management` with the CVE reference, affected module path, exploit path summary, and a recommendation to route through design for a dependency replacement decision. The build package is marked not security-clean and must not advance until the escalation is resolved or a documented exception with owner sign-off is attached.
