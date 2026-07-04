# PMOVES.AI — Public Landing Page

Static HTML/CSS/vanilla-JS landing page for `https://pmoves.ai`.
No build step. No framework. Drag-and-droppable to Cloudflare Pages.

## What's in here

```
website/
├── index.html         # Single-page landing — all sections live here
├── styles.css         # Dark-first theme, AA contrast, mobile-first
├── main.js            # Nav drawer, smooth scroll, lazy-load hook
├── _headers           # Cloudflare Pages security headers (CSP/HSTS/Frame)
├── _redirects         # /demo/* placeholders + social shortlinks
├── robots.txt         # Allow all + LLM-crawler-friendly
├── sitemap.xml        # Root index only for now
├── README.md          # This file
└── assets/            # Favicons + README with asset spec
    ├── favicon.svg
    └── README.md
```

Uncompressed total is under ~50 KB. Gzipped is under ~15 KB.

## Tagline decision

We ship with **"It's been a good run, ISPs."** as the hero headline.

Reasons this won over the alternatives:

- **Memorable.** Fits a tweet, a shirt, a sticker, a LinkedIn headline.
  The other two are explanatory; this one is a stance.
- **Press-friendly.** Every reporter covering mesh / disaster-response
  infra will quote that line verbatim. You can't buy that on adspend.
- **Community-legible.** The Bronx co-op audience and the UN/NGO
  audience both hear it and nod — one group because of cable bills,
  the other because of field-office uptime.
- **Mission pairs cleanly.** The subhead carries the "zero-retention +
  voice-through-walls" load without needing the headline to explain it.

The two runners-up live inside the copy anyway:

- *"Zero-retention AI. Community-owned infrastructure. Voice that goes
  through walls."* — reused in the meta description / Twitter card.
- *"The AI that forgets — by design."* — earmarked for a future
  section-head on /security once that page ships.

Swap is trivial if you change your mind: edit the `<h1>` in
`index.html` and the meta tags at the top. Two edits.

## Deploy — Cloudflare Pages

You have two paths. Both work. Pick one.

### Path A — Pages dashboard (drag-and-drop; fastest for first ship)

1. Log in to **https://dash.cloudflare.com** → your account → **Workers & Pages**.
2. Click **Create → Pages → Upload assets**.
3. Project name: `pmoves-ai` (or whatever you want your `*.pages.dev` URL to be).
4. Drag the entire `website/` folder contents into the drop zone.
   Cloudflare will pick up `index.html` as the root automatically.
5. Click **Deploy site**. First deploy takes ~30 seconds.
6. When it's live at `pmoves-ai.pages.dev`, go to **Custom domains**
   and add `pmoves.ai` + `www.pmoves.ai`. Cloudflare will set DNS
   automatically if the zone lives in the same account.

Re-deploy on future changes by clicking **Create new deployment** and
dragging the updated folder again. Or — better — wire up Path B below.

### Path B — Wrangler CLI + Git (recommended for ongoing work)

One-time setup:

```bash
# Install wrangler (already authed if you've used it before)
npm install -g wrangler
wrangler login
```

Deploy straight from the repo root:

```bash
# From the repo root, NOT from inside website/
wrangler pages deploy website --project-name pmoves-ai --branch main
```

Or set up Git-connected deploys (after the first manual deploy exists):

1. Cloudflare dashboard → your `pmoves-ai` project → **Settings → Builds & deployments → Git**.
2. Connect the `POWERFULMOVES/PMOVES.AI` repository.
3. Configure:
   - **Production branch:** `main`
   - **Build command:** *leave blank*
   - **Build output directory:** `website`
4. Save. Every push to `main` now triggers an auto-deploy. Preview
   deployments are generated automatically for every PR.

### Path C — Cloudflare Workers (only if you ever need dynamic routes)

You don't need this for the landing page. Noted for later: if a
`/demo/*` route grows into a real backend, bind a Worker with a
`_routes.json` file and deploy alongside. For now, static is king.

## Local preview

```bash
# From repo root
cd website
python -m http.server 8000
# then open http://localhost:8000
```

Or, if you have Wrangler installed:

```bash
wrangler pages dev website
```

Wrangler's dev server also honors `_headers` and `_redirects`, which
plain `python -m http.server` does not — use Wrangler when testing
those files.

## How to update content

All copy lives in `index.html`. Sections are clearly delimited with
`<!-- ========= SECTION NAME ========= -->` comments.

- **Tagline:** line with `<h1 id="hero-title">` — change the text and
  the `<title>` + `og:title` + `twitter:title` meta tags above.
- **CTAs:** search for `mailto:` — every email target is explicit and
  independent (enterprise@, community@, response@, etc). Change once.
- **YouTube playlist:** search for `PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8`
  and replace if the playlist URL changes.
- **Demo dates:** search for `Coming Q2 2026` / `Coming Q3 2026` and
  update when real endpoints ship.
- **Colors / fonts:** `:root` block at the top of `styles.css`.

## Gaps the founder still needs to fill

- [ ] `/og-image.png` at `website/og-image.png` — 1200x630 PNG, dark
      background, PMOVES logo + tagline. Social preview will look
      broken without it.
- [ ] `/assets/favicon.ico` and `/assets/apple-touch-icon.png` —
      generate from the real logo (svg favicon stub is shipped).
- [ ] Real Discord invite URL — replace `/discord` target in
      `_redirects` and the footer link in `index.html`.
- [ ] LinkedIn company page URL — currently a best-guess slug in footer.
- [ ] X handle verified — currently points to `@DARKXSIDE` in meta tags.
- [ ] Decide if `enterprise@pmoves.ai`, `community@pmoves.ai`,
      `response@pmoves.ai`, `tour@pmoves.ai`, `press@pmoves.ai`, and
      `hello@pmoves.ai` should all resolve — or consolidate to
      `hello@` + routing rules in your mail provider.
- [ ] Real `/privacy.html`, `/terms.html`, `/security.html` pages.
      Currently the `_redirects` file points those slugs at anchor
      sections as a defensive fallback.
- [ ] Enable **Cloudflare Web Analytics** on the project (free, no
      cookies, no third-party). Uncomment the beacon section in
      `index.html` and add the host to the CSP in `_headers`.
- [ ] A real `<img>` for the mobile-node section once the rig is built
      — drop it in `assets/` and replace the inline SVG schematic.

## Accessibility notes

- Skip link first-focusable. `main` has `tabindex="-1"` so the skip
  link target takes focus cleanly.
- Every color combination hits WCAG AA contrast on `#0b0b10` ground.
- `prefers-reduced-motion: reduce` disables all transitions and the
  smooth-scroll behavior.
- Heading order is strict (single `<h1>`, `<h2>` per section, `<h3>`
  for cards). Don't let future edits break that.
- Nav drawer is keyboard-operable: Escape closes, focus returns to the
  toggle button.

## Security headers explained (`_headers`)

- **HSTS 2 years + preload-ready** — once you submit `pmoves.ai` to
  the HSTS preload list, this header qualifies.
- **CSP** — `default-src 'self'` with explicit YouTube frame allowance.
  No inline JS or inline CSS is used by the page, so no `unsafe-inline`
  is needed. When you wire Cloudflare Web Analytics, add
  `https://static.cloudflareinsights.com` to `script-src`.
- **Permissions-Policy** — Microphone is granted (for the future voice
  demo). Camera, geolocation, payment are all denied by default.
- **X-Frame-Options: DENY** — the site cannot be iframed. Pair with
  `frame-ancestors 'none'` in CSP for layered defense.

If Lighthouse or `securityheaders.com` complains after deploy, the
likely cause is a CDN/proxy stripping headers — check that
`_headers` actually shipped by `curl -I https://pmoves.ai`.

## Performance targets

- Lighthouse Performance ≥ 95
- Lighthouse Accessibility ≥ 95
- Lighthouse Best Practices ≥ 95
- Lighthouse SEO ≥ 95
- Total payload on first visit (uncached): under 50 KB over the wire.

If you add hero images or a background video later, lazy-load them
through the `data-src` hook already wired in `main.js`.

---

Built by Cataclysm Studios Inc. Community-owned infrastructure.
