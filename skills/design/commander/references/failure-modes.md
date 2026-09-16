# Failure Modes Reference

`../SKILL.md` carries the five failures that change what Commander does next
(absent Taste resolution, unregistered runtime, unusable input, exhausted revise
cycle, missing host capability). This file carries the rest: the lineage,
approval, skip, and Taste-drift failures whose handling is procedural. Nothing
here repeats a row stated in `../SKILL.md`.

## Contents

The table below covers, in order: phase disagreement, missing approval lineage,
upstream drift, Taste snapshot revision change, Taste revocation, a skip that
would drop a required design artifact, and a skip that would drop an endpoint
contract.

| Scenario | Response |
| --- | --- |
| Research, architecture, interface, security-seed, or planning work disagree on target users, scope, or locked stack assumptions | Freeze package assembly, preserve the contradictory phase outputs, and route the mismatch back to the owning phase instead of normalizing it inside the final package. |
| A phase deliverable looks polished but lacks the gatekeeper-design approval record for the current revision | Keep the phase closed, record the missing approval lineage, and rerun the gate before any later phase advances. |
| An upstream design change invalidates downstream phase work already assembled into the package | Invalidate the affected downstream artifacts, log the drift explicitly, and replay the pipeline from the earliest changed boundary. |
| A Taste source revision differs from the snapshot before `design-to-build` | Invalidate `taste_snapshot`, request re-resolution from Admiral/Taste, and replay every affected design-system decision before resubmission. |
| A used Taste entry is revoked, or a project preference conflicts with an already approved project design | Surface drift and ask the user whether to replay; never mutate either store or retroactively rewrite the approved design. |
| A requested skip would leave a required frontend, architecture, or implementation artifact absent from the design package | Reject the skip, name the missing boundary, and require an explicit scoped exception before proceeding. |
| A requested skip would leave an API endpoint contract absent for a surface the build must implement | Reject the skip, require `design/architect` to produce the endpoint inventory and contracts, or record a scoped backend-only/no-endpoint exception. |
