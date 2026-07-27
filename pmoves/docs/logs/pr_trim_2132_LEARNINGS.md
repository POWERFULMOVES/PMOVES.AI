# PR #2132 — Peer-Review Trim LEARNINGS

> Reviewer: 5090-CLAUDE (peer-CLAUDE angle, 3-angle reciprocity).
> Style: `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` (Mavis-5090).
> Fix commits on this branch: XSS hardening, self-hosted media, correctness nits.

## Conformance delta

| Gate | Pre-trim | Post-trim |
|------|----------|-----------|
| compose python tests | 19/19 | 19/19 |
| component registry | 7/7 | 7/7 |
| axe-core WCAG 2 AA | 0 violations (21 rules) | 0 violations (21 rules) |
| tenant page render (Chrome, 127.0.0.1 served) | full render | full render, clean console |
| external URLs in shipped tenant JSON | 2 (unsplash, archive.org) | 0 |

## missed-signal

1. **The compose tool is not the runtime security boundary.** `compose.py`
   enum-validates `aspectRatio` etc., but `tenant-renderer.js` fetches the
   JSON and applies props with no validation — the component layer is the
   real boundary. Three concrete escapes existed: CSS-context injection via
   `aspect-ratio` into the shadow `<style>`, `javascript:` hrefs surviving
   `_escapeAttr`, and `applyProps` writing ANY key (incl. `innerHTML`) onto
   live elements. Pattern: **whenever a validator and a consumer are in
   different languages/processes, re-enforce at the consumer.**
2. **`createComponent` trusted the tag name** — `document.createElement`
   would happily make a `<script>`. Registry allowlist (`pm-*` +
   `customElements.get`) added.
3. **CDN assets in `website/`** (unsplash image, archive.org mp3) violated
   the self-host rule and leaked visitor IPs. The conformance harness checks
   a11y/tokens/shadow — it has no "no external origins" check. **Candidate
   gate addition: grep shipped tenant JSON for `https?://`.**

## fix-pattern

4. **`role` → `agentRole` rename was incomplete**: component + shipping
   fixture used `agentRole`, but tests/demos still passed `role` (4 sites).
   When a prop is renamed for ARIA-safety, sweep tests and demos in the same
   commit — the hardened `applyProps` now makes the old name fail loudly
   instead of silently clobbering ARIA.
5. **Malformed meta tag** (`<meta name="color-scheme" "dark">`) — HTML
   parsers absorb the error silently; screenshots can't catch a meta tag.
   A tidy/html-validate pass on `website/` would.

## wrong-suggestion

6. **register.js claimed "we use a try/catch to make the import
   side-effect safe" — no try/catch exists.** The code was still correct
   (ES-module caching is the real guard), but the comment taught the next
   maintainer a false mechanism. Comments that state a safety mechanism
   must name the actual one.

## already-addressed

7. `_escapeText`/`_escapeAttr` are present and correct in all 7 components
   for HTML-text and attribute contexts — the gaps were only the CSS
   context and URL schemes (different injection contexts need different
   escapes; there are more contexts than escapers).
8. Lifecycle cleanup (EventSource unsubscribe in `disconnectedCallback`)
   verified correct in pm-metric-tile / pm-space-agent-card.
9. No secrets, internal hostnames, or topology in the diff. `--pm-signature`
   untouched; darkxside theme sets `--pm-accent` only.

## fixture-provenance (post-merge, resolved)

10. **Fordham-resident-legitimacy — 2 attributed quotes in `fordham-hill.json`
    with no recorded consent or provenance, pinned to a real, identifiable
    Bronx housing cooperative.** A trim cycle that only reads diffs misses
    fixture-content questions — this needed a fixture-content audit step.
    **Resolved:** quotes rewritten to obviously-synthetic personas ("Sample
    voice — Maya R." / "Sample voice — Devon A." with `illustrative persona
    (not a real resident)` role). A 3rd quote-block added as a "share your
    story" CTA inviting real Fordham Hill residents to contribute — when they
    do with consent, their quote replaces the placeholder (option C path).
