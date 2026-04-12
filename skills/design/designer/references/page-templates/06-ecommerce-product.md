# Template 06: E-commerce Product Page

**Scope**: Individual product display page. Optimized for conversion.

**Layout Architecture**: Two-column (images + info) on desktop, stacked on
mobile.

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│ BREADCRUMB: Home > Category > Product Name   │
├────────────────────┬─────────────────────────┤
│ PRODUCT IMAGES     │ PRODUCT INFO             │
│                    │ [Badge: New / Sale]      │
│ [Main Image]       │ Product Name (h1)        │
│                    │ Rating: ★★★★☆ (234)      │
│                    │ Price: $49.99 $39.99      │
│ [Thumbnail strip]  │ Short description        │
│ [1] [2] [3] [4]   │                          │
│                    │ [Color selector]          │
│                    │ [Size selector]           │
│                    │ Quantity: [- 1 +]         │
│                    │                          │
│                    │ [Add to Cart] [Buy Now]   │
│                    │ [Add to Wishlist]         │
│                    │                          │
│                    │ Accordion sections:       │
│                    │ ▸ Description             │
│                    │ ▸ Specifications          │
│                    │ ▸ Shipping & Returns      │
│                    │ ▸ Reviews (234)           │
├────────────────────┴─────────────────────────┤
│ PRODUCT DESCRIPTION (full width)             │
├──────────────────────────────────────────────┤
│ CUSTOMER REVIEWS                             │
│ Rating summary + Review list + Write review  │
├──────────────────────────────────────────────┤
│ RELATED PRODUCTS                             │
│ 4-column product card carousel/grid          │
├──────────────────────────────────────────────┤
│ RECENTLY VIEWED                              │
│ Horizontal scrollable product card row       │
└──────────────────────────────────────────────┘
```

---

## Responsive Behavior

- **Mobile**: Single column, images above info, thumbnail row scrollable,
  sticky "Add to Cart" bar at bottom
- **Tablet**: Two-column layout, smaller image
- **Desktop**: Two-column (60/40 split), sticky product info on scroll
