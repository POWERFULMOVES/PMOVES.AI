# Self-hosted fonts (`website/fonts/`)

Self-hosted so the brand display face works under the hardened CSP
(`font-src 'self'`; no Google Fonts / external requests) — part of DL-2 of the
unified design language.

| File | Family | License | Use |
|------|--------|---------|-----|
| `orbitron-v35-latin-wght.woff2` | Orbitron (variable, wght 400–900, latin subset) | SIL OFL 1.1 — see `OFL.txt` | display headings (`h1`/`h2`), brand wordmark |

Body + mono text intentionally stay on the system font stack (the landing page
keeps zero external requests and a small payload).

The `--pm-font-display` / `--f-display` token in `../styles.css` references this
face; it mirrors the `pmoves-armor` theme display font in
`pmoves/design/build/tokens.pmoves-armor.css`.

**Source:** Orbitron via Google Fonts (gstatic), latin subset, woff2. To refresh,
re-fetch `https://fonts.googleapis.com/css2?family=Orbitron:wght@400..900` with a
modern User-Agent and download the referenced woff2.
