# Example Invocations

## Example 1

**User request:** review security of the file-upload pipeline

**Output:**
- Scope: multipart upload handler, object-store write path, and the image-processing worker.
- Blocking issue: the handler trusts the client-supplied content type, which leaves the worker reachable with a crafted script payload.
- Fix direction: validate file signatures before enqueueing work and restrict the worker to the permitted media types.

## Example 2

**User request:** check for vulnerabilities in the new admin export feature

**Output:**
- Scope: admin export endpoint, CSV generation path, and authorization guard.
- Major finding: export authorization checks role membership but misses per-tenant scope, which can leak another tenant's data under an elevated shared account.
- Handoff: ask `review/mr-robot` to pressure-test tenant-boundary abuse cases once the trust-boundary mapping is recorded.

## Example 3

**User request:** audit the dependency risk in this release

**Output:**
- Scope: updated dependency manifest, lockfile delta, and the code paths that load the new parser library.
- Finding set: one dependency has a known advisory, but the packet marks it as conditional because the vulnerable feature is not reachable from the shipped configuration.
- Delivery: security packet that separates confirmed vulnerabilities from hardening follow-ups.
