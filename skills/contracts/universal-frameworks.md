# Universal Frameworks

## Contents

- Responsibility
- Governing contract index
- Cross-cutting frameworks
- Enforcement limits
- Pointer failure paths
- Performance claims
- Use

## Responsibility

This is the shared contract index, not a new source of invariants. Each target
owns its rule; where a row and its target disagree, the target wins and this row
is the defect. Machine checks establish only the facts named below. Judgement
means a reviewer still owes the semantic assessment, not that tests never read
that document.

## Governing contract index

| Concern | Governing document | Backing | Comparator |
|---------|--------------------|---------|------------|
| Lifecycle states, transitions, rewind, resume | [workflow-protocol](workflow-protocol.md) | partial | `../validation/test_orchestration.py` `GuardedTransitionTests` parses declared states and checks gate guard edges. `../harness/gatekeeper/test_gate_manifests.py` compares boundary names; `../validation/test_docs_inventory.py` `GateProseTests` compares Submitter cells. Actual run transitions and semantic rewind decisions remain judgement. |
| Gate boundaries, required evidence, typed records | [gates.yaml](../gates.yaml) | partial | `../harness/gatekeeper/check.py` checks required keys, sanctioned applicability, typed shapes, digests and lineage. `../scripts/contract_floor.py` independently protects shipped obligations. Records attest observations; hashes do not prove their truth. |
| Claim support | [evidence-standards](evidence-standards.md) | partial | The gate checks artifact backing, hashes and input binding where required. It reads `.md` and `.txt` artifacts for blocked phrases and links; it does not compare their substantive contents with record claims. Specificity, trust, calibration and retention remain judgement. |
| Artifact ownership | [ownership.yaml](../ownership.yaml) | partial | `../scripts/validate_manifests.py` checks declared writers; `../validation/test_catalog_contracts.py` `OwnershipProseTests` checks selected SKILL.md claims. References and actual authorship are not fully checked. |
| Generated path ownership | [save-ownership.yaml](../save-ownership.yaml) | partial | `../validation/test_save_contracts.py` compares path policies; the pre-tool hook enforces only classes it recognizes, not every role or generated file. |
| Output destinations | [save-protocol](../save-protocol.md) | partial | `../scripts/output_paths.py` rejects unsupported kinds and traversal. Core run records use `save_run.py`. Phase directories and verdict naming conventions remain partly policy. |
| Pipeline stages and dependencies | [pipelines.yaml](../pipelines.yaml) | partial | `validate_manifests.py` and `../validation/test_pipeline_contracts.py` compare owners, boundaries, artifacts, scripts and declared dependency order. They do not prove stage execution or approval. |
| Roster | [team-manifest.yaml](../team-manifest.yaml) | partial | `validate_manifests.py` checks membership, role/list shapes and skill count. Routing classes also have catalog comparators; arbitrary grouping choices are not fully validated. |
| Execution clauses | [execution-contract](../execution-contract.md) | partial | `test_catalog_contracts.py` `ExecutionContractTests` compares six clauses in bound skills. Run tier selection and response quality remain judgement. |
| Delegation | [handoff-templates](handoff-templates.md) | partial | `SaveContextParityTests` compares discovered blocks carrying the Run ID anchor. Request/response semantics and skipped prose-only mentions are not validated. |
| Delivery record | [delivery-template](delivery-template.md) | authored policy | A complete response and its approval scope require review; generic catalog text scans are not a delivery-shape validator. |
| Layer owners and gate coverage | [responsibility-matrix](responsibility-matrix.md) | partial | `../validation/test_contract_mirrors.py` compares exact Owner cells and every Gate coverage column; `DeclaredCoverageTests` checks specialist coverage. Trigger, input/output and one-writer prose remain judgement. |
| Runtime | [runtime-manifest.yaml](../runtime-manifest.yaml) | partial | `../scripts/check_runtime.py` checks the interpreter. `validate_manifests.py` checks floor, launchers, commands and optional-dependency fallbacks; declaration is not proof that each launcher works. |
| Package delivery | [package-manifest.yaml](../package-manifest.yaml) | partial | `../scripts/package_check.py` rejects residue, symlinks and nested Git state in the selected set; manifest validation checks excludes and delivery flags. |
| Intake | [grill-me-doctrine](../grill-me-doctrine.md) | partial | The gate checks the hashed `decisions` artifact, not interview quality or whether it happened at the right time. |
| Preferences | [taste-doctrine](../taste-doctrine.md) | partial | `taste_prefs.py` validates storage and proposals; `taste-review` checks required evidence and typed records. User intent, complete semantic resolution and absence of a saved profile are not proved by record shape. |
| MCP discovery | [mcp-tools](../mcp-tools.md) | partial | `../scripts/mcp_registry.py` diagnoses metadata TTL and host/workspace identity. It never proves live availability or permissions, and a blank template never blocks unrelated intake. |
| Measured optimization | [performance-doctrine](../performance-doctrine.md) | judgement for measurement obligations | No performance gate key or typed timing record exists. Read the claim-triggered guidance; structural catalog coverage is not measurement validation. |

## Cross-cutting frameworks

| Framework | Minimum invariant | Practice |
|-----------|-------------------|----------|
| Context-first build | Read neighboring contracts and observed evidence before implementation. | [bob-the-builder](../build/bob-the-builder/SKILL.md), [researcher](../design/researcher/SKILL.md) |
| Grilled intake | Resolve load-bearing branches and record deferrals with reopen triggers. | [grill-me-doctrine](../grill-me-doctrine.md) |
| Systematic debugging | Reproduce, isolate one mechanism, test a candidate and return the bounded repair to its writer. | [investigate](../investigate/SKILL.md), [debugger](../build/debugger/SKILL.md) |
| Stack discipline | Lock versions and record dependency decisions. | [tech-stacks registry](../tech-stacks/registry.yaml) |
| Design system | One component model, responsive tiers, accessibility as correctness. | [design-doctrine](../design-doctrine.md), [architect](../design/architect/SKILL.md) |
| Redesign parity | Inventory first; four static directions; select before one living build. | [redesign](../design/redesign/SKILL.md), [design-mapper](../design/design-mapper/SKILL.md) |
| Taste | Confirm provenance, apply deterministic scope precedence, never outrank mandatory requirements. | [taste-doctrine](../taste-doctrine.md) |
| Release readiness | Configuration, rollback, owner go and exact revision binding precede rollout. | [ship](../ship/SKILL.md) |
| Adversarial review | Preserve evidence, failure paths, gaps and finding severity/status. | [code-chief](../review/code-chief/SKILL.md), [mr-robot](../review/mr-robot/SKILL.md) |
| Denial paths | Authorized probes demonstrate trust-boundary behavior rather than inferring it. | [security-review](../review/security-review/SKILL.md) |
| Optimization | Baseline, one mechanism, noise bounds and unchanged acceptance budgets. | [performance-doctrine](../performance-doctrine.md), [benchmark](../benchmark/SKILL.md) |
| Evidence-first reporting | Claim, scope, revision, hash, gap and trust level travel together. | [evidence-standards](evidence-standards.md) |

## Enforcement limits

`../validation/test_docs_inventory.py` reads this file for selected gate claims;
`test_catalog_contracts.py` scans catalog prose. Neither parses every row of this
index into a complete semantic model. The named sibling comparators, not this
index, decide what is actually checked. A new domain requirement needs its own
producer and evidence; it cannot remove a required gate key or reassign a writer.

## Pointer failure paths

- Missing/unreadable target: record the broken pointer, block dependent work and
  escalate; the index summary is not a substitute for the target.
- Target and row disagree: correct the row, not the target to match the index.
- Governing targets conflict: escalate the contract defect to the relevant owner.
- Named comparator missing or unable to run: mark that check unverified; never
  infer approval from absence of output.
- Concern not covered: Admiral routes the gap; do not invent an implicit owner.

## Performance claims

Build-management and code-chief link the performance doctrine when accepting a
performance claim. Benchmark and frontier may measure; delegation does not move
responsibility for the claim. Touching a hot path alone does not establish a win.
No approved package, render capture or functional test substitutes for a measured
baseline on a suitable host. Lack of a rig is a verification gap, not permission
to lower a budget or report an inferred speedup.

## Use

Apply the smallest relevant set and cite its evidence. Distinguish a static
contract comparison, an observed run, an attested record and semantic judgement.
