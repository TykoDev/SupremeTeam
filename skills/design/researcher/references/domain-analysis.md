# Domain Analysis Methodology

## Event Storming

Event Storming is the primary domain discovery technique. It rapidly explores
business domains using color-coded elements arranged on a timeline.

### Event Storming Levels

| Level | Purpose | Participants | Duration |
|-------|---------|-------------|----------|
| **Big Picture** | Discover the full domain landscape | All stakeholders | 2-4 hours |
| **Process** | Detail specific business processes | Domain experts + engineers | 2-3 hours |
| **Design** | Derive aggregates, commands, policies | Engineers + architects | 1-2 hours |

### Color-Coded Elements

| Color | Element | Meaning | Example |
|-------|---------|---------|---------|
| **Orange** | Domain Event | Something that happened (past tense) | "Order Placed", "Payment Received" |
| **Blue** | Command | An action that triggers an event | "Place Order", "Process Payment" |
| **Yellow** | Aggregate | Cluster of entities that handle a command | "Order", "Payment" |
| **Purple/Lilac** | Policy | Automated reaction to an event | "When Payment Received, Ship Order" |
| **Pink** | External System | System outside the domain boundary | "Payment Gateway", "Email Service" |
| **Green** | Read Model | Data view optimized for queries | "Order Summary Dashboard" |
| **Red** | Hot Spot | Problem, question, or conflict | "What happens if payment fails mid-order?" |

### Event Storming Workflow

1. **Chaotic exploration**: List all domain events on the timeline (no order yet)
2. **Temporal ordering**: Arrange events chronologically left-to-right
3. **Add commands**: For each event, identify what command triggered it
4. **Identify aggregates**: Group related commands/events into aggregates
5. **Add policies**: Identify automated reactions between events
6. **Mark hot spots**: Flag ambiguities, conflicts, and open questions
7. **Identify bounded contexts**: Draw boundaries around cohesive groups

---

## Bounded Context Mapping

### Context Map Patterns

| Pattern | Relationship | Description |
|---------|-------------|-------------|
| **Shared Kernel** | Symmetric | Two contexts share a subset of the domain model |
| **Customer/Supplier** | Asymmetric | Upstream (supplier) provides, downstream (customer) consumes |
| **Conformist** | Asymmetric | Downstream conforms to upstream's model without translation |
| **Anti-Corruption Layer** | Protective | Downstream translates upstream's model into its own language |
| **Open Host Service** | Publishing | Context exposes a well-defined protocol for consumers |
| **Published Language** | Standard | Shared language (e.g., OpenAPI spec) for communication |
| **Separate Ways** | Independent | Contexts have no integration; duplicate as needed |

### Context Map Template

```markdown
## Context Map

### [Context A] ←→ [Context B]
- **Relationship**: [Pattern name]
- **Direction**: [Upstream/Downstream/Symmetric]
- **Integration mechanism**: [REST API / Events / Shared DB / etc.]
- **Data exchanged**: [Entities/events that cross the boundary]
- **Translation layer**: [Where and how models are translated]
```

---

## Domain Model Documentation

### Entity Template

```markdown
### Entity: [Name]
**Bounded Context**: [Context name]
**Type**: Aggregate Root | Entity | Value Object

#### Attributes
| Attribute | Type | Constraints | Description |
|-----------|------|------------|-------------|
| id | UUID | Primary key | Unique identifier |
| [attr] | [type] | [constraints] | [description] |

#### Business Rules
- [Rule 1]: [Description of invariant]
- [Rule 2]: [Description of invariant]

#### Relationships
- Has many [Entity B] (1:N)
- Belongs to [Entity C] (N:1)

#### Lifecycle Events
- Created → Active → Suspended → Closed
```

### Domain Classification

| Classification | Description | Strategic Importance |
|---------------|-------------|---------------------|
| **Core Domain** | The primary competitive advantage; custom-built | Highest investment, best engineers |
| **Supporting Domain** | Necessary but not differentiating; custom but simpler | Moderate investment |
| **Generic Domain** | Commodity; buy or use open-source | Minimal investment, outsource |

### Ubiquitous Language Glossary

Maintain a glossary of domain terms used consistently across all deliverables:

```markdown
## Ubiquitous Language

| Term | Definition | Context |
|------|-----------|---------|
| [Term] | [Precise definition] | [Where/how used] |
```

Ensure the same term is never used with different meanings in different contexts.
When contexts use different language for similar concepts, document the translation
in the context map.
