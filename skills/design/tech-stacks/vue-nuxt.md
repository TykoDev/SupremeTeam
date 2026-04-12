# TECH STACK OVERLAY: Vue 3 + Nuxt 3 Frontend

Applies to: Enterprise web apps, SEO-driven sites, progressive web applications
Runtime: Vite 8 | Nuxt 3.14+ | Vue 3.5

---

## Runtime and Execution Model

- **Framework**: Vue 3.5 with Composition API (`<script setup lang="ts">`)
- **Meta-framework**: Nuxt 3.14+ for SSR, file-based routing, auto-imports
- **Build tool**: Vite 8
- **Server engine**: Nitro (Nuxt's server engine) — universal deployment

---

## Framework Conventions

### Vue 3 Component Standard

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';

const props = defineProps<{ title: string }>();
const count = ref(0);
const doubled = computed(() => count.value * 2);
</script>

<template>
  <div>
    <h2>{{ props.title }}</h2>
    <p>Count: {{ count }} (doubled: {{ doubled }})</p>
    <button @click="count++">Increment</button>
  </div>
</template>
```

### Nuxt Project Structure

```
project-root/
├── app/
│   ├── components/         # Auto-imported components
│   │   ├── ui/
│   │   └── features/
│   ├── composables/        # Auto-imported composables (use* prefix)
│   ├── layouts/            # Layout components
│   ├── pages/              # File-based routing
│   │   ├── index.vue
│   │   ├── about.vue
│   │   └── users/
│   │       ├── index.vue
│   │       └── [id].vue
│   ├── middleware/
│   ├── plugins/
│   └── app.vue
├── server/
│   ├── api/                # Server API routes
│   ├── middleware/
│   └── utils/
├── shared/                 # Shared between Vue and Nitro (Nuxt 3.14+)
│   └── utils/
│       └── validators.ts
├── stores/                 # Pinia state stores
├── public/
├── nuxt.config.ts
├── package.json
└── tsconfig.json
```

---

## State Management

- **Official**: Pinia — setup stores for Composition API projects
- **Server state**: `useFetch` / `useAsyncData` (Nuxt built-in) or TanStack Query Vue
- **Composables**: `use` prefix convention; independent instances per consumer
- **Rule**: For shared state across components, use Pinia (not composables)

### Pinia Setup Store Pattern

```typescript
// stores/auth.ts
import { defineStore } from 'pinia';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const isAuthenticated = computed(() => !!user.value);

  async function login(credentials: LoginInput) { /* ... */ }
  function logout() { user.value = null; }

  return { user, isAuthenticated, login, logout };
});
```

---

## Data Contracts and Validation

- **Runtime validation**: Zod via VeeValidate + `@vee-validate/zod`
- **Full-stack schemas**: Placed in `shared/utils/validators.ts` for use in Vue and Nitro
- **Form handling**: VeeValidate for form state and validation
- **Naming**: PascalCase with descriptive prefixes for components

---

## Auto-Imports (Nuxt)

Nuxt auto-imports from these directories:
- `components/` — Vue components
- `composables/` — Composable functions
- `utils/` — Utility functions
- `server/utils/` — Server utilities

---

## Performance

- **SSR**: Nuxt handles server-side rendering by default
- **Hydration**: Automatic hydration with minimal client JS
- **Lazy loading**: Dynamic imports via `defineAsyncComponent`
- **Build**: Vite 8 with Rolldown for fast builds

---

## Build and Deployment

- **Package manager**: pnpm
- **Build**: `nuxt build` for production; `nuxt generate` for static
- **Linter/formatter**: Biome 2.0 or ESLint with `@nuxt/eslint`
- **Deployment**: Nitro supports Node, Deno, Cloudflare, Vercel, Netlify, AWS Lambda
