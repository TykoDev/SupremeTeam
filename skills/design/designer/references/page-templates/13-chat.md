# Template 13: Chat / Messaging Interface

**Scope**: Real-time messaging, support chat, team communication.

---

## Section Breakdown

```
┌──────────┬──────────────────────────┬────────┐
│ CONVO    │ MESSAGE AREA             │ INFO   │
│ LIST     │                          │ PANEL  │
│ [Search] │ [Name] [Status] [⋮]     │ Photo  │
│          │─────────────────────────│ Name   │
│ Convo 1  │ Message bubble (rx)     │        │
│ Convo 2  │      Message (tx)      │ Email  │
│ Convo 3  │ Message bubble (rx)     │        │
│          ├──────────────────────────│        │
│          │ [📎] [Input...] [Send]  │        │
└──────────┴──────────────────────────┴────────┘
```

## Responsive Behavior

- **Mobile**: Single panel (list OR chat). Tap to open, back to return.
- **Tablet**: Two panels (list + chat). Info as drawer.
- **Desktop**: Three panels. Info panel collapsible.
