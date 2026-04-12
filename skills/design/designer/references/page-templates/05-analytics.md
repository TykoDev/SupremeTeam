# Template 05: Analytics Dashboard

**Scope**: Data-heavy dashboard for visualizing metrics, KPIs, and trends.

**Layout Architecture**: Same shell as Template 04 but content area optimized
for data visualization.

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│ HEADER BAR                                   │
│ [Date Range Picker: Last 30 days ▾]          │
│ [Refresh] [Export PDF] [Fullscreen]           │
├──────────────────────────────────────────────┤
│ KPI CARDS ROW (4-5 cards)                     │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        │
│ │Metric│ │Metric│ │Metric│ │Metric│        │
│ │Value │ │Value │ │Value │ │Value │        │
│ │+12% ↑│ │-3% ↓ │ │+8% ↑ │ │0% ──│        │
│ └──────┘ └──────┘ └──────┘ └──────┘        │
├──────────────────────────────────────────────┤
│ PRIMARY CHART (full width)                    │
│ Line/Area chart with multiple data series    │
│ Toggle series, zoom, tooltip                 │
├────────────────────┬─────────────────────────┤
│ SECONDARY CHART 1  │ SECONDARY CHART 2       │
│ Bar chart          │ Donut/Pie chart         │
│ (Breakdown by X)   │ (Distribution)         │
├────────────────────┴─────────────────────────┤
│ DATA TABLE                                  │
│ Sortable, filterable, paginated table        │
├──────────────────────────────────────────────┤
│ OPTIONAL: Filters sidebar (collapsible)      │
└──────────────────────────────────────────────┘
```

---

## Key Design Decisions

- Date range picker always visible (critical for analytics)
- KPI cards show value + trend (percentage change with arrow)
- Primary chart takes full width for maximum data visibility
- Charts use color-blind-safe palettes
- All charts have interactive tooltips with exact values
- Provide "Download as CSV/PDF" for all data sections
- Use skeleton loading for charts during data fetch
