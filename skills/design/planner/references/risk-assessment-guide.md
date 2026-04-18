# Risk Assessment Guide

Use this guide when `planner` builds the risk register. The goal is not to list
every possible bad outcome; the goal is to identify the risks most likely to
change delivery order, scope, or rollout safety.

## Risk Categories

| Category | Use When | Typical Signals |
|----------|----------|-----------------|
| **Technical** | Architecture, performance, integration, or data risks | Unknown APIs, new framework, migration complexity |
| **Schedule** | Timeline or sequencing risks | Hard deadline, external launch date, narrow milestone spacing |
| **Resource** | Team capacity or ownership risks | Single-owner subsystem, missing specialist, parallel work overload |
| **External** | Vendor, partner, or dependency risks | Third-party API readiness, procurement, approval gates |
| **Security** | Exposure, compliance, or secret-management risks | Sensitive data, public endpoints, regulatory controls |

## Probability × Impact Matrix

Use the following matrix to score each risk:

| Probability | Impact | Score | Interpretation |
|-------------|--------|-------|----------------|
| Low | Low | 1 | Track only |
| Low | Medium | 2 | Watch |
| Low | High | 3 | Plan mitigation |
| Medium | Low | 2 | Watch |
| Medium | Medium | 4 | Active mitigation required |
| Medium | High | 6 | High priority |
| High | Low | 3 | Plan mitigation |
| High | Medium | 6 | High priority |
| High | High | 9 | Top escalation candidate |

## Mitigation Patterns

- **Technical unknowns**: add a spike, prototype, or contract test before the main phase starts.
- **Schedule compression**: reduce scope per milestone, not quality gates.
- **Resource bottlenecks**: assign explicit owners and cross-train a backup.
- **External dependencies**: model mock/fallback paths and set check-in dates.
- **Security risks**: shift controls earlier into architecture, CI, and rollout gates.

## Contingency Design

Every risk entry should answer: "What happens if this risk materializes anyway?"
Useful contingency patterns include:

- fallback scope reduction
- rollout pause criteria
- temporary feature flag disablement
- alternate vendor or integration path
- explicit user escalation trigger

Mitigation lowers probability. Contingency lowers impact. Strong project plans
document both.