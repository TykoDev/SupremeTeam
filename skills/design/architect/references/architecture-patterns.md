# Architecture Patterns Reference

## Clean Architecture

### Core Principle
Dependencies always point inward. The domain core knows nothing about
databases, frameworks, or UI. Outer layers depend on inner layers, never
the reverse.

### Layers (Inside Out)

```
┌─────────────────────────────────────────────┐
│              Frameworks & Drivers            │  ← HTTP, DB, UI, External APIs
│  ┌─────────────────────────────────────────┐ │
│  │          Interface Adapters             │ │  ← Controllers, Gateways, Presenters
│  │  ┌─────────────────────────────────────┐│ │
│  │  │        Application (Use Cases)      ││ │  ← Application-specific business rules
│  │  │  ┌─────────────────────────────────┐││ │
│  │  │  │     Enterprise (Entities)       │││ │  ← Enterprise-wide business rules
│  │  │  └─────────────────────────────────┘││ │
│  │  └─────────────────────────────────────┘│ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Rules
1. Domain entities MUST be free from framework annotations and dependencies
2. Use cases define application behavior using domain entities
3. Interface adapters translate between use case formats and external formats
4. Dependency injection wires outer layers to inner interfaces

### When to Use
- Complex business logic with many rules and invariants
- Long-lived applications (5+ years expected lifetime)
- High testability requirements (domain testable without infrastructure)
- Multiple delivery channels (API, CLI, message consumer)

### When NOT to Use
- Simple CRUD applications with minimal business logic
- MVPs where speed-to-market is the priority
- Small teams where the overhead outweighs the benefits

---

## Hexagonal Architecture (Ports and Adapters)

### Core Principle
The application core defines "ports" (interfaces) for how it communicates
with the outside world. "Adapters" implement these ports for specific
technologies.

### Structure

```
          ┌──────────────┐
    ┌───→ │ REST Adapter  │
    │     └──────┬───────┘
    │            │ (Driving Port)
    │     ┌──────▼───────┐
    │     │              │
    │     │   DOMAIN     │
    │     │   (Core)     │
    │     │              │
    │     └──────┬───────┘
    │            │ (Driven Port)
    │     ┌──────▼───────┐
    └───← │ DB Adapter   │
          └──────────────┘

Driving Adapters              Driven Adapters
(input)                       (output)
- REST controller             - PostgreSQL repository
- GraphQL resolver            - Redis cache
- CLI handler                 - SMTP email sender
- Message consumer            - S3 file storage
```

### Ports
- **Driving ports** (primary): Interfaces the application exposes to the world
- **Driven ports** (secondary): Interfaces the application uses to talk to infrastructure

### Adapters
- **Driving adapters**: Implement the technology that calls into the application
- **Driven adapters**: Implement the technology the application calls out to

---

## Event-Driven Architecture

### Core Components

| Component | Purpose | Technology Examples |
|-----------|---------|-------------------|
| **Event Producer** | Emits events when state changes | Application services |
| **Event Bus/Broker** | Routes events to consumers | Kafka, RabbitMQ, NATS |
| **Event Consumer** | Reacts to events | Subscriber services |
| **Event Store** | Persists events as source of truth | EventStoreDB, Kafka |

### Key Patterns

#### Outbox Pattern
Write to database AND event table in the same transaction. A separate
process reads the outbox and publishes events. Ensures exactly-once
delivery semantics.

```
Transaction:
  1. INSERT INTO orders (...)
  2. INSERT INTO outbox (event_type, payload, status='PENDING')
COMMIT

Background worker:
  1. SELECT FROM outbox WHERE status='PENDING'
  2. Publish to message broker
  3. UPDATE outbox SET status='PUBLISHED'
```

#### Saga Pattern
Manage distributed transactions across services using a sequence of
local transactions with compensating actions for rollback.

#### Event Sourcing
Store all changes as a sequence of events rather than current state.
Rebuild state by replaying events. Enables audit trails and temporal queries.

---

## CQRS (Command Query Responsibility Segregation)

Separate the read model (queries) from the write model (commands):

```
Commands → Write Model → Event Store → Projections → Read Model → Queries
```

### When to Use CQRS
- Read and write workloads have very different scaling needs
- Complex domain with many invariants on writes
- Need for audit trails (combine with Event Sourcing)
- Multiple read views of the same data

### When NOT to Use
- Simple CRUD with uniform read/write patterns
- Small applications without scaling concerns

---

## Microservices vs Monolith Decision Framework

| Factor | Monolith Preferred | Microservices Preferred |
|--------|-------------------|------------------------|
| **Team size** | < 5 developers | > 15 developers |
| **Domain complexity** | Single bounded context | Multiple distinct contexts |
| **Deployment independence** | Not needed | Critical |
| **Scaling** | Uniform scaling sufficient | Components scale independently |
| **Data consistency** | Strong consistency needed | Eventual consistency acceptable |
| **Operational maturity** | Limited DevOps capability | Strong DevOps, CI/CD, observability |
| **Timeline** | MVP / rapid delivery | Platform / long-term evolution |

### Modular Monolith (Recommended Starting Point)
Start with a well-structured monolith using domain modules. Each module
has clear boundaries, its own models, and communicates via defined interfaces.
Extract to microservices only when the monolith's constraints become real
bottlenecks — not theoretical ones.

---

## API Protocol Selection Guide

| Protocol | Best For | Latency | Payload | Client Control |
|----------|---------|---------|---------|---------------|
| **REST + OpenAPI** | External/public APIs | ~12ms | ~1,247B | Low (fixed endpoints) |
| **gRPC + Protobuf** | Service-to-service | ~4ms | ~312B | Low (RPC contracts) |
| **tRPC** | Full-stack TypeScript | ~8ms | Variable | High (type-safe RPC) |
| **GraphQL** | Client-driven data needs | ~15ms | Variable | High (flexible queries) |

### Multi-Protocol Architecture
```
External clients  →  REST (OpenAPI 3.1)
Frontend app      →  tRPC or GraphQL
Service ↔ Service →  gRPC (Protocol Buffers)
Async events      →  AsyncAPI (Kafka/NATS/RabbitMQ)
```
