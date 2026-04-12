# Template 16: Multi-Step Form / Wizard

**Scope**: Multi-step data collection (onboarding, checkout, configuration).

---

## Section Breakdown

```
┌──────────────────────────────────────────────┐
│ PROGRESS INDICATOR                           │
│ ① ─────── ② ─────── ③ ─────── ④            │
│ Account   Personal   Preferences   Review    │
├──────────────────────────────────────────────┤
│  STEP 2: Personal Information                │
│  First Name:  [________________]             │
│  Last Name:   [________________]             │
│  Email:       [________________]             │
│  Address:     [________________]             │
│  Country:     [Select ▾]                     │
├──────────────────────────────────────────────┤
│              [← Back]  [Continue →]          │
│         [Save as Draft]                      │
└──────────────────────────────────────────────┘
```

## Standards

- Progress indicator: Step counter OR progress bar (%age)
- Step validation: Validate current step before forward nav
- Navigation: Back/Next, skip optional, save as draft
- Review step: Summary of all data before final submit
- Confirmation: Clear success message with next steps
- Mobile: Full-width form, progress at top
