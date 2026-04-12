# Supply Chain Security

This reference provides detailed procedures for supply chain security evaluation, including SBOM generation, dependency scanning, provenance verification, secrets detection, and end-to-end supply chain gate implementation.

---

## Software Bill of Materials (SBOM)

### Why SBOMs Are Required

SBOM generation is a baseline expectation in 2026. NIST SSDF practice PS.3.2 explicitly requires collecting and safeguarding provenance data for each release, with SBOM as a primary example. The EU Cyber Resilience Act will mandate SBOMs for market access by 2027.

An SBOM documents every component in a software artifact: direct dependencies, transitive dependencies, their versions, licenses, and known vulnerabilities. Without an SBOM, organizations cannot answer the question "are we affected?" when a new vulnerability is disclosed.

### SBOM Formats

**CycloneDX v1.7 (October 2025):**
- Achieved ECMA International standardization
- Full-stack BOM standard supporting SBOM and additional supply-chain artifacts
- Formats: JSON, XML, Protocol Buffers
- Supports: component inventory, vulnerability data, license information, dependency graph
- Tools: `cyclonedx-cli`, `cdxgen`, `syft` (Anchore)

**SPDX v3 (ISO/IEC 5962:2021):**
- International open standard with modernized 3.0 specification
- Formats: JSON-LD, Tag-Value, RDF/XML
- Supports: package information, file information, licensing, relationships
- Tools: `spdx-sbom-generator`, `syft`, `tern`

### SBOM Generation in CI

Integrate SBOM generation into the build pipeline:
1. Generate SBOM after successful build (before artifact signing)
2. Store SBOM alongside release artifacts (same storage, same retention policy)
3. Scan SBOM for known vulnerabilities (Trivy supports scanning CycloneDX/SPDX SBOMs)
4. Include SBOM reference in release metadata

---

## Software Composition Analysis (SCA)

### Purpose

SCA tools identify known vulnerabilities, license compliance issues, and malicious packages in open-source dependencies. Critical because 77–86% of application code now comes from open-source components.

### Key Tools

**Snyk:**
- Developer-first remediation guidance
- Reachability analysis: determines whether vulnerable code is actually called at runtime (reduces false positives by up to 98%)
- Auto-generates pull requests with safe upgrade paths
- Supports: npm, pip, Maven, Gradle, Go modules, NuGet, and more

**OWASP Dependency-Check:**
- Open-source, free
- Identifies known vulnerabilities using NVD, NPM Audit, and other data sources
- Generates reports in HTML, JSON, XML, SARIF
- Good baseline for teams without budget for commercial tools

**Dependabot (GitHub):**
- Automated dependency update PRs
- Vulnerability alerts integrated with GitHub Security Advisories
- Configurable update schedules and version constraints

**OSV-Based Scanners:**
- Use the Open Source Vulnerabilities (OSV) database
- Ecosystem-specific vulnerability data (npm, PyPI, RubyGems, crates.io, Go)
- Tools: `osv-scanner` (Google), integrated into various CI pipelines

### Transitive Dependency Scanning

Direct dependencies are only part of the risk. Transitive (indirect) dependencies introduce vulnerabilities that developers may not be aware of:
- A project depends on library A, which depends on library B, which has a critical vulnerability
- Scan the full dependency tree, not just direct dependencies
- Tools like Snyk and OWASP Dependency-Check resolve and scan transitive dependencies

### SCA Review Checks

When a PR adds or updates dependencies:
- [ ] New dependency is from a reputable publisher with active maintenance
- [ ] No known critical or high vulnerabilities in the dependency or its transitives
- [ ] License is compatible with the project's licensing requirements
- [ ] Dependency size is proportionate to the functionality it provides
- [ ] Lock file is updated and committed (prevents dependency confusion attacks)
- [ ] Minimum necessary version constraints are specified (not `*` or `latest`)

---

## SLSA Provenance and Integrity

### SLSA Framework

Supply-chain Levels for Software Artifacts (SLSA, pronounced "salsa") defines build levels for increasing trust in artifact provenance.

**SLSA Provenance v1.2:**
- Verifiable information about how an artifact was produced
- Captures: builder identity, source repository, build configuration, entry point
- Format: in-toto attestation with SLSA provenance predicate

**Build Levels:**

| Level | Requirements | Trust Guarantee |
|-------|-------------|-----------------|
| Build L0 | No provenance | No assurance |
| Build L1 | Provenance exists | Package has provenance; know where it came from |
| Build L2 | Hosted build service | Build process is harder to tamper with |
| Build L3 | Hardened build service | Build is resistant to insider threats |

### in-toto Attestation Framework

Specifies how to generate verifiable claims about software production that consumers can validate:
- Defines a standard envelope for attestations (who signed, what was signed, statement type)
- Supports multiple predicate types (SLSA provenance, vulnerability scan results, test results)
- Enables policy engines to verify attestations before deployment

### Sigstore / cosign

**Sigstore:**
- Open-source project for signing, verifying, and protecting software
- Records signatures in a transparency log (Rekor) for public auditability
- Uses ephemeral certificates via Fulcio CA (no long-lived key management)

**cosign:**
- Container image and artifact signing tool
- Supports: OCI images, blobs, in-toto attestations
- Integration: Sign artifacts in CI, verify in deployment pipeline

### Supply Chain Gate Implementation

End-to-end supply chain integrity gate:

```
Build → Generate SBOM → Scan Dependencies → Emit Provenance → Sign Artifacts → Verify at Deploy
```

1. **Build:** Compile/package the artifact in a hosted build environment (SLSA L2+)
2. **Generate SBOM:** Create CycloneDX or SPDX SBOM for the build output
3. **Scan dependencies:** Run SCA against the SBOM; fail on critical vulnerabilities without exception tickets
4. **Emit provenance:** Generate SLSA-aligned provenance attestation (in-toto format)
5. **Sign artifacts:** Sign the artifact and attestations using cosign
6. **Verify at deploy:** Verify signatures + attestations + policy compliance before deploying to production

---

## Secrets Detection

### The Problem

Embedded secrets (API keys, passwords, tokens, certificates) in source code are a critical vulnerability. Once committed, secrets persist in git history even if removed from HEAD.

### Key Tools

**TruffleHog v3:**
- 800+ credential detectors for APIs, cloud providers, and services
- **Active verification:** Tests whether detected credentials are actually live (revolutionary feature)
- Scans: git history, filesystems, S3 buckets, CI logs
- High signal-to-noise ratio due to verification

**Gitleaks:**
- Fast, lightweight, regex and entropy-based scanning
- Pre-commit hook integration for immediate developer feedback
- Configurable rules with allow-lists for false positive management
- Lower overhead than TruffleHog, suitable for pre-commit hooks

**GitHub Secret Scanning with Push Protection:**
- Server-side scanning that blocks pushes containing known secret patterns
- Prevents secrets from ever entering the repository
- Partner program: notifies service providers when their tokens are detected
- Push protection: blocks the push and alerts the developer before the secret is committed

### Best Practice: Layer Multiple Tools

Research confirms no single secrets detection tool catches all secrets. The recommended approach:
1. **Pre-commit:** Gitleaks (fast, local feedback)
2. **Push protection:** GitHub Secret Scanning (server-side, blocks before merge)
3. **Periodic deep scan:** TruffleHog v3 (comprehensive, with active verification)
4. **Incident response:** Defined playbook for secret rotation when detection fails

### Secrets Detection Review Checks

- [ ] No hardcoded secrets in the code change (API keys, passwords, tokens, certificates)
- [ ] Environment variables or secret management services used for all credentials
- [ ] `.gitignore` includes common secret file patterns (`.env`, `*.pem`, `*.key`)
- [ ] Pre-commit hooks are configured for secrets detection
- [ ] If a secret was accidentally committed: immediately rotate the credential, force-push to remove from history, scan for any usage of the compromised credential

---

## OWASP CI/CD Top 10 Security Risks

The OWASP CI/CD Top 10 addresses supply chain risks specific to build and deployment pipelines:

1. **Insufficient Flow Control Mechanisms:** Missing approval gates, direct push to production
2. **Inadequate Identity and Access Management:** Over-permissioned CI service accounts
3. **Dependency Chain Abuse:** Malicious packages, typosquatting, dependency confusion
4. **Poisoned Pipeline Execution:** Adversary injects malicious code into the build pipeline
5. **Insufficient PBAC (Pipeline-Based Access Controls):** CI jobs with excessive permissions
6. **Insufficient Credential Hygiene:** Long-lived secrets in CI, shared credentials across environments
7. **Insecure System Configuration:** Default CI configs, exposed CI dashboards, disabled security features
8. **Ungoverned Usage of 3rd Party Services:** CI plugins and marketplace integrations without vetting
9. **Improper Artifact Integrity Validation:** Artifacts deployed without signature verification
10. **Insufficient Logging and Visibility:** CI/CD actions not audited, missing security event logging

### CI/CD Security Review Checks

When a PR modifies CI/CD configuration:
- [ ] Pipeline changes require approval from platform/security team
- [ ] CI service accounts follow least privilege (no admin access to production)
- [ ] Secrets in CI are stored in the platform's secret management (not in config files)
- [ ] Third-party CI plugins/actions are pinned to specific versions (not `@latest` or `@main`)
- [ ] Build artifacts are signed before deployment
- [ ] Pipeline logs do not expose secrets or sensitive data
