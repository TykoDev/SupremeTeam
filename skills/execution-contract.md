# Execution Contract

This file is canonical for three things and nothing else: the exact text of the
six shared execution clauses every orchestrator and gatekeeper restates locally,
the definition of the blast-radius tier scale clause 1 selects from, and the
maintenance procedure that keeps those two in step across the affected set.

It is not canonical for entry routing or Tier 0 eligibility
([routing-doctrine.md](routing-doctrine.md)), for gate boundaries and evidence
keys ([gates.yaml](gates.yaml)), for the Save Context field set
([contracts/handoff-templates.md](contracts/handoff-templates.md)), or for
save-path ownership ([save-ownership.yaml](save-ownership.yaml)). A
phase-specific contract may add constraints on top of these clauses; it may not
weaken, reword, or reinterpret them.

## Contents

- [Enforcement status](#enforcement-status)
- [Canonical clauses](#canonical-clauses)
- [Tier selection](#tier-selection)
- [Tier 0 completion note](#tier-0-completion-note)
- [Maintenance rule](#maintenance-rule)
- [Failure paths](#failure-paths)

## Enforcement status

Some of what follows is compared by a script on every run of the suites; the
rest is a rule a reader applies by judgement. Conflating the two is how a
contract acquires a guarantee nothing verifies, so each row states which it is.
A reader must not assume any clause below is machine-checked unless this table
says so.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| This file states exactly six numbered clauses | machine-checked | `skills/validation/test_catalog_contracts.py`, `ExecutionContractTests.test_canonical_section_parses_to_six_clauses` |
| Every skill in the affected set restates all six clauses verbatim | machine-checked | `skills/validation/test_catalog_contracts.py`, `ExecutionContractTests.test_every_bound_skill_states_the_clauses_verbatim` |
| The canonical handoff block carries a `Preamble tier` field, and no *discovered* copy of that block drops it | machine-checked, with a discovery precondition | `skills/validation/test_catalog_contracts.py`, `SaveContextParityTests`. The scan counts a file as a copy only when it carries the block's `Run ID` anchor line: 89 files under `skills/` contain the words "Save Context" and 10 are parsed — the canonical copy plus nine others. The remaining 79, this file among them, mention the block without carrying it and are skipped, so a field dropped in one of those is invisible to the comparator. |
| Inside a typed gate record, findings use `Critical`, `Major`, `Minor`, `Info` and verdicts use `APPROVED`, `REVISE`, `ESCALATE` (clause 3) | machine-checked | `skills/harness/gatekeeper/check.py`, the `FINDING_SEVERITIES` and `VERDICTS` sets |
| Inside a typed gate record, an unavailable or errored check is a data gap rather than a pass (clause 5) | machine-checked | `skills/harness/gatekeeper/check.py`, `RESULT_STATUSES`, with `evidence_type_rules` in [gates.yaml](gates.yaml) |
| Writes stay inside the workspace and destructive actions need explicit owner intent (clause 4) | machine-checked only where hooks are registered | `skills/harness/hooks/pre_tool_use.py`; unregistered, clause 4 is judgement |
| A given run actually records the tier it selected, and the tier matches that run's blast radius (clause 1) | judgement | nothing — the comparator reads clause text in a SKILL.md, never a produced handoff |
| Proactive triggering, declining adjacent work, and suppressing the next-action offer (clause 2) | judgement | nothing |
| The six-part return shape of clause 6 | judgement | nothing — a gate checks the evidence keys it requires, not the shape of a response |
| Which tier a task belongs in, given the tier table below | judgement | nothing |

The comparator therefore proves that the clause text has not drifted between
this file and fifteen skills. It proves nothing about any individual run's
conduct. Both halves matter, and only one of them is mechanical.

## Canonical clauses

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Tier selection

Tier is a property of the run, not a fixed attribute of a skill. The same skill
runs at Tier 0 for a typo fix and at Tier 3 for an authentication change. Blast
radius decides:

| Tier | Blast radius | Ceremony |
| --- | --- | --- |
| 0 | Local, understood, reversible; acceptance is obvious | Direct change, focused verification, brief completion note |
| 1 | Bounded and read-only | Intake, evidence, no state change |
| 2 | Multi-step edits, delegation, external coordination | Full pipeline route, saved run, gate package |
| 3 | Destructive, security-sensitive, production, irreversible | Tier 2 plus explicit owner intent and a fresh human go decision |

Clause 1 records this tier and its rationale in the handoff as `Preamble tier`
in the Save Context block ([contracts/handoff-templates.md](contracts/handoff-templates.md)),
mirrored in [save-protocol.md](save-protocol.md) and in the normative field
table in [admiral/stub-contract.md](admiral/stub-contract.md). The `Context
tier` field in the same block is a different scale, drawn from `1`, `2`, `3`,
and does not satisfy clause 1. Where a scale is ambiguous in a record, the field
name decides: `Preamble tier` is always the blast-radius tier defined here.

Every copy of the Save Context block is compared against the canonical one, so a
field cannot be dropped silently. Nothing reads a written handoff and checks that
`Preamble tier` was filled in with a tier that matches the work, so that half is
judgement and a reviewer is the only check on it.

## Tier 0 completion note

Tier 0 is the one tier that produces no handoff, so clause 1's "brief completion
note" is the whole record of the run and this file fixes its shape. The note is
prose in the reply, not a saved artifact, and carries exactly four parts in this
order:

1. **Tier and rationale.** `Preamble tier: 0` plus the one-sentence reason the
   task met every Tier 0 condition in
   [routing-doctrine.md](routing-doctrine.md).
2. **Changes.** Each file touched and what changed in it.
3. **Checks.** Every verification actually performed, each with its result. A
   check that was not run is named as not run rather than omitted.
4. **Limitations.** Anything left unverified, unknown, or deliberately out of
   scope, or the explicit word `none`.

The note is judgement-only: no script reads it. Its value is that a reader can
tell at a glance whether Tier 0 was a defensible classification, and a run that
cannot fill all four parts honestly was not Tier 0 work.

## Maintenance rule

The affected set is fifteen skills, derived from
[team-manifest.yaml](team-manifest.yaml) so the list stays checkable rather
than remembered. Skill names here are the bare `name` values that manifest
records, because the comparator reads them from it; the directory a skill lives
in is a separate fact and is never part of the name:

- the entry orchestrator named by `front_door`: `admiral`;
- the ten pipeline owners in `phase_leads` plus `pipeline_owners`: `commander`,
  `build-management`, `code-chief`, `cso`, `investigate`, `qa`, `redesign`,
  `skill-maker`, `ship`, `taste`;
- the four gatekeepers in `cross_stage_gatekeeper` plus `phase_gatekeepers`:
  `gatekeeper-admiral`, `gatekeeper-design`, `gatekeeper-build`,
  `gatekeeper-code`.

Adding or removing a name in any of those five manifest keys changes the
affected set automatically, and the comparator fails until the new skill carries
the clauses. Nothing else needs editing here.

When a shared clause changes, update this file first, then update the local
statement of the clause in those fifteen skills, then rerun both suites:
`python skills/scripts/validate_manifests.py` for manifest and catalog
consistency, and `python -m unittest discover -s skills/validation -p "test_*.py"`
for the contract suites. The clause comparison lives in the second one:
`validate_manifests.py` never opens a SKILL.md, and
`skills/validation/test_catalog_contracts.py` is the test that reads the clause
text out of each affected skill. The six numbered clauses are compared exactly;
a paraphrase in a skill is drift.

The comparator normalises whitespace before comparing, so a line rewrap in a
skill is not drift. Every other difference is: a changed word, a changed
punctuation mark, a changed backtick.

**Who fixes a comparator failure.** The failure names a skill and a clause
number. The owner of the change that introduced the divergence repairs it, and
the repair is always to restore the canonical text in the skill, never to edit
the clause here so the skill matches. A clause is edited here only as a
deliberate contract change that then propagates to all fifteen skills in the
same revision. When the two directions are genuinely ambiguous, this file wins
and the skill is corrected.

## Failure paths

- **The comparator cannot run.** No Python, no import, or a suite that errors
  before collecting. The clause contract is then unverified, not satisfied. Say
  so, do not record a passing check, and treat every clause as judgement until
  the suite runs. A gate that needs the contract verified returns `ESCALATE`
  rather than approving on an unrun check.
- **A skill is in the affected set but has no `SKILL.md`.** The comparator
  reports it by name. This is a manifest defect, not a clause defect: either the
  manifest names a skill that does not exist, or a skill directory was moved
  without updating the manifest. Fix the manifest or restore the skill; do not
  silence the comparator by removing the name.
- **Clause 1 and a phase-specific contract disagree about a tier.** The higher
  tier wins, because the tiers are ordered by blast radius and the more
  cautious reading is the safe one. Record both readings and the choice in the
  handoff rationale.
- **The host cannot register hooks, so clause 4 has no deterministic
  enforcement.** Clause 4 still binds as judgement. State in the handoff that
  guarded-write enforcement is advisory in this host, and apply read-only or
  dry-run probes first rather than relying on a guard that is not running.
- **No handoff exists because the run is Tier 0.** The Tier 0 completion note
  above is the record. If the work grew past Tier 0 mid-run, reclassify per
  [routing-doctrine.md](routing-doctrine.md), open a handoff, and record the
  tier that the work actually reached rather than the one it started at.
- **An evidence check is unavailable at a gate.** Clause 5 governs: preserve the
  evidence, do not fabricate a result, and return `REVISE` or `ESCALATE` with
  the gap named. `check.py` treats an unavailable or errored typed record as a
  data gap, so the mechanical and judgement readings agree here.
