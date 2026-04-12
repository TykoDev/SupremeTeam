# TECH STACK OVERLAY: Angular 19+ Frontend

Applies to: Enterprise SPAs, complex LOB applications, large team codebases
Runtime: Angular CLI | Angular 19+ | Standalone Components

---

## Runtime and Execution Model

- **Framework**: Angular 19+ — standalone components by default, signals-based reactivity
- **Build tool**: Angular CLI with esbuild (default) or Webpack (legacy)
- **Language**: TypeScript strict mode (enforced by Angular)
- **Rendering**: CSR default; SSR via `@angular/ssr` with hydration

---

## Framework Conventions

### Standalone Components (Default in Angular 19+)

```typescript
import { Component, signal, computed, input, output } from '@angular/core';

@Component({
  selector: 'app-counter',
  template: `
    @if (count() > 0) {
      <p>Count: {{ count() }} (doubled: {{ doubled() }})</p>
    }
    <button (click)="increment()">Increment</button>
  `,
})
export class CounterComponent {
  count = signal(0);
  doubled = computed(() => this.count() * 2);
  label = input<string>('Counter');      // Signal-based input
  changed = output<number>();            // Signal-based output

  increment() {
    this.count.update(c => c + 1);
    this.changed.emit(this.count());
  }
}
```

### Project Structure (Feature-Based)

```
src/
├── app/
│   ├── core/                    # Singletons: auth interceptors, global error handlers
│   │   ├── interceptors/
│   │   ├── guards/
│   │   └── services/
│   ├── shared/                  # Reusable components, pipes, directives
│   │   ├── components/
│   │   ├── pipes/
│   │   └── directives/
│   ├── features/                # Feature-specific, lazy-loaded modules
│   │   ├── dashboard/
│   │   │   ├── dashboard.component.ts
│   │   │   ├── dashboard.routes.ts
│   │   │   ├── services/
│   │   │   └── models/
│   │   ├── users/
│   │   └── settings/
│   ├── app.component.ts
│   ├── app.config.ts
│   └── app.routes.ts
├── environments/
├── assets/
├── styles/
├── angular.json
├── package.json
└── tsconfig.json
```

---

## Reactivity: Angular Signals

- **`signal()`**: Writable reactive value
- **`computed()`**: Derived reactive value (read-only)
- **`effect()`**: Side effect triggered by signal changes
- **`input()`**: Signal-based component inputs (replaces `@Input()`)
- **`output()`**: Signal-based component outputs (replaces `@Output()`)
- **`model()`**: Two-way binding signal

### NgRx SignalStore (Replaces Traditional NgRx Store)

```typescript
import { signalStore, withState, withComputed, withMethods } from '@ngrx/signals';

export const UsersStore = signalStore(
  withState({ users: [] as User[], loading: false }),
  withComputed(({ users }) => ({
    activeUsers: computed(() => users().filter(u => u.active)),
    userCount: computed(() => users().length),
  })),
  withMethods(({ users, ...store }) => ({
    async loadUsers() {
      patchState(store, { loading: true });
      const result = await inject(UserService).getAll();
      patchState(store, { users: result, loading: false });
    },
  })),
);
```

---

## New Control Flow Syntax

```html
<!-- Replaces *ngIf, *ngFor, *ngSwitch -->
@if (user()) {
  <p>Welcome, {{ user().name }}</p>
} @else {
  <p>Please log in</p>
}

@for (item of items(); track item.id) {
  <app-item [data]="item" />
} @empty {
  <p>No items found</p>
}

@defer (on viewport) {
  <app-heavy-chart />
} @placeholder {
  <p>Loading chart...</p>
}
```

- **Performance**: ~30KB bundle reduction, ~90% faster rendering vs structural directives
- **`@defer`**: Declarative lazy loading with triggers (`on viewport`, `on idle`, `on interaction`)

---

## Data Contracts and Validation

- **Forms**: Reactive Forms with typed `FormGroup` / `FormControl`
- **Validation**: Built-in validators + custom validator functions
- **HTTP**: `HttpClient` with typed request/response
- **Interceptors**: Functional interceptors for auth tokens, error handling

---

## Build and Deployment

- **Package manager**: pnpm or npm
- **Build**: Angular CLI with esbuild (fast dev builds)
- **Linter**: ESLint with `@angular-eslint`
- **Testing**: Karma/Jasmine (default) or Jest; Playwright for E2E
- **Deployment**: Any static host (SSR requires Node.js server)
