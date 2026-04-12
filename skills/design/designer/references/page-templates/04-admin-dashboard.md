# Template 04: Admin Dashboard

**Scope**: Back-office interface for managing data, users, settings, and
business operations. The most versatile template.

**Layout Architecture**: Persistent sidebar navigation + top header bar + main
content area. Sidebar is collapsible on desktop and hidden (drawer) on mobile.

---

## Section Breakdown

```
┌────────┬──────────────────────────────────────┐
│ SIDE   │ TOP BAR                              │
│ BAR    │ [Burger] [Search...] [Notifications] [User]│
│        ├──────────────────────────────────────┤
│ [Logo] │ PAGE HEADER                          │
│        │ Page title + description              │
│ Dash   │ [Action button] [Filter] [Export]     │
│ Users  ├──────────────────────────────────────┤
│ Prod   │                                      │
│ Order  │ MAIN CONTENT                         │
│ Anal   │ (Data tables, stats cards, charts)    │
│ Sett   │                                      │
│        │                                      │
│ [Col]  │                                      │
│ lapse  │                                      │
├────────┴──────────────────────────────────────┤
│ FOOTER (minimal, optional)                    │
└──────────────────────────────────────────────┘
```

---

## Sidebar Navigation Structure

- **Primary items**: Dashboard, main entities (Users, Products, Orders)
- **Secondary items**: Analytics, Reports, Integrations
- **Bottom items**: Settings, Help, Logout
- **Collapse state**: Show icons only when collapsed (64px), icons + labels
  expanded (240–280px)

## Dashboard Home Page Content

1. Welcome banner (optional)
2. 4 stat cards in a row (Revenue, Users, Orders, Conversion Rate)
3. Primary chart (line chart showing trends over time)
4. Secondary charts (2 columns: bar chart + donut chart)
5. Recent activity table (last 10 items)
6. Quick actions panel

## Responsive Behavior

- **Mobile**: Sidebar hidden, accessible via hamburger → overlay drawer.
  Content full width. Stats cards stack vertically.
- **Tablet**: Sidebar as collapsible overlay. Stats cards 2×2 grid.
- **Desktop**: Sidebar fixed. Stats cards 4-column. Charts side-by-side.
