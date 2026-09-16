# Failure Modes Reference

`../SKILL.md` carries the six failures that change what Build-Management does
next (no startable entry point, absent or mismatched design approval, incoherent
design input, an investigation with no bounded path, an exhausted revise cycle,
a missing host capability). This file carries the rest: the revision-coherence,
phase-skip, and vendored-surface failures whose handling is procedural. Nothing
here repeats a row stated in `../SKILL.md`.

## Contents

The table below covers, in order: evidence pointing at different revisions, a
late change that invalidates passed tests, pressure to skip a mandatory phase,
and non-first-party content arriving without treatment.

| Scenario | Response |
| --- | --- |
| Implementation, test, security, or completeness artifacts point to different revisions of the build package | Treat the package as incoherent, require a single revision-aligned evidence set, and stop the handoff until the lineage is repaired. |
| A security remediation or late implementation fix changes the code surface after tests have already passed | Reopen the affected phases, rerun the necessary validation, and prevent the build packet from advancing on stale evidence. |
| Schedule pressure or a local workaround attempts to skip a mandatory build phase such as testing, security review, or completeness confirmation | Reject the shortcut and force the missing phase back into the pipeline before the package can claim readiness. |
| Generated, vendored, or third-party content appears in the build package without explicit ownership, scan notes, or change rationale | Isolate the non-first-party surface, require explicit treatment, and keep the package out of the review boundary until it is explained. |
