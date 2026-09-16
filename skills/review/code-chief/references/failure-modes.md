# Failure Modes Reference

`../SKILL.md` carries the five failures that change what Code-Chief does next
(an unsupported governance claim, a browserless host, an unusable build package,
an exhausted revise cycle, a missing host capability). This file carries the
rest: the lens-coverage, disagreement, and resubmission failures whose handling
is procedural. Nothing here repeats a row stated in `../SKILL.md`.

## Contents

The table below covers, in order: a missing mandatory lens, a conditional lens
invoked without its supporting artifacts, specialists disagreeing on severity,
and a resubmission that rewrites findings without a delta.

| Scenario | Response |
| --- | --- |
| A mandatory review lens is missing from the consolidated package | Stop the gate submission, record the missing lens, and route the package back for completion before summarizing any verdict. |
| Optional frontend or developer-experience phases were invoked without supporting artifacts | Remove the unsupported phase from the run, record the skip reason, and ask for rendered UI, screenshots, CLI traces, or onboarding evidence before re-adding it. |
| Specialist reports disagree on severity, exploitability, or scope | Preserve both positions in the consolidated package, identify the unresolved contradiction, and send the disagreement to `review/gatekeeper-code` rather than averaging the claims. |
| A resubmitted package changes findings without explaining the delta from the previous round | Compare the new package against the prior verdict, demand a revision summary, and reject silent rewrites of the review history. |
