# Template 17: Error / Status Pages

**Scope**: 404, 500, maintenance, rate limiting, unauthorized.

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│           ┌──────────────────┐               │
│           │   404            │               │
│           │   Page not found │               │
│           │   The page you're│               │
│           │   looking for    │               │
│           │   doesn't exist. │               │
│           │   [Go Home]      │               │
│           │   [Report Issue] │               │
│           └──────────────────┘               │
└──────────────────────────────────────────────┘
```

## Error Page Standards

| Status | Content |
|--------|---------|
| **404** | Friendly message + search + homepage link + popular pages |
| **500** | Apology + retry button + homepage link + status page link |
| **Maintenance** | Downtime estimate + notification signup + countdown |
| **Rate Limited** | Explanation + countdown until reset + contact support |
| **Unauthorized** | Explanation + login link + request access link |

Always maintain site navbar and footer on error pages.
