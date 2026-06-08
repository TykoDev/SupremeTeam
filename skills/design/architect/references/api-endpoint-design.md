# API Endpoint Design — Contract Template

Architect owns API endpoint design whenever the system exposes HTTP, RPC, webhook, event-ingest, or internal service endpoints. The endpoint contract is part of the architecture package and must be concrete enough for build and review phases to implement tests without reinterpreting intent.

Run the `../../grill-me-doctrine.md` planning-mode decision prompt contract before locking endpoint behavior. Auto-resolve framework, router, schema, auth, and serialization conventions from the codebase when discoverable; ask the user only for policy and product decisions the code cannot answer.

## Endpoint Inventory

Start every API package with an inventory table:

| Method | Path / Topic | Purpose | Consumer | Owner | Auth | State Change | Contract Tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/items` | List items | Web UI | `items-service` | user token | no | required |

Include internal endpoints and webhooks when build work depends on them. If the design is backend-only but has no endpoint surface, record an explicit skip with the reason.

## Endpoint Contract Template

Each endpoint must include these fields, filled concretely:

```markdown
### {METHOD} {path}

**Purpose**: one sentence tied to a user or system job.
**Owner**: service/module/team responsible for behavior.
**Consumers**: frontend route, worker, integration, partner, or internal caller.
**Auth and authorization**: identity source, required roles/scopes, tenant boundary, anonymous behavior.
**Request shape**:
- Path params:
- Query params:
- Headers:
- Body schema:
- Validation rules:
**Response shape**:
- Success status:
- Success body schema:
- Empty-state response:
- Error envelope:
- Status codes:
**Behavior**:
- Side effects:
- Idempotency/retry behavior:
- Pagination/filtering/sorting:
- Caching/ETag behavior:
- Rate limits/quotas:
- Consistency/transaction boundary:
**Security and privacy**:
- Sensitive fields:
- Logging/redaction:
- Abuse cases:
**Versioning and compatibility**:
- Version strategy:
- Backward compatibility promise:
- Deprecation behavior:
**Observability**:
- Metrics:
- Logs:
- Traces/correlation IDs:
**Contract tests**:
- Positive cases:
- Validation/error cases:
- Auth/authorization cases:
- Compatibility cases:
```

## Error Envelope

Use one error shape per API surface unless an upstream platform already enforces one:

```json
{
  "error": {
    "code": "ITEM_NOT_FOUND",
    "message": "Human-readable summary safe for clients.",
    "details": {},
    "correlation_id": "01H..."
  }
}
```

Document every exception. Do not let endpoints invent one-off error formats.

## Frontend Handoff

For user-facing surfaces, map endpoints into the UI/UX specification:

| Route / Screen | Endpoint | Load State | Empty State | Error State | Mutation Feedback |
| --- | --- | --- | --- | --- | --- |

Every form submission must name the endpoint, client-side validation, server-side validation, optimistic/pessimistic behavior, retry policy, and user-visible error message.

## Acceptance Checklist

- Endpoint inventory covers every API, webhook, job trigger, and frontend dependency in scope.
- Each endpoint has auth, authorization, validation, status codes, and error envelope defined.
- Mutating endpoints define idempotency, side effects, transaction boundaries, and retry behavior.
- List endpoints define pagination, filtering, sorting, and empty-state semantics.
- Security/privacy handling names sensitive fields and redaction requirements.
- Observability fields are sufficient for production triage.
- Contract tests cover success, validation, auth, authorization, and compatibility behavior.
- Frontend screens depending on endpoints map loading, empty, error, success, and mutation-feedback states.

## Failure Modes

| Scenario | Response |
| --- | --- |
| An endpoint is named but lacks request/response schemas | Treat the architecture as not build-ready and require the full contract template. |
| Auth is described generically as "protected" | Require identity source, roles/scopes, tenant boundary, and anonymous behavior. |
| A mutation omits idempotency or retry behavior | Preserve it as a blocking consistency risk before build work starts. |
| The frontend spec depends on API data without a route-to-endpoint map | Reopen the UI/API handoff and require state behavior for loading, empty, error, success, and mutation feedback. |
