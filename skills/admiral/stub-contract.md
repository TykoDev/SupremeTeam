# Admiral Stub Contract



## Contents



1. Scope

2. Stage Model

3. Required Stage Inputs

4. Handoff Rules

5. Delivery Contract

6. Persistence Contract

7. Agent Contract



## Scope



Admiral owns stage selection, cross-stage gate routing, persistence-aware resume behavior, and final delivery assembly.



## Stage Model



1. Design through commander

2. Build through build-management

3. Review through code-chief

4. Skill creation through skill-maker when requested (on-demand utility, not a sequential stage)



## Required Stage Inputs



- Design stage: user request, constraints, and mode selection

- Build stage: approved design package

- Review stage: approved build package plus design package for traceability

- Skill-creation stage: skill intent or team description with constraints



## Handoff Rules



- Admiral never edits a sub-orchestrator package.

- Every handoff record must capture approval state, revision count, and the current package revision identifier.

- Verdict vocabulary is limited to APPROVED, REVISE, and ESCALATE.

- Skill-creation verdicts map: SHIP → APPROVED, ITERATE → REVISE, BLOCKED → ESCALATE.

- Maximum revisions per cross-stage handoff: 2.



## Delivery Contract



- Deliver a unified package with table of contents, executive summary, traceability matrix, and prioritized next actions.

- Record unresolved disputes separately from approved deliverables.



## Persistence Contract



Every pipeline participant follows `../save-protocol.md` while persistence is active. Saving is not optional, because the run directory is the only thing a resume, a gate, or a later audit can read: an unsaved deliverable leaves the run with a phase that claims to have completed and no artifact to prove it. The write-ownership rules below bind orchestrators, specialists, and gatekeepers alike, because one writer per path class is what makes a conflicting write detectable instead of silent.



### Write Ownership



The authoritative path policy is `../save-ownership.yaml`; this table summarizes it.



| Owner | Owns These Paths |

|-------|------------------|

| `session-memory`, only through `harness/hooks/save_run.py` | `skillset-saves/_latest.md`, `runs/{run-id}/_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, `_history/` |

| Admiral | `runs/{run-id}/intake/report_grilling.md`, `intake/intake-brief.md`, `delivery/reports/handoff_{boundary}.md` (one cross-stage handoff record per boundary), `delivery/reports/delivery-package.md` |

| Phase leads (commander, build-management, code-chief; cso, investigate, qa, taste, skill-maker, ship for their pipelines) | `runs/{run-id}/{phase}/manifest.json`, `reports/`, `artifacts/`, `evidence/`, `packages/` |

| Specialists | Only the report, artifact, or evidence file named in their delegation, at the destination it names (resolved with `scripts/output_paths.py`) |

| Gatekeepers | `runs/{run-id}/{phase}/verdict_{boundary}.json` (phase gatekeeper) and `verdict_{boundary}.cross-stage.json` (gatekeeper-admiral), written through `harness/gatekeeper/check.py --verdict-out`; never the submission |

| `taste`, only through `taste/taste_prefs.py` | `skillset-saves/preferences/*` |



Phase state, skips, and the next action live in the run record and are published only through `save_run.py checkpoint` (`--set key=value`, `--next-action`). The active owner is published too, but from `--owner` rather than `--set`, which refuses it as a reserved field. Nested per-specialist directories, phase-state files, and hand-written pointers belong to no declared class and are write-ownership violations.



### Enforcement Rules



- Include a `### Save Context` block in every specialist delegation while persistence is active. The block is the delegate's only source of the run id, save path, owner, and return boundary, so a delegation without it produces work the run has no declared place to put.

- Write deliverables to the save path Save Context names whenever `Persistence active: yes`. A save made anywhere else belongs to no declared path class in `../save-ownership.yaml`: nothing owns it, no gate collects it, and the run record goes on pointing at a destination that stayed empty.

- Skip every save operation when Save Context is absent or carries `Persistence active: no`. Persistence off means the `save_run.py create` probe did not return `ok`, so a write attempted anyway lands outside any published run; the deliverable returns inline instead (`../save-protocol.md` §2).

- Before starting a new run, classify `skillset-saves/` as active/inactive/orphaned/missing/unreadable/conflict and resume an active reclaimable run before creating new state.

- Attempt persistence activation (`save_run.py create`) when no active run exists and file-system writes are available; activation failure downgrades to read-only resume or transient mode with one warning.

- Reuse saved artifacts only after lineage and package-shape validation.

- Rewind to the earliest affected stage when an approved upstream artifact changes or fails validation.



### Save Context Schema



Every `### Save Context` block delivered to a sub-orchestrator or specialist carries the canonical field set from `../contracts/handoff-templates.md` (mirrored in `../save-protocol.md`); neither file may drop a field the other carries. That parity is machine-checked — `SaveContextParityTests` in `../validation/test_catalog_contracts.py` compares the copies — so a field added to one and missed in the other fails the suite rather than degrading quietly at run time. Sub-orchestrators propagate the same fields when they delegate further:



| Field | Values | Notes |

|-------|--------|-------|

| `Run ID` | `{run-id}` | Stable for the entire run |

| `Phase` | `{phase}` | The declared phase directory |

| `Save path` | `skillset-saves/runs/{run-id}/{phase}/` | Forward slashes, workspace-relative |

| `Persistence active` | `yes` \| `no` | Reflects the actual `save_run.py create` probe result; a `yes` recorded ahead of an `ok` sends every delegate to save into a run that was never published |

| `Persistence probe result` | `ok` \| reason | Never omit |

| `Context tier` | `1` \| `2` \| `3` | Feeds artifact-mode decisions |

| `Preamble tier` | `0` \| `1` \| `2` \| `3`, plus rationale | Execution-contract clause 1: the run's blast radius and why. Not `Context tier` |

| `Artifact mode` | `inline` \| `file` \| `reference` | How the deliverable returns |

| `Session pin` | `true` \| `false` | True while the run is active and the lock is held |

| `Execution mode` | `agent` \| `skill` | Current mode after the per-boundary re-probe |

| `Submission ID` | `{id}` | Idempotency key for the boundary |

| `Revision` | `{revision}` | The run revision being worked |

| `Owner` | `{owner}` | The delegate that may write |

| `Expected artifact` | `{artifact}` | The one artifact the delegate returns, at its resolved destination |

| `Evidence paths` | relative paths | Existing evidence the delegate may rely on |

| `Artifact hashes` | `path: sha256` \| `none yet` | Hashes already registered |

| `Risks` | known risks \| `none declared` | Carried forward, never dropped |

| `Return boundary` | gate boundary | Where the returned package is validated |



A specialist that receives a Save Context block with `Persistence active: no` treats every save call as a no-op and surfaces its deliverable inline in the response, because with nothing being written the response is the entire record of the work. A specialist that receives `Session pin: true` honors admiral routing and does not spawn parallel skills: the pin marks a held run lock, and a skill that starts its own run beside it leaves two runs competing for the pin, which `../save-protocol.md` §2 resolves only by reclaiming one through `save_run.py recover --reason`.



### Session-Memory Integration



- Admiral engages `session-memory` first at intake (mandatory, after scope confirmation and before the first delegation), then at context tier 3+ escalations, before every gatekeeper-admiral submission, at session end, and on error recovery.

- Sub-orchestrators reference session-memory checkpoints during cross-session resume.

- See `save-protocol.md` for the complete directory structure, file formats, and resume protocol.



## Agent Contract



- Detect execution mode (agent or skill) at intake and record in state.

- In agent mode, manage state programmatically and delegate to sub-agents.

- In skill mode, provide instructions for the host agent to follow.

- Both modes use the same pipeline stages, handoff contracts, and save-protocol structure.

