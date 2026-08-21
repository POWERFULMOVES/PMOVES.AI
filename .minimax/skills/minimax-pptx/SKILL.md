---
name: minimax-pptx
description: >
  Build, edit, audit and extract from PPTX presentations using python-pptx and
  PptxGenJS, with a slide-type catalogue, a design system for palette and
  typography, and rendering to PNG for visual inspection. Use when the output or
  input is a slide deck — "make a deck", "build slides", "fix this presentation",
  "pull the images out of this pptx", "read the reviewer comments", "screenshot
  the slides" — and when a task implies a presentation deliverable. Covers PPTX,
  PowerPoint, slides, deck, presentation, 幻灯片, 演示文稿, PPT.
license: MIT
compatibility: Requires Python 3 with python-pptx; Node for PptxGenJS; LibreOffice for PDF export, and macOS/Swift for the pdf2png renderer.
metadata:
  author: MiniMax Agent
  adapted-by: PMOVES.AI
  version: "1.0.0-pmoves"
  category: document-processing
  upstream: none
---

# minimax-pptx

Build, edit, audit and extract from PPTX decks.

## Read before generating

- `references/slide-types.md` — the slide-type catalogue; choose the type first
- `references/design-system.md` — palette reference and typography rules
- `references/pitfalls.md` — the failure modes worth knowing in advance

## Two generation libraries

| library | reference |
|---|---|
| python-pptx | `references/python-pptx-recipes.md` |
| PptxGenJS | `references/pptxgenjs.md` |

`references/editing.md` covers mutating an existing deck rather than authoring a
new one.

## Scripts

| script | purpose |
|---|---|
| `scripts/audit_pptx.py` | check a deck against the design system |
| `scripts/extract_pptx.py` | unpack deck structure |
| `scripts/extract_images.py` | pull embedded images |
| `scripts/extract_comments.py` | pull reviewer comments |
| `scripts/pptx-screenshot.sh` | render slides for visual inspection |
| `scripts/pdf2png.swift` | PDF→PNG renderer used by the screenshot path |

## Provenance

**PMOVES-local. There is no upstream counterpart.** Authored by MiniMax Agent on
2026-05-13 and landed in PMOVES.AI via #1484 as "skill scaffolding".

`MiniMax-AI/skills` has *no* `minimax-pptx` — checked against its full tree, its
commit history for that path (zero commits), its tags (none), and every branch.
Its nearest equivalents are a different skill, `pptx-generator`, and a separate
`plugins/pptx-plugin/`. So this is not a stale copy of anything and must not be
replaced by assuming it is.

It shipped without a `SKILL.md`, which is why the `skills` package could not see
it. This file is that missing entry point.
