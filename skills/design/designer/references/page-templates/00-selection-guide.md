# Page Templates — Selection Guide

> **Purpose**: Master index for selecting page layout templates. The designer
> SKILL.md instructs the agent to consult this file when choosing structural
> templates for a project, then read the individual template files for detail.

---

## Template Selection Guide

| Project Type | Primary Template(s) | Secondary Template(s) | Notes |
|-------------|-------------------|---------------------|-------|
| **SaaS Product** | `02-saas-product` + `04-admin-dashboard` + `09-pricing` | `10-authentication`, `11-settings`, `12-data-table` | Full SaaS = 5–6 templates |
| **Marketing Website** | `01-marketing-landing` | `07-blog` for content marketing | Single template for simple sites |
| **E-commerce** | `06-ecommerce-product` + `12-data-table` (admin) | `04-admin-dashboard`, `01-marketing-landing` | Product + admin + marketing |
| **Admin Panel** | `04-admin-dashboard` + `12-data-table` + `11-settings` | `10-authentication` | Core admin = 3–4 templates |
| **Documentation** | `03-documentation` | `01-marketing-landing` for docs homepage | Docs homepage = landing template |
| **Portfolio** | `08-portfolio` | `07-blog` if including blog | Simple sites use just `08-portfolio` |
| **Social Platform** | `04-admin-dashboard` + `13-chat` + `12-data-table` | `10-authentication`, `11-settings` | Complex; 4–5 templates |
| **Internal Tool** | `04-admin-dashboard` + `12-data-table` | `10-authentication` | Simplest admin version |
| **Booking/Scheduling** | `15-calendar` + `10-authentication` | `04-admin-dashboard`, `12-data-table` | Add dashboard for management |
| **Developer Platform** | `03-documentation` + `04-admin-dashboard` + `05-analytics` | `02-saas-product`, `09-pricing` | Docs + dashboard + analytics |

---

## Template Combinations for Complex Projects

### Full SaaS Application

```
Authentication Flow: 10-authentication → 10-authentication → 10-authentication
├── Onboarding: 16-multi-step-wizard
│   └── Dashboard: 04-admin-dashboard
│       ├── Users Management: 12-data-table
│       ├── Billing: 09-pricing
│       ├── Settings: 11-settings
│       └── Profile: 11-settings > Profile
├── Public Pages:
│   ├── Landing: 01-marketing-landing
│   ├── Pricing: 09-pricing
│   ├── Documentation: 03-documentation
│   ├── Blog: 07-blog
│   └── Status Pages: 17-error-pages
└── Transactional Emails: 18-email-template
```

### E-commerce Platform

```
Customer Flow:
├── Homepage: 01-marketing-landing
├── Product: 06-ecommerce-product
├── Cart: 12-data-table (list-like)
├── Checkout: 16-multi-step-wizard
├── Confirmation: 18-email-template
└── Account: 11-settings + 12-data-table (order history)

Admin Flow:
├── Dashboard: 04-admin-dashboard
├── Products: 12-data-table
├── Orders: 12-data-table
├── Customers: 12-data-table
└── Settings: 11-settings
```

### Developer Platform / API Product

```
Public:
├── Landing: 02-saas-product
├── Pricing: 09-pricing
├── Documentation: 03-documentation
└── Blog: 07-blog

Authenticated:
├── Auth: 10-authentication
├── Dashboard: 05-analytics
├── API Keys: 12-data-table + Create Modal
├── Usage: 05-analytics
└── Settings: 11-settings
```

---

## Template Index

| # | Template | File | Primary Use |
|---|----------|------|-------------|
| 01 | Marketing Landing Page | `01-marketing-landing.md` | Conversion pages, campaigns |
| 02 | SaaS Product Page | `02-saas-product.md` | Software product showcase |
| 03 | Documentation Site | `03-documentation.md` | Technical docs, API references |
| 04 | Admin Dashboard | `04-admin-dashboard.md` | Back-office management |
| 05 | Analytics Dashboard | `05-analytics.md` | Data visualization, KPIs |
| 06 | E-commerce Product | `06-ecommerce-product.md` | Product display pages |
| 07 | Blog / Content Site | `07-blog.md` | Articles, tutorials, news |
| 08 | Portfolio / Personal | `08-portfolio.md` | Personal brand, freelancer |
| 09 | SaaS Pricing | `09-pricing.md` | Plan comparison, conversion |
| 10 | Authentication Pages | `10-authentication.md` | Login, signup, reset |
| 11 | Settings Page | `11-settings.md` | User/app configuration |
| 12 | Data Table / CRUD | `12-data-table.md` | Record management |
| 13 | Chat / Messaging | `13-chat.md` | Real-time communication |
| 14 | File Manager | `14-file-manager.md` | File/media browsing |
| 15 | Calendar / Scheduling | `15-calendar.md` | Events, booking |
| 16 | Multi-Step Wizard | `16-multi-step-wizard.md` | Complex data collection |
| 17 | Error / Status Pages | `17-error-pages.md` | 404, 500, maintenance |
| 18 | Email Template | `18-email-template.md` | Transactional emails |

---

## Template Customization Rules

| Element | Customizable | Not Customizable |
|---------|-------------|-----------------|
| Content (text, images) | Fully | N/A |
| Colors (via design tokens) | Fully | N/A |
| Typography (via design tokens) | Fully | N/A |
| Number of sections | Add/remove based on needs | Core sections maintained |
| Section order | Adjust for user flow | Hero before features, CTA at end |
| Layout grid (columns) | Adjust breakpoints and counts | Mobile-first approach required |
| Responsive breakpoints | Adjust for specific content | Must support mobile, tablet, desktop |
| Component library | Choose per project requirements | Must follow accessibility standards |
