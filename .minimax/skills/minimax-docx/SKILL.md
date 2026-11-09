---
name: minimax-docx
description: >
  Create, edit, format, repair and compare DOCX documents via OpenXML SDK (.NET)
  and Python helpers. Three pipelines: create from scratch, fill/edit an existing
  document, or apply template formatting with XSD validation. Use whenever the
  output is a .docx — "write a report", "draft a proposal", "make a contract",
  "fill in this form", "reformat to match this template" — and also when the task
  merely implies a printable or formal document without naming Word. Covers Word,
  docx, document, report, contract, official document, layout, templating,
  文档, 报告, 合同, 公文, 排版, 套模板.
license: MIT
compatibility: Requires .NET (OpenXML SDK) for the C# backends and Python 3 for the helper scripts; LibreOffice for PDF/page rendering.
metadata:
  author: MiniMaxAI
  adapted-by: PMOVES.AI
  version: "1.0.0-pmoves"
  category: document-processing
  upstream: MiniMax-AI/skills
  standards: "ECMA-376 OOXML; GB/T 9704-2012; IEEE/ACM/APA/MLA/Chicago/Turabian; Springer LNCS / Nature / HBR templates"
---

# minimax-docx

Create, edit, and format DOCX documents through OpenXML SDK (.NET) backends and
Python helper scripts.

## Read `docs/index.md` next — do not improvise a route

This skill is **route-first**. `docs/index.md` is the dispatch table; it picks the
task file, and each task file is self-contained. Reading this file and then
guessing is the documented anti-pattern.

| intent | route |
|---|---|
| new formal Word deliverable | `docs/task-create.md` |
| same content, new template / visual system | `docs/task-apply-template.md` |
| in-place content mutation on an existing DOCX | `docs/task-edit-fill.md` |
| read meaning | `docs/task-read-content.md` |
| inspect structure | `docs/task-read-structure.md` |
| inspect rendered pages | `docs/task-read-rendered.md` |
| fix visible defects | `docs/task-repair-layout.md` |
| compare two DOCX files | `docs/task-compare-two-docx.md` |

Load only when the route calls for it:

- `docs/router.md` — route choice is ambiguous
- `docs/evidence.md` — the route needs truth-source arbitration
- `docs/backends.md` — backend choice is still ambiguous after route + mode
- `docs/acceptance.md` + `docs/acceptance-checklists/` — validating output
- `docs/anti-patterns.md`, `docs/failure-taxonomy.md` — something went wrong
- `docs/template-dsl.md`, `docs/xml-patch-dsl.md`, `docs/tables-and-numbering.md`,
  `docs/track-changes.md`, `docs/rendered-delivery.md` — mechanics

## Scripts

`scripts/` holds the Python side: `unpack_docx.py` / `pack_docx.py`,
`read_docx_structure.py`, `extract_docx_text.py`, `diff_docx_structure.py`,
`build_patch_plan.py`, `verify_anchor_atomicity.py`,
`validate_template_manifest.py`, `render_docx_pages.py`, `rendered_report.py`,
`docx_to_pdf.py`. The .NET backends live under `scripts/dotnet/`.

Sample payloads for the DSLs are in `references/sample-patch-plans.json`,
`sample-task-intents.json`, and `sample-template-manifests.json`.

## Attribution

Upstream is [`MiniMax-AI/skills`](https://github.com/MiniMax-AI/skills) (MIT),
`skills/minimax-docx`. This copy shares 74 of upstream's 75 files and adds a
PMOVES routing/acceptance layer on top (`docs/`, the Python `scripts/`, and the
`references/` samples). The one upstream file it lacked was this `SKILL.md`,
which is why the skill was invisible to the `skills` package until now — every
`docs/*` file already said *"Start here only after reading `../SKILL.md`."*
