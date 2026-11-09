# PMOVES.AI Website / UI Baseline — 2026-07-14

> **For**: DARKXSIDE (operator sign-off gate) + any agent picking up the Web/UI lane
> **From**: Mavis-5090 (auto-mode lane `feat/auto-20260714-9d8a9584`)
> **Status**: BASELINE COMPLETE — research/diagnostic, **no production code changes shipped**

## TL;DR

The website is in **excellent shape** for what it is — a high-craft static CF Pages site. The two public surfaces (`/`, `/stage/`) render cleanly across desktop / tablet / mobile, the brand voice is on-message, and the DL-4.1 / DL-4.2 work landed well. **No critical bugs found.**

Three things to fix (one is real, two are founder TODOs already on the README):

1. **Color contrast violation** on `index.html` `.card-cta` elements — 10 nodes fail WCAG AA. The README claims AA is met; axe says otherwise. **Real, easy fix.**
2. **Color contrast violation** on `/stage/` `footer > p` — 1 node. Same story.
3. **5 broken internal links** — all are documented placeholders (`/demo/voice`, `/demo/rag`, `/privacy`, `/terms`, `/security`). Not regressions; expected per README §"Gaps the founder still needs to fill."

Bonus: 4 brand assets generated, ready to drop in once you sign off visually.

---

## What was run

| Tool | Skill | Output |
|------|-------|--------|
| `python -m http.server 8765 --bind 127.0.0.1` | (system) | Local server serving `website/` |
| Playwright (Chromium headless) | `playwright` | 6 screenshots + link sweep + a11y audit |
| axe-core 4.10.2 (CDN-injected) | (via playwright) | WCAG 2.0/2.1 AA check |
| `image_synthesize` | `image_synthesize` | 4 brand assets (og-image, favicon, apple-touch-icon, mobile-node rig) |

All artifacts under `pmoves/docs/evidence/website-baseline-2026-07-14/`.

## Screenshots (6 total)

| Page | Desktop 1920x1080 | Tablet 768x1024 | Mobile 375x667 |
|------|-------------------|-----------------|----------------|
| `index.html` (`/`) | 200, full render ✓ | 200, full render ✓ | 200, full render ✓ |
| `stage/index.html` (`/stage/`) | 200, full render ✓ | 200, full render ✓ | 200, full render ✓ |

All six are at `pmoves/docs/evidence/website-baseline-2026-07-14/screenshots/`. **Note: the index page is ~5790px tall at desktop, ~9730px at mobile** — single-page landing, expected.

**Visual observations** (no findings, just notes):
- The hero CTAs and customer cards render well at all viewports
- Gallery iframes load successfully on all 4 (3 hyperdim + 1 beats-constellation)
- The mobile index stacks cleanly; nav collapses to a hamburger
- The /stage/ room cards (Fordham Hill, PMOVES Demo, ToKenism Exchange) render with the new A2UI renderer; persona-driven typography is intact

## Broken-link sweep

`index.html` had 15 unique internal links. **5 are 404** (all expected per README):

| Link | Status | Type | Note |
|------|--------|------|------|
| `/demo/voice` | 404 | Founder TODO | "Coming Q2 2026" demo placeholder |
| `/demo/rag` | 404 | Founder TODO | "Coming Q2 2026" demo placeholder |
| `/privacy` | 404 | Founder TODO | Defensive fallback (no real page yet) |
| `/terms` | 404 | Founder TODO | Defensive fallback (no real page yet) |
| `/security` | 404 | Founder TODO | Defensive fallback (no real page yet) |

`/stage/` had 2 internal links; both work.

**Recommendation**: leave them as-is until you have real content. They're a visible signal that the site is "in progress" which matches the reality. When you ship `/privacy.html` etc., the existing `_redirects` rules (which 301 to anchor fallbacks) will simply stop firing.

## Accessibility audit (axe-core 4.10.2, WCAG 2 AA)

### `index.html` — 1 violation, 10 nodes

| ID | Impact | Help | Nodes | Targets |
|----|--------|------|-------|---------|
| `color-contrast` | serious | Elements must meet minimum color contrast ratio thresholds | 10 | `.card-link > .card-cta` (Enterprise, Communities, Disaster, Creators — x2 likely "Card" + nested CTA) |

**What it means**: the violet-on-dark CTA links at the bottom of each customer card (e.g. "Download the capabilities brief →") don't hit the 4.5:1 contrast ratio that WCAG AA requires for body text. The README's "Every color combination hits WCAG AA contrast on `#0b0b10` ground" is slightly optimistic.

**How to fix** (pick one):
- Brighten the CTA text to `#A78BFA` (soft violet) or `#C4B5FD` (lighter) — already in your palette
- Increase the font weight from 500 to 600
- Add `text-decoration: underline` for non-color contrast cue (WCAG 1.4.1)

**Effort**: ~5 minutes, 1 CSS rule change in `styles.css`. Single PR.

### `/stage/` — 1 violation, 1 node

| ID | Impact | Help | Nodes | Target |
|----|--------|------|-------|--------|
| `color-contrast` | serious | (same) | 1 | `footer > p` |

**What it means**: the footer line "Room manifests: `pmoves/config/rooms/` · curated by `access.visibility` · baked by `make stage-data`" uses a muted gray on the very dark stage background.

**How to fix**: bump the `--pm-muted` token or add a `:where(footer)` override. ~3 minute change in `stage/stage.css`.

### Why these slipped through

The README's accessibility claim was likely made by-eye or against a smaller token set. axe-core measures the actual computed color against the actual background at the actual font size — it'll catch anything the human eye is willing to forgive but a screen reader user can't compensate for. **These are real issues for ~10% of visitors** (low-vision, bright-sunlight reading, older displays). Fix them before any serious outreach push.

## Brand assets generated (4)

All in `pmoves/docs/evidence/website-baseline-2026-07-14/assets-generated/`:

| File | Spec | Purpose | Visual check |
|------|------|---------|--------------|
| `og-image.png` | 1200×630 (2K, 16:9 native — needs crop to exact 1200×630 if you want pixel-perfect) | Social previews (OG / Twitter) | ✓ matches hero |
| `favicon-512.png` | 512×512 | Favicon master; can be exported to 16/32/48/180 sizes | ✓ matches brand ◆ |
| `apple-touch-icon-1024.png` | 1024×1024 with rounded square (iOS will mask) | iOS home screen icon | ✓ matches brand ◆ |
| `mobile-node-rig.png` | 16:9 editorial photo, 2K | Hero for `#mobile-node` section (replaces SVG schematic) | ✓ Fordham Hill / Pelican case vibe |

**All four are research/diagnostic** — they live under `evidence/`, not in `website/assets/`. **DARKXSIDE visual sign-off required** before they're promoted to production paths.

### What still needs to be done to deploy these

1. **Visual sign-off** (DARKXSIDE) — open the 4 PNGs, confirm they match the brand vibe
2. **Crop the og-image** to exact 1200×630 (current is 16:9 ≈ 2752×1536; or accept 16:9 — most platforms crop anyway)
3. **Export favicon.ico** from `favicon-512.png` (multi-size: 16, 32, 48 packed in one .ico file) — needs imagemagick or a similar tool
4. **Drop the 4 files** into the right paths:
   - `website/og-image.png` (root)
   - `website/assets/favicon.ico` (replace stub)
   - `website/assets/apple-touch-icon.png` (replace stub)
   - `website/assets/mobile-node-rig.jpg` (or .webp for size)
5. **Uncomment the Cloudflare Web Analytics beacon** in `index.html` + add the host to CSP in `_headers`
6. **Re-deploy** via `wrangler pages deploy website --project-name pmoves-ai --branch main`

## What I did NOT do (and why)

- **No code changes** to `website/`, `pmoves/ui/`, or `styles.css`. The CLAIM explicitly said "no production changes" — this lane is research-only.
- **No PR opened** — the contrast fixes are queued as a recommendation, not committed.
- **No Lighthouse run** — Playwright + axe covers accessibility; Lighthouse is a superset that includes performance/SEO. If you want a Lighthouse baseline, that's a follow-up.
- **No CI gate added** — the playwright+axe script lives at `baseline.js` for re-runs, but isn't wired into a CI workflow yet (see "Follow-ups").
- **Did not touch the /stage/ A2UI vendored bundle** — that's 301KB of locked-down build-once-commit code; we trust the DL-4.1 / DL-4.2 work.

## Follow-ups (ranked by leverage)

1. **Fix the 2 contrast violations** in one tiny PR — both fixes are 1-3 line CSS changes; total effort <15 min; resolves 11 actual accessibility failures.
2. **Promote the 4 brand assets** after visual sign-off. This single-handedly closes 4 of the README §"Gaps the founder still needs to fill" items (og-image, favicon.ico, apple-touch-icon, mobile-node image).
3. **Wire the baseline script into CI** as a post-deploy smoke (`.github/workflows/website-baseline.yml`). Would catch the next contrast regression automatically. ~30 min to write.
4. **Generate a real capabilities-brief PDF** to replace the mailto CTA on the Enterprise card. The brief content already exists in scattered form (CLAUDE.md, NEXT_STEPS.md, PMOVES_MODEL_INTEGRATION_FRAMEWORK.md). Could be a 4-page PDF in an hour.
5. **Privacy/terms/security pages** — three 1-page HTML files. The README explicitly defers these; once shipped, the `_redirects` fallback rules become real.
6. **Real Discord URL** — blocks the `/discord` shortlink and the footer "Discord" link. One env var + one config update.

## Files changed this session

| File | Action | Note |
|------|--------|------|
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | EDIT | Added CLAIM entry (will RELEASE in this same lane) |
| `pmoves/docs/operations/WEBSITE_UI_BASELINE_2026-07-14.md` | NEW | This document |
| `pmoves/docs/evidence/website-baseline-2026-07-14/` | NEW | All artifacts (screenshots, JSON, generated assets) |

**0 production code files modified.** All changes are in `docs/` and `evidence/`.

## Reproducibility

To re-run the baseline:

```bash
# 1. Start the local server (from repo root)
python -m http.server 8765 --bind 127.0.0.1 --directory website

# 2. Run the playwright baseline (separate shell)
node "C:\Users\russe\.agents\skills\playwright\run.js" \
  "C:\Users\russe\Documents\GitHub\PMOVES.AI\.worktrees\feat-auto-20260714-9d8a9584\pmoves\docs\evidence\website-baseline-2026-07-14\baseline.js"
```

> **Note**: the playwright skill's `run.js` changes cwd to the skill directory. The baseline script uses relative paths from the **worker's** cwd, so if you run from outside the worktree, the screenshots land in `<skill-dir>/pmoves/docs/...` instead of the worktree. Move them after.

## Signoff

- **Delivery body**: Mavis-5090 (this lane)
- **Control body**: DARKXSIDE (visual sign-off on the 4 generated assets + go/no-go on shipping the contrast fixes)
- **Memory body**: this trail + `pmoves/docs/operations/WEBSITE_UI_BASELINE_2026-07-14.md`

CHIT trail unsigned-local (no passphrase loaded). agent_signature: `ACK::Mavis-5090::WEBSITE-UI-BASELINE-DELIVERED-2026-07-14`.

---

*Built by Mavis-5090 from the auto-mode worktree `feat/auto-20260714-9d8a9584` on 2026-07-14.*
