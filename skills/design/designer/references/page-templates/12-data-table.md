# Template 12: Data Table / CRUD Page

**Scope**: List, search, filter, create, update, delete records.

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│ PAGE HEADER: Title + description             │
├──────────────────────────────────────────────┤
│ TOOLBAR                                      │
│ [Search...] [Filter ▾] [Sort ▾] [+ Add New]  │
│ Active filters: [Status: Active ×] [Date ×]  │
├──────────────────────────────────────────────┤
│ DATA TABLE                                   │
│ ☐ Name          Email           Status  Act │
│ ☐ John Doe    john@mail.com    Active  ⋯  │
│ ☐ Jane Smith  jane@mail.com    Inact.  ⋯  │
│ Showing 1-10 of 234 results                  │
│ [< 1 2 3 ... 24 >]  Items: [20 ▾]           │
├──────────────────────────────────────────────┤
│ BULK ACTIONS BAR (when items selected)       │
│ 3 selected  [Delete] [Export] [Change Status] │
└──────────────────────────────────────────────┘
```

## Interaction Standards

- Column headers: Sortable (click for asc/desc toggle)
- Row hover: Highlight background
- Row actions: Kebab menu (⋮) with Edit, Delete, Duplicate
- Checkbox column: Select all / individual
- Bulk actions: Show action bar when items selected
- Empty state: "No items found" + [Create First Item]
- Loading: Skeleton rows matching table structure
- Mobile: Convert to card layout (each row → card)
