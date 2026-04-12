# Software Requirements Specification Template

## Document Metadata

```markdown
# SRS: [Project Name]
**Version**: [X.Y]
**Authors**: [Names]
**Status**: Draft | In Review | Approved
**Date**: YYYY-MM-DD
**Reviewers**: [Names]
```

---

## 1. Project Overview

### 1.1 Problem Statement
[What problem does this system solve? Who is affected? What is the current state?]

### 1.2 Project Vision
[One-paragraph description of the desired future state]

### 1.3 Success Metrics
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| [Metric 1] | [Target value] | [How measured] |
| [Metric 2] | [Target value] | [How measured] |

### 1.4 Scope Boundaries
**In scope**: [Explicit list]
**Out of scope**: [Explicit list — equally important]

---

## 2. Stakeholder Registry

| ID | Role | Name/Team | Key Concerns | Communication Cadence |
|----|------|-----------|-------------|----------------------|
| S01 | Business Owner | [Name] | [Concerns] | [Weekly/Monthly] |
| S02 | End User | [Segment] | [Concerns] | [User research cadence] |
| S03 | Architect | [Name] | [Concerns] | [Design reviews] |
| S04 | Security | [Team] | [Concerns] | [Security reviews] |
| S05 | SRE/Ops | [Team] | [Concerns] | [Ops reviews] |

---

## 3. Functional Requirements

### FR-001: [Requirement Title]
**Priority**: MUST | SHOULD | MAY
**Description**: [Clear statement of what the system does]
**Rationale**: [Why this is needed]
**Acceptance Criteria**:
- AC-001.1: GIVEN [precondition] WHEN [action] THEN [expected outcome]
- AC-001.2: GIVEN [precondition] WHEN [action] THEN [expected outcome]
**Error Scenarios**:
- ES-001.1: WHEN [error condition] THEN [system behavior]
**Dependencies**: [FR-XXX, external system, etc.]

[Repeat for each functional requirement...]

---

## 4. Non-Functional Requirements (ISO 25010 Mapping)

### 4.1 Performance Efficiency
| ID | Requirement | Threshold | Measurement |
|----|-------------|-----------|-------------|
| NFR-PE-01 | API response time | < 200ms p95 | Load test under 1000 concurrent users |
| NFR-PE-02 | Page load time | LCP < 2.5s | Core Web Vitals measurement |
| NFR-PE-03 | Database query time | < 50ms p95 | Query profiling |

### 4.2 Reliability
| ID | Requirement | Threshold | Measurement |
|----|-------------|-----------|-------------|
| NFR-RE-01 | Availability | ≥ 99.9% monthly | Uptime monitoring |
| NFR-RE-02 | Mean time to recovery | < 30 minutes | Incident log analysis |
| NFR-RE-03 | Data durability | Zero data loss | Backup verification |

### 4.3 Security
| ID | Requirement | Threshold | Measurement |
|----|-------------|-----------|-------------|
| NFR-SE-01 | Data encryption at rest | AES-256 | Security audit |
| NFR-SE-02 | Data encryption in transit | TLS 1.3 | SSL scan |
| NFR-SE-03 | Authentication | OWASP ASVS L2 | Penetration test |

### 4.4 Usability
| ID | Requirement | Threshold | Measurement |
|----|-------------|-----------|-------------|
| NFR-US-01 | Accessibility | WCAG 2.2 Level AA | Automated + manual audit |
| NFR-US-02 | Touch targets | ≥ 24×24px | Design review |

### 4.5 Maintainability
| ID | Requirement | Standard | Measurement |
|----|-------------|----------|-------------|
| NFR-MA-01 | Code coverage | ≥ 80% | CI pipeline report |
| NFR-MA-02 | Documentation | All public APIs documented | Review checklist |

### 4.6 Portability
| ID | Requirement | Standard | Measurement |
|----|-------------|----------|-------------|
| NFR-PO-01 | Container support | OCI-compliant images | Docker build verification |
| NFR-PO-02 | Cloud agnostic | No vendor-specific APIs in core | Architecture review |

### 4.7 Compatibility
| ID | Requirement | Threshold | Measurement |
|----|-------------|-----------|-------------|
| NFR-CO-01 | Browser support | Last 2 versions of Chrome, Firefox, Safari, Edge | Cross-browser testing |
| NFR-CO-02 | API backward compat | Semantic versioning with deprecation period | API versioning policy |

---

## 5. External Interface Requirements

### 5.1 User Interfaces
[High-level UI requirements — screen types, responsive breakpoints, key user flows]

### 5.2 API Interfaces
[External APIs consumed or exposed — protocols, authentication, rate limits]

### 5.3 Data Interfaces
[Data imports/exports, file formats, database connections, message queues]

### 5.4 Hardware/Infrastructure Interfaces
[Cloud provider requirements, hardware constraints, network requirements]

---

## 6. Domain Model

### 6.1 Bounded Contexts
[List each bounded context with its responsibility and relationships]

### 6.2 Core Entities
[Key domain entities with their attributes and relationships]

### 6.3 Domain Events
[Key events that flow between bounded contexts]

---

## 7. Constraints and Assumptions

### 7.1 Constraints
[Technical, business, regulatory, timeline constraints]

### 7.2 Assumptions
[Assumptions that, if invalidated, would change the requirements]

---

## 8. Open Questions

| ID | Question | Impact | Owner | Deadline |
|----|----------|--------|-------|----------|
| Q01 | [Question] | [What it affects] | [Who decides] | [When needed] |

---

## Quality Attributes Framework (ISO/IEC 25010:2023)

The nine quality characteristics for reference:

1. **Functional Suitability** — Completeness, correctness, appropriateness
2. **Performance Efficiency** — Time behavior, resource utilization, capacity
3. **Compatibility** — Co-existence, interoperability
4. **Usability** — Appropriateness recognizability, learnability, operability, user error protection, UI aesthetics, accessibility
5. **Reliability** — Maturity, availability, fault tolerance, recoverability
6. **Security** — Confidentiality, integrity, non-repudiation, accountability, authenticity
7. **Maintainability** — Modularity, reusability, analysability, modifiability, testability
8. **Portability** — Adaptability, installability, replaceability
9. **Safety** — Operational constraint satisfaction, risk identification, fail-safe, hazard warning
