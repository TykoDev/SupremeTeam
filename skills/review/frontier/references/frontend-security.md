# Frontend Security — CSP, Trusted Types, SRI & DOM Security

## Content Security Policy (CSP) Evaluation

### CSP Header Analysis

Evaluate the application's CSP configuration against these criteria:

| Directive | Best Practice | Severity if Missing/Weak |
|-----------|--------------|-------------------------|
| `default-src` | `'none'` or `'self'` | Major — permissive default allows all content types |
| `script-src` | `'self'` with nonces or hashes | Critical — must not include `'unsafe-inline'` or `'unsafe-eval'` |
| `style-src` | `'self'` or `'self' 'unsafe-inline'` (styles are lower risk) | Medium |
| `img-src` | `'self' data:` plus allowed CDN origins | Low |
| `connect-src` | `'self'` plus API origins | Medium — controls fetch/XHR destinations |
| `font-src` | `'self'` plus font CDN origins | Low |
| `object-src` | `'none'` | Major — blocks Flash, Java, ActiveX |
| `base-uri` | `'self'` or `'none'` | Medium — prevents base tag injection |
| `form-action` | `'self'` | Medium — prevents form hijacking |
| `frame-ancestors` | `'self'` or `'none'` | Medium — prevents clickjacking (replaces X-Frame-Options) |
| `frame-src` | Specific origins only | Medium |
| `worker-src` | `'self'` | Medium |
| `upgrade-insecure-requests` | Present | Minor — automatically upgrades HTTP to HTTPS |
| `require-trusted-types-for` | `'script'` | Major — enables Trusted Types enforcement |

### CSP Anti-Patterns

| Anti-Pattern | Risk | Detection |
|-------------|------|-----------|
| `script-src 'unsafe-inline'` | Critical — defeats XSS protection | Search for CSP headers/meta tags |
| `script-src 'unsafe-eval'` | Critical — enables eval-based attacks | Search for CSP headers/meta tags |
| `default-src *` | Critical — allows everything | Search for CSP headers/meta tags |
| `script-src *` | Critical — allows any script source | Search for CSP headers/meta tags |
| Overly broad whitelists | High — large allowlists can include attacker-controlled origins | Review CSP source lists |
| No CSP at all | Major — no defense-in-depth against XSS | Check response headers |
| CSP in `<meta>` only | Medium — can be bypassed if attacker can inject before meta tag | Check header vs meta placement |

### Nonce-Based CSP Implementation

```html
<!-- Server generates unique nonce per request -->
<script nonce="random-base64-value">
  // Inline script with nonce
</script>

<!-- CSP header includes the nonce -->
Content-Security-Policy: script-src 'nonce-random-base64-value' 'strict-dynamic';
```

**Verification checklist:**
- [ ] Nonce is cryptographically random (at least 128 bits of entropy)
- [ ] Nonce is unique per HTTP response (never reused)
- [ ] Nonce is not predictable or derivable
- [ ] `strict-dynamic` keyword is used to propagate trust to dynamically loaded scripts
- [ ] Nonce is not included in any cached response

---

## Trusted Types Enforcement

### What Are Trusted Types?

Trusted Types prevent DOM XSS by forcing all assignments to dangerous DOM
sinks through a validation policy. When enabled, raw strings cannot be assigned
to sinks like `innerHTML` — they must first be wrapped in a Trusted Type.

### Enforcement via CSP

```
Content-Security-Policy: require-trusted-types-for 'script';
                         trusted-types my-policy;
```

### Dangerous DOM Sinks (Require Trusted Types)

| Sink | Risk |
|------|------|
| `element.innerHTML` | HTML injection |
| `element.outerHTML` | HTML injection |
| `document.write()` | HTML injection |
| `document.writeln()` | HTML injection |
| `element.insertAdjacentHTML()` | HTML injection |
| `DOMParser.parseFromString()` | HTML injection |
| `setTimeout(string)` | JavaScript execution |
| `setInterval(string)` | JavaScript execution |
| `eval(string)` | JavaScript execution |
| `new Function(string)` | JavaScript execution |
| `element.src` (script) | Script loading |
| `element.href` (with `javascript:`) | JavaScript execution |
| `location.href`, `location.assign()` | Navigation, potential XSS |

### Code Review Checks

- [ ] Application code does not use dangerous sinks with user-controlled data
- [ ] If sinks are used, data is sanitized through DOMPurify or equivalent
- [ ] Trusted Types policies are created with descriptive names
- [ ] Policies validate and sanitize input before creating Trusted Type objects
- [ ] Default policy (fallback) logs violations but passes through sanitized content

---

## DOM-Based XSS Detection

### Source-to-Sink Tracing

Trace data flow from **sources** (where untrusted data enters) to **sinks** (where data is rendered or executed):

**Sources (untrusted data origins):**
- `window.location` (`.hash`, `.search`, `.pathname`, `.href`)
- `document.referrer`
- `document.cookie`
- `window.name`
- `postMessage` data
- `Web Storage` (localStorage, sessionStorage — if populated with untrusted data)
- URL parameters via framework routers
- API response data containing user-generated content

**Sinks (dangerous execution points):**
- HTML context: `innerHTML`, `outerHTML`, `document.write()`
- JavaScript context: `eval()`, `setTimeout(string)`, `new Function()`
- URL context: `location.href`, `location.assign()`, `window.open()`
- CSS context: `element.style.cssText`

### postMessage Security

```javascript
// VULNERABLE — no origin check
window.addEventListener('message', (event) => {
  document.getElementById('output').innerHTML = event.data;
});

// SECURE — origin validation + content sanitization
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://trusted-origin.example.com') return;
  const sanitized = DOMPurify.sanitize(event.data);
  document.getElementById('output').textContent = sanitized;
});
```

**Verification checklist:**
- [ ] All `message` event handlers validate `event.origin`
- [ ] Received data is sanitized before DOM insertion
- [ ] `postMessage` calls specify exact target origin (not `*`)

---

## Subresource Integrity (SRI)

### When SRI is Required

SRI is required for all scripts and stylesheets loaded from external origins
(CDNs, third-party services). It verifies that fetched resources haven't been
tampered with.

```html
<!-- Correct SRI implementation -->
<script
  src="https://cdn.example.com/lib/v3.2.1/lib.min.js"
  integrity="sha384-abc123..."
  crossorigin="anonymous">
</script>

<link
  rel="stylesheet"
  href="https://cdn.example.com/css/v2.0/style.css"
  integrity="sha384-def456..."
  crossorigin="anonymous">
```

### SRI Checklist

- [ ] All CDN-loaded `<script>` tags include `integrity` attribute
- [ ] All CDN-loaded `<link rel="stylesheet">` tags include `integrity` attribute
- [ ] Integrity hashes use SHA-384 or SHA-512 (not SHA-256 alone)
- [ ] `crossorigin="anonymous"` attribute is present
- [ ] Build pipeline generates SRI hashes automatically (webpack SriPlugin, Rspack)
- [ ] SRI hashes are updated when CDN resource versions change

---

## Prototype Pollution Prevention

### Detection

Search for vulnerable patterns in code:

```javascript
// Deep merge without prototype checks
function merge(target, source) {
  for (const key in source) {
    if (typeof source[key] === 'object' && source[key] !== null) {
      target[key] = merge(target[key] || {}, source[key]);
    } else {
      target[key] = source[key];
    }
  }
}

// Object.assign with user-controlled source
Object.assign(config, JSON.parse(userInput));

// Lodash/underscore deep merge with untrusted input
_.merge(defaults, userProvidedOptions);
_.defaultsDeep(config, userConfig);
```

### Prevention Checklist

- [ ] Deep merge functions check for `__proto__`, `constructor`, `prototype` keys
- [ ] User-controlled JSON is not directly merged into application objects
- [ ] `Object.create(null)` used for lookup maps (no prototype chain)
- [ ] `Object.freeze(Object.prototype)` considered for critical applications
- [ ] Libraries with known prototype pollution CVEs are updated

---

## Cookie Security Attributes

| Attribute | Required Value | Purpose |
|-----------|---------------|---------|
| `HttpOnly` | `true` | Prevents JavaScript access to cookie (XSS mitigation) |
| `Secure` | `true` | Cookie sent only over HTTPS |
| `SameSite` | `Strict` or `Lax` | CSRF mitigation (Strict preferred for auth cookies) |
| `Path` | Narrowest applicable path | Limits cookie scope |
| `Domain` | Most specific domain | Prevents subdomain leakage |
| `Max-Age` / `Expires` | Reasonable expiration | Limits exposure window |

### Code Review Checks

- [ ] Session cookies set `HttpOnly`, `Secure`, and `SameSite` attributes
- [ ] Authentication tokens are not stored in `localStorage` (prefer `HttpOnly` cookies)
- [ ] Cookie configuration is consistent across the application
- [ ] Sensitive cookies have appropriate expiration (not permanent)

---

## Security Headers Checklist

| Header | Expected Value | Severity if Missing |
|--------|---------------|--------------------|
| `Content-Security-Policy` | See CSP section above | Major |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Major |
| `X-Content-Type-Options` | `nosniff` | Medium |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` | Medium (superseded by CSP frame-ancestors) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` or `no-referrer` | Minor |
| `Permissions-Policy` | Restrict unused features (camera, microphone, geolocation) | Minor |
| `Cross-Origin-Opener-Policy` | `same-origin` | Medium |
| `Cross-Origin-Resource-Policy` | `same-origin` or `same-site` | Minor |
| `Cross-Origin-Embedder-Policy` | `require-corp` (if SharedArrayBuffer needed) | Minor |

---

## CORS Configuration

### Vulnerable Patterns

```javascript
// VULNERABLE — reflects any origin
app.use(cors({ origin: true }));
app.use(cors({ origin: '*' }));
app.use(cors({ origin: req.headers.origin })); // Reflection attack

// VULNERABLE — null origin allowed
app.use(cors({ origin: ['null'] }));
```

### Secure Pattern

```javascript
const ALLOWED_ORIGINS = [
  'https://app.example.com',
  'https://admin.example.com'
];

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || ALLOWED_ORIGINS.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
```

### CORS Checklist

- [ ] Origin is validated against an allowlist (not reflected or wildcarded with credentials)
- [ ] `Access-Control-Allow-Credentials: true` is not used with `Access-Control-Allow-Origin: *`
- [ ] Allowed methods are restricted to those actually needed
- [ ] Preflight caching (`Access-Control-Max-Age`) is set appropriately
- [ ] Sensitive endpoints restrict CORS to specific origins
