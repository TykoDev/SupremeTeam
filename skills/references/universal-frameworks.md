# Universal Dimensional Frameworks

> Shared reference for all Supreme Team skills. Every skill operates within
> these four cross-cutting frameworks. They define the constraints and quality
> standards that apply regardless of which pipeline or phase a skill belongs to.

---

## Build & Implementation Protocol

*(For non-build skills, this defines constraints; for build skills, this defines execution)*

- **Downstream Translation:** Ensure all decisions map directly to implementable
  code or deployment configuration. A recommendation that cannot be expressed as
  a code change or config value is incomplete.
- **Traceability:** Maintain stack-lock lineage and requirement tracking from
  concept to code. Every design decision should trace forward to implementation;
  every implementation choice should trace back to a requirement or ADR.

---

## Iron-Law Troubleshooting & Debugging

- **Observe & Hypothesize:** Gather evidence before drawing conclusions. Read
  error messages, stack traces, and logs before forming a theory.
- **Isolate & Verify:** Prove the root cause before applying or recommending a
  fix. A fix applied to a guess creates new problems.
- **No Ad-Hoc Adjustments:** Require regression testing or evidence for all
  remediations. "It works now" is not proof — tests passing is proof.

---

## Azure Deployment Integration

- **Environment Awareness:** Ensure all decisions consider CI/CD, resource
  constraints, and production topology. What works locally may fail in
  production due to network policies, resource limits, or missing env vars.
- **Deployment Safety:** Enforce idempotent operations, safe rollbacks, and
  secrets management via Key Vault. Never hardcode secrets. Every deployment
  must be reversible.

---

## Adversarial Anti-Gaming Protocol

- **Anti-Rubber-Stamp Rule:** No automatic approvals or progression. All outputs
  must cite specific evidence from the user or prior phases. "Looks good" is not
  a verdict.
- **Gaming Detection:** Actively detect and reject circular logic, phantom
  resolutions, and unchecked omissions. Watch for rewording without substance,
  scope-laundering of constraints, and severity deflation.
- **Pre-Verdict Self-Check:** Verify existence, accuracy, completeness,
  proportionality, and consistency before marking a task complete. Ask: "If this
  fails in production, would my review have caught it?"
