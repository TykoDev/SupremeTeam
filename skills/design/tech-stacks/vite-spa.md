# TECH STACK OVERLAY: Vite 8 SPA Baseline (React/Vue)

Applies to: Single-page applications, client-rendered dashboards, internal tools
Runtime: Vite 8 | React or Vue | Client-Side Rendering

---

## Runtime and Execution Model

- **Build tool**: Vite 8 with Rolldown (Rust-based bundler, 10-30× faster than Webpack)
- **UI Library**: React 19 or Vue 3.5 (framework-agnostic baseline)
- **Rendering**: Client-side rendering (CSR) — no SSR
- **Dev server**: Native ESM-based dev server with instant HMR

---

## Project Structure

```
project-root/
├── index.html                  # Entry HTML (Vite root)
├── src/
│   ├── main.tsx                # Application entry point
│   ├── App.tsx
│   ├── components/
│   │   ├── ui/                 # Reusable UI primitives
│   │   └── features/           # Feature-specific components
│   ├── pages/                  # Route-level components
│   ├── hooks/ (or composables/)
│   ├── lib/
│   │   ├── api/                # API client functions
│   │   ├── schemas/            # Zod validation schemas
│   │   └── utils/
│   ├── stores/                 # State management
│   └── styles/
│       ├── globals.css
│       └── variables.css
├── public/                     # Static assets (unprocessed)
├── vite.config.ts
├── package.json
├── tsconfig.json
└── biome.json
```

---

## Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';       // or vue()
import checker from 'vite-plugin-checker';

export default defineConfig({
  plugins: [
    react(),     // Uses Oxc Transformer for Fast Refresh
    checker({ typescript: true }),
  ],
  resolve: {
    alias: { '@': '/src' },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
        },
      },
    },
  },
});
```

---

## Environment Variables

- **Client-exposed**: Must use `VITE_` prefix (`VITE_API_URL`, `VITE_APP_TITLE`)
- **Server-only**: No prefix (not exposed to client bundle)
- **Validation**: Validate at app initialization with Zod
- **Files**: `.env`, `.env.local`, `.env.production` (Vite loads by mode)

---

## Essential Plugins

| Plugin | Purpose |
|--------|---------|
| `@vitejs/plugin-react` | React Fast Refresh with Oxc Transformer |
| `@vitejs/plugin-vue` | Vue SFC support |
| `vite-plugin-checker` | TypeScript/ESLint checking in worker thread |
| `rollup-plugin-visualizer` | Bundle size analysis |

---

## State Management

- **Server state**: TanStack Query (React) or VueQuery (Vue)
- **Client state**: Zustand (React) or Pinia (Vue)
- **Router**: React Router or TanStack Router (React) / Vue Router (Vue)

---

## Build and Deployment

- **Package manager**: pnpm
- **Build**: `vite build` — outputs to `dist/`
- **Preview**: `vite preview` for local production preview
- **Hosting**: Any CDN or static host (Cloudflare Pages, Netlify, S3+CloudFront)
- **Bundle analysis**: `npx vite-bundle-visualizer`
