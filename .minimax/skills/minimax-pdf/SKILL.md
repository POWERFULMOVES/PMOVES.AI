---
name: minimax-pdf
description: >
  Create, read, reformat and fill PDF documents. Generation routes cover HTML→PDF
  (page geometry, page-break rules, Chart.js settle, CJK font cascade) and LaTeX
  for academic theses and technical books; reading covers text/table extraction
  and vision-based inspection; forms cover AcroForm fill and inspection. Use when
  the output or input is a .pdf — "make a report", "generate a PDF", "fill this
  form", "extract the tables", "read this scanned document", "convert to PDF" —
  and when a task implies a printable deliverable. Covers PDF, AcroForm, LaTeX,
  thesis, whitepaper, annual report, visa form, 表单, 报告, 论文.
license: MIT
compatibility: Requires Python 3; headless Chrome for the HTML→PDF route and a LaTeX toolchain for the LaTeX routes.
metadata:
  author: MiniMaxAI
  adapted-by: PMOVES.AI
  version: "1.0.0-pmoves"
  category: document-processing
  upstream: MiniMax-AI/skills
---

# minimax-pdf

Generate, read, reformat and fill PDFs.

## Pick a route before doing anything

| intent | route |
|---|---|
| generate a new PDF from content | `docs/create-guide.md` |
| academic thesis (LaTeX) | `docs/latex-academic-thesis-guide.md` |
| technical book (LaTeX) | `docs/latex-technical-book-guide.md` |
| extract text / tables / meaning | `docs/read-guide.md` |
| inspect visually (scans, layout) | `docs/vision-guide.md` |
| fill or inspect an AcroForm | `docs/forms-guide.md` |
| restyle an existing document | `docs/reformat-guide.md` |

Two contracts back the generation routes and both are prerequisites, not
optional reading:

- `docs/html-pdf-spec.md` — the **mechanical** contract: page geometry,
  page-break rules, Chart.js settle, CJK cascade
- `docs/design-guide.md` — the **aesthetic** contract: palette mood, typography,
  anti-patterns

When something misbehaves: `docs/pitfalls-index.md`, `docs/troubleshooting.md`,
`docs/advanced-reference.md`.

## Worked cases

Real end-to-end runs, useful as templates for similar work:

- `docs/annual-report-financial-digest-latex-case.md`
- `docs/ai-voice-cloning-regulatory-report-case.md`
- `docs/docx-contract-roundtrip-professional-case.md`
- `docs/email-translation-goldman-two-sessions-case.md`
- `docs/italy-schengen-visa-acroform-case.md`
- `docs/markdown-static-academic-data-viz-case.md`

## Scripts

`scripts/` provides the reading library (`_pdf_read_lib.py`, `pdf_inspect`),
form fill (`fill`), assembly (`merge.py`), and the build entry point (`make.sh`).

## Attribution

Upstream is [`MiniMax-AI/skills`](https://github.com/MiniMax-AI/skills) (MIT),
`skills/minimax-pdf`. This copy has diverged substantially — 79 files against
upstream's 12 — with the guides, contracts and worked cases added on the PMOVES
side. Upstream still holds nine files this copy does not (`design/design.md`,
`README.md`, and `scripts/{cover,fill_inspect,fill_write,palette,render_body}.py`,
`render_cover.js`); folding those in is open work, tracked separately rather than
assumed here.
