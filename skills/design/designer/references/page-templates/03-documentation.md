# Template 03: Documentation Site

**Scope**: Technical documentation, API references, guides, and tutorials.
Optimized for reading and search.

**Layout Architecture**: Two-panel layout with persistent left sidebar
navigation and scrollable main content area.

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│ TOP BAR                                       │
│ [Logo/Docs]  [Search (Cmd+K)]  [v1.0] [Theme] │
├────────┬─────────────────────────────────────┤
│ LEFT   │ MAIN CONTENT                         │
│ SIDEBAR│                                      │
│        │ Breadcrumb: Docs > Getting Started   │
│ Getting│                                      │
│ Started│ # Page Title (h1)                    │
│ ├ Guide│                                      │
│ ├ Instal│ Page content (prose typography)     │
│ ├ Quick│                                      │
│ │ Start│ [Code blocks with copy button]       │
│ │       │                                      │
│ API    │ [Admonitions: Note, Warning, Info]    │
│ ├ Auth │                                      │
│ ├ Users│ ## Section (h2)                      │
│ │       │                                      │
│        │ [Inline code, links, tables]          │
│        │                                      │
│        │ ── On This Page ──                   │
│        │ (TOC - right sidebar on desktop)     │
│        │                                      │
│        │ ── Prev: Installation ──             │
│        │ ── Next: Configuration ──            │
├────────┴─────────────────────────────────────┤
│ FOOTER (minimal)                             │
└──────────────────────────────────────────────┘
```

---

## Responsive Behavior

- **Mobile**: Sidebar hidden (toggle via hamburger), full-width content, TOC
  hidden
- **Tablet**: Sidebar as overlay drawer, content full width
- **Desktop**: Fixed sidebar (240–280px), content max-width 800px for prose,
  floating TOC on right

## Key Features

- Full-text search with keyboard shortcut (Cmd+K)
- Version switcher in top bar
- Syntax-highlighted code blocks with language label and copy button
- Edit on GitHub link
- Breadcrumb navigation
- In-page table of contents (right sidebar on desktop)
- Prev/Next page navigation links
