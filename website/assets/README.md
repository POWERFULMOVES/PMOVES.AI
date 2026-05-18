# website/assets

Drop brand assets here. The landing page references these specific
filenames — easiest path is to match them exactly.

## Needed now

| Filename                 | Purpose                        | Size                 | Notes |
|--------------------------|--------------------------------|----------------------|-------|
| `favicon.svg`            | Primary favicon (shipped)      | any (SVG)            | Replace the stub diamond with real mark when ready. |
| `favicon.ico`            | Legacy favicon fallback        | 32x32 + 16x16 (.ico) | Generate from logo. |
| `apple-touch-icon.png`   | iOS home-screen icon           | 180x180 PNG          | Opaque, no transparency for iOS. |
| `/og-image.png` (root)   | Open Graph + Twitter card      | 1200x630 PNG         | Place at `website/og-image.png` (not in assets/). |

## Optional

| Filename                 | Purpose                        | Size                 |
|--------------------------|--------------------------------|----------------------|
| `logo.svg`               | Full wordmark for hero         | vector               |
| `portrait.jpg`           | Founder photo for future About | 800x1000 JPG         |
| `mobile-node.jpg`        | Real photo of the rolling rig  | 1600x900 JPG         |

## Image guidelines

- **Dark-friendly first.** Page background is `#0b0b10`.
- **No text baked into PNGs** — keep copy in HTML for a11y + i18n.
- **Compress.** Run PNGs through `oxipng -o4` or squoosh.app before commit.
- **Keep each image under 150 KB** unless it's a hero background.

After dropping new files, push to the `feat/website-landing-page` branch
(or whatever branch Cloudflare Pages is tracking) — the CDN will pick
them up on next deploy.
