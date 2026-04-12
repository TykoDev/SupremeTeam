# TECH STACK OVERLAY: Svelte 5 + SvelteKit

Applies to: Modern web apps, progressive enhancement, performance-critical UIs
Runtime: Vite | SvelteKit | Svelte 5 Runes

---

## Runtime and Execution Model

- **Framework**: Svelte 5 with Runes (fine-grained reactivity via `$state`, `$derived`, `$effect`)
- **Meta-framework**: SvelteKit — file-based routing, SSR, API routes, adapters
- **Build tool**: Vite-based
- **Rendering**: SSR by default; client hydration; static generation via `@sveltejs/adapter-static`

---

## Svelte 5 Runes

```svelte
<script lang="ts">
  let count = $state(0);
  let doubled = $derived(count * 2);

  $effect(() => {
    console.log(`Count changed to ${count}`);
  });

  function increment() {
    count++;
  }
</script>

<button onclick={increment}>
  Count: {count} (doubled: {doubled})
</button>
```

---

## Project Structure

```
project-root/
├── src/
│   ├── routes/                 # File-based routing
│   │   ├── +layout.svelte      # Root layout
│   │   ├── +page.svelte        # Home page
│   │   ├── +page.server.ts     # Server-side load function
│   │   ├── about/
│   │   │   └── +page.svelte
│   │   ├── users/
│   │   │   ├── +page.svelte
│   │   │   ├── +page.server.ts
│   │   │   └── [id]/
│   │   │       ├── +page.svelte
│   │   │       └── +page.server.ts
│   │   └── api/
│   │       └── users/
│   │           └── +server.ts   # API endpoint
│   ├── lib/
│   │   ├── components/
│   │   ├── stores/
│   │   ├── schemas/
│   │   └── utils/
│   └── app.html
├── static/
├── svelte.config.js
├── vite.config.ts
├── package.json
└── tsconfig.json
```

---

## Data Loading

```typescript
// routes/users/+page.server.ts
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
  const users = await fetch('/api/users').then(r => r.json());
  return { users };
};
```

---

## State Management

- **Component state**: `$state` rune (replaces `let` reactive declarations)
- **Derived state**: `$derived` rune (replaces `$:` reactive statements)
- **Effects**: `$effect` rune for side effects
- **Shared state**: Svelte stores (`writable`, `readable`, `derived`) in `$lib/stores/`

---

## Data Contracts and Validation

- **Runtime validation**: Zod for schema validation
- **Form handling**: `superforms` library with Zod integration
- **Server validation**: Validate in `+page.server.ts` load/action functions
- **Type safety**: Full TypeScript support with generated route types (`$types`)

---

## Build and Deployment

- **Package manager**: pnpm
- **Build**: `vite build`
- **Adapters**: `@sveltejs/adapter-node`, `adapter-cloudflare`, `adapter-static`, etc.
- **Testing**: Vitest for unit; Playwright for E2E
- **Linter**: ESLint with `eslint-plugin-svelte`
