# Template 07: Blog / Content Site

**Scope**: Content-heavy site for articles, tutorials, or news.

---

## Homepage Structure

```
┌──────────────────────────────────────────────┐
│ NAVBAR (sticky)                               │
│ [Logo] [Topics] [About] [Search] [Subscribe] │
├──────────────────────────────────────────────┤
│ FEATURED ARTICLE (hero card)                  │
│ Large image + title + excerpt + author + date │
├──────────────────────────────────────────────┤
│ TOPIC TABS: [All] [Tech] [Design] [AI]       │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │ Article │ │ Article │ │ Article │        │
│ │ Card    │ │ Card    │ │ Card    │        │
│ └─────────┘ └─────────┘ └─────────┘        │
│ [Load More Articles]                          │
├──────────────────────────────────────────────┤
│ NEWSLETTER SIGNUP                             │
│ [Email input] [Subscribe button]              │
├──────────────────────────────────────────────┤
│ FOOTER                                       │
└──────────────────────────────────────────────┘
```

## Article Page Structure

- Centered prose column (max-width: 65ch / ~720px)
- Article header: title, author (avatar + name), date, reading time, badge
- Cover image (full-width within prose column)
- Article body with rich typography
- Table of contents (sticky sidebar on desktop)
- Author bio card at bottom
- Related articles (3 cards)

## Article Card Design

- Thumbnail image (16:9 aspect ratio)
- Topic badge (overlaid on image)
- Title (2–3 lines, line-clamped)
- Excerpt (2–3 lines, line-clamped)
- Author name + date (muted, small)
- Reading time estimate
