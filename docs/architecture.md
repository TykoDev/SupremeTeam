# Pipeline Architecture

Supreme Team orchestrates four sub-pipelines through a single entry point
(**admiral**), with cross-pipeline validation at every handoff boundary.

## Pipeline Flow

```
 USER IDEA / EXISTING ARTIFACTS
       |
       v
    +-----------+
    |  ADMIRAL  |
    +-----------+
       |
       v
 +---------------------------+     +---------------------+
 | design/commander          | --> | GATEKEEPER-ADMIRAL  |  Handoff 1:
 | researcher -> planner ->  |     | Design -> Build     |  Build-ready?
 | architect -> designer ->  |     +---------------------+
 | engineer                  |
 +---------------------------+
       |
       v
 +---------------------------+     +---------------------+
 | build/build-management    | --> | GATEKEEPER-ADMIRAL  |  Handoff 2:
 | bob-the-builder ->        |     | Build -> Review     |  Review-ready?
 | test-builder ->           |     +---------------------+
 | security-builder ->       |
 | cross-check-build-confirm |
 | [debugger] [health-check] |
 +---------------------------+
       |
       v
 +---------------------------+     +---------------------+
 | review/code-chief         | --> | GATEKEEPER-ADMIRAL  |  Handoff 3:
 | bug-review -> code-review |     | Review -> Delivery  |  Delivery-ready?
 | -> quality-review ->      |     | or Review -> Azure  |
 | security-review ->        |     +---------------------+
 | mr-robot -> frontier ->   |
 | design-qa -> devex-review |
 +---------------------------+
       |
       v
 +---------------------------+     +---------------------+
 | azure/azure-provisioner   | --> | GATEKEEPER-ADMIRAL  |  Handoff 4:
 | azure-planner ->          |     | Azure -> Delivery   |  Delivery-ready?
 | azure-architect ->        |     +---------------------+
 | azure-configurator ->     |
 | azure-deployer ->         |
 | azure-verifier            |
 +---------------------------+
       |
       v
  +-----------------------+
  | FINAL DELIVERY PACKAGE |
  +-----------------------+
```

Stage 4 (Azure) runs only when the request targets Azure deployment or admiral
resumes from already-reviewed artifacts.

## Admiral

Admiral is the single entry point for the full pipeline. It:

1. Receives the user's project idea, constraints, and goals
2. Determines the pipeline mode (full, partial, or single sub-pipeline)
3. Delegates to sub-orchestrators in sequence
4. Submits each sub-pipeline output to gatekeeper-admiral for cross-pipeline validation
5. Delivers a consolidated package containing all design, build, review, and (optionally) Azure deployment artifacts

### Trigger Phrases

```
"Run the full pipeline on this idea"
"Design, build, and review this project"
"Take this from idea to reviewed code"
"Run admiral"
"Start the end-to-end pipeline"
"Design, build, review, and deploy to Azure"
"Deploy this to Azure"
"Resume the pipeline"
```

## Pipeline Modes

Admiral supports multiple execution modes:

| Mode | Stages | When to Use |
|------|--------|-------------|
| **Full Pipeline** | Design -> Build -> Review | New project idea, end-to-end |
| **Full Pipeline + Azure** | Design -> Build -> Review -> Azure | New project idea targeting Azure deployment |
| **Design + Build** | Design -> Build | Plan and implement, review later |
| **Build + Review** | Build -> Review | Have a design, need implementation and validation |
| **Build + Review + Azure** | Build -> Review -> Azure | Have a design, implement, validate, and deploy |
| **Review + Azure** | Review -> Azure | Have code, validate and deploy |
| **Design Only** | Design | Planning and architecture only |
| **Build Only** | Build | Have a plan, need implementation |
| **Review Only** | Review | Have code, need validation |
| **Azure Only** | Azure | Have reviewed code, need Azure deployment |

Admiral auto-detects existing artifacts. If a design package is provided, it
skips to build. If an existing codebase is provided, it skips to review. If a
validated review package is already available, it can enter at Azure. If the
request mentions Azure, cloud deployment, or infrastructure provisioning, the
Azure stage is included automatically.

## Design Sub-Pipeline

Primary entry skill: **`commander`** (`skills/design/commander/SKILL.md`)

```
commander -> researcher -> gatekeeper-design -> planner -> gatekeeper-design ->
architect -> gatekeeper-design -> designer -> gatekeeper-design ->
engineer -> gatekeeper-design -> Design Package
```

Output: Approved Design Package (SRS, architecture, API contracts, stack locks,
implementation spec)

## Build Sub-Pipeline

Primary entry skill: **`build-management`** (`skills/build/build-management/SKILL.md`)

```
build-management -> bob-the-builder -> gatekeeper-build ->
test-builder -> gatekeeper-build -> security-builder -> gatekeeper-build ->
cross-check-build-confirm -> gatekeeper-build -> Build Package
```

Utility skills **debugger** and **health-check** are available on-demand within
the build sub-pipeline for root-cause investigation and code quality scoring.

Output: Production-ready code, tests, security audit, completeness certification

## Review Sub-Pipeline

Primary entry skill: **`code-chief`** (`skills/review/code-chief/SKILL.md`)

```
code-chief -> bug-review -> code-review -> quality-review ->
security-review -> mr-robot -> frontier* -> design-qa* -> devex-review* ->
gatekeeper-code -> Review Package

* frontier skipped for backend-only projects
* design-qa skipped when no frontend components exist
* devex-review skipped when not targeting developer-facing products
```

Output: Adversarially-validated review reports with merge recommendation

## Azure Sub-Pipeline

Primary entry skill: **`azure-provisioner`** (`skills/azure/azure-provisioner/SKILL.md`)

```
azure-provisioner -> azure-planner -> gatekeeper-azure ->
azure-architect -> gatekeeper-azure -> azure-configurator -> gatekeeper-azure ->
azure-deployer -> gatekeeper-azure -> azure-verifier -> gatekeeper-azure -> Azure Package
```

Output: Deployment runbook, Bicep templates, configuration spec, verification
report, gatekeeper adversarial findings
