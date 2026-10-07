"""Independent safety floor for the shipped gate contract.

This is intentionally not derived from gates.yaml: weakening that input must
not redefine a validator's acceptance criterion. Stronger requirements may be
added in the spec; changing this floor requires a reviewed code change too.
Explicit --gates experiments are reported as non-shipped and are not authority.
"""
from __future__ import annotations

REQUIRED = {
    "design-to-build": "decisions architecture interfaces plan acceptance security_seed stack_lock taste_snapshot ui_evidence",
    "redesign-review": "design_inventory taste_grilling taste_snapshot design_directions mock_set mock_parity mock_rendering selection selected_variant parity_evidence rendered_verification accessibility_evidence recommendation residual_risk",
    "build-to-review": "approved_design_revision implementation tests runtime traceability security_evidence",
    "review-to-delivery": "review_verdict findings executed_probes rendered_verification residual_risk revision_lineage",
    "security-review": "scope threat_model findings vulnerability_scan denial_path_evidence remediation_plan residual_risk",
    "investigation-review": "scope reproduction mechanism evidence_chain fix_path residual_uncertainty",
    "qa-review": "scope test_matrix executed_probes defects fixes_applied residual_risk",
    "taste-review": "scope intent before_revision preference_diff confirmation conflict_analysis policy_check persistence_result effective_profile consumer_handoff taste_review_record residual_uncertainty",
    "skill-maker-to-delivery": "skills team_manifest link_report validation_report",
    "deploy-readiness": "approved_delivery deploy_config verification_plan rollback_plan human_go_required",
}
ARTIFACTS = {
    "design-to-build": "decisions architecture plan taste_snapshot",
    "redesign-review": "design_inventory taste_grilling taste_snapshot design_directions mock_set mock_parity mock_rendering selection selected_variant parity_evidence rendered_verification",
    "build-to-review": "tests runtime", "review-to-delivery": "executed_probes rendered_verification",
    "security-review": "threat_model denial_path_evidence", "investigation-review": "reproduction evidence_chain",
    "qa-review": "test_matrix executed_probes",
    "taste-review": "preference_diff confirmation conflict_analysis persistence_result effective_profile taste_review_record",
    "skill-maker-to-delivery": "link_report validation_report", "deploy-readiness": "deploy_config verification_plan rollback_plan",
}
SUBMITTERS = dict(zip(REQUIRED, ("commander", "redesign", "build-management", "code-chief", "cso",
                                  "investigate", "qa", "taste", "skill-maker", "ship"), strict=True))
FALLBACKS = {
    "security_evidence": ["no trust-boundary change - security-builder not engaged"],
    "stack_lock": ["no new runtime or framework - existing stack unchanged"],
    "ui_evidence": ["no user-facing surface - design system not engaged"],
    "taste_snapshot": ["no saved Taste profile available"],
    "rendered_verification": ["no visible surface changed - rendered verification not applicable"],
    "denial_path_evidence": ["static analysis only - active probes not authorized"],
    "vulnerability_scan": ["no dependency or source scan surface - scanner not engaged"],
    "fixes_applied": ["report-only run - no fixes applied"],
    "team_manifest": ["single skill - no team manifest produced"],
}
SELECTION_FALLBACKS = {"deferred": "selection deferred - no variant built",
                       "merge": "merge brief recorded - implemented as a fifth direction in the design pipeline"}
DEPENDENT_KEYS = ["selected_variant", "parity_evidence", "rendered_verification", "accessibility_evidence"]
BOUNDARY_FALLBACKS = {
    "redesign-review": {key: list(SELECTION_FALLBACKS.values()) for key in DEPENDENT_KEYS},
    "taste-review": {"before_revision": ["new store - no prior revision"],
                     "consumer_handoff": ["preference management only - no downstream consumer"],
                     "residual_uncertainty": ["none observed"]},
}
TYPES = {
    **dict.fromkeys("tests runtime executed_probes reproduction evidence_chain test_matrix denial_path_evidence mock_parity parity_evidence".split(), "probe"),
    **dict.fromkeys("rendered_verification mock_rendering".split(), "render"),
    **dict.fromkeys("findings security_evidence defects accessibility_evidence".split(), "findings"),
    "vulnerability_scan": "scan", "review_verdict": "verdict", "stack_lock": "stack_lock",
    "approved_design_revision": "revision_ref", "approved_delivery": "revision_ref",
    **{name: name for name in "preference_diff confirmation conflict_analysis persistence_result effective_profile consumer_handoff selection security_seed".split()},
    "human_go_required": "human_go", "mock_set": "variant_set", "selected_variant": "variant_set",
}


def gate_floor_errors(spec: dict) -> list[str]:
    errors = []
    boundaries = spec.get("boundaries", {})
    if not isinstance(boundaries, dict):
        return ["gate safety floor: boundaries must be a mapping"]
    for name, keys in REQUIRED.items():
        boundary = boundaries.get(name)
        if not isinstance(boundary, dict):
            errors.append(f"gate safety floor: missing boundary {name}")
            continue
        if boundary.get("submitter") != SUBMITTERS[name]:
            errors.append(f"gate safety floor: {name}.submitter changed")
        for field, expected in (("required_evidence", keys), ("artifact_evidence", ARTIFACTS[name])):
            value = boundary.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value) or not set(expected.split()) <= set(value):
                errors.append(f"gate safety floor: {name}.{field} weakened")
    types = spec.get("evidence_types", {})
    if not isinstance(types, dict) or any(types.get(key) != kind for key, kind in TYPES.items()):
        errors.append("gate safety floor: typed evidence weakened")
    policy = spec.get("finding_policy", {})
    if not isinstance(policy, dict) or policy.get("critical") != "verified-before-gate" or policy.get("major_deferral") != "owner-and-reopen-trigger":
        errors.append("gate safety floor: finding policy weakened")
    redesign = boundaries.get("redesign-review", {})
    if not isinstance(redesign, dict) or "mock_rendering" not in (redesign.get("no_fallback") or []):
        errors.append("gate safety floor: mock_rendering waiver bar removed")
    def waivers(table: object, allowed: dict, label: str) -> None:
        if not isinstance(table, dict):
            errors.append(f"gate safety floor: {label} must be a mapping")
            return
        for key, reasons in table.items():
            if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons) or not set(reasons) <= set(allowed.get(key, [])):
                errors.append(f"gate safety floor: unsanctioned {label} waiver for {key}")

    waivers(spec.get("fallback_values", {}), FALLBACKS, "global")
    for name, boundary in boundaries.items():
        if isinstance(boundary, dict):
            waivers(boundary.get("fallback_values", {}), BOUNDARY_FALLBACKS.get(name, {}), name)
    params = spec.get("evidence_type_params", {})
    if not isinstance(params, dict):
        return errors + ["gate safety floor: evidence_type_params must be a mapping"]
    for key, count, field, files in (("mock_set", 4, "mocks", ["spec", "tokens", "components", "mock"]),
                                    ("selected_variant", 1, "variants", ["spec", "tokens", "components", "app"])):
        record = params.get(key, {})
        if not isinstance(record, dict) or record.get("required_count") != count or record.get("list_field") != field or record.get("file_fields") != files:
            errors.append(f"gate safety floor: {key} variant contract weakened")
    selection = params.get("selection", {})
    expected = {"decision_values": ["variant", "merge", "deferred"], "variant_decision": "variant",
                "option_key": "mock_set", "built_key": "selected_variant", "dependent_keys": DEPENDENT_KEYS,
                "fallback_by_decision": SELECTION_FALLBACKS}
    if not isinstance(selection, dict) or any(selection.get(key) != value for key, value in expected.items()):
        errors.append("gate safety floor: selection binding weakened")
    return errors
