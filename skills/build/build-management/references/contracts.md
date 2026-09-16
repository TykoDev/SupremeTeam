# Contracts Reference

The full normative text of every contract `../SKILL.md` binds the build phase to.
The SKILL.md section of the same name carries one decision line per contract and
points here; this file is the single statement of the procedure behind each, so
neither document paraphrases the other.

## Contents

1. Vendoring detection — the mechanical rule that classifies a changed path, and the tighter rules that follow
2. Save-Protocol Adherence — what to persist and what to propagate

## The Contracts

- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes. The rule is mechanical rather than a judgment call. A changed path is non-first-party when it sits under a vendor or generated root (`vendor/`, `third_party/`, `node_modules/`, `dist/`, or any directory the generated-root policy declares), when its name or header marks it as machine-produced (a "do not edit" or generated banner, `*.generated.*`, `*_pb2.py`, `*.lock`), or when it entered the diff through a package manager or codegen step rather than an authored edit. Each such path is then listed with its upstream source and version, the owner who accepted it, and its scan note; it is excluded from first-party coverage and completeness claims rather than counted toward them; and it is never hand-edited, because an edit the next regeneration erases is not a fix — change the generator and regenerate.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.
