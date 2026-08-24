---
name: minimax-xlsx
description: >
  Create, edit and repair XLSX workbooks with openpyxl and xlsxwriter, including
  full styling, charts, conditional formatting, in-place edits, formula
  recalculation, and a raw-OOXML escape hatch validated against the ECMA-376 /
  ISO-IEC 29500 schemas. Use when the output or input is a spreadsheet — "build a
  workbook", "add a chart", "fix these formulas", "reformat this sheet",
  "convert to Excel", "why is this cell wrong" — and when a task implies tabular
  deliverables. Covers Excel, xlsx, spreadsheet, workbook, formulas, pivot,
  charts, 表格, 报表, 公式.
license: MIT
compatibility: Requires Python 3 with openpyxl and xlsxwriter; LibreOffice for formula recalculation.
metadata:
  author: MiniMaxAI
  adapted-by: PMOVES.AI
  version: "1.0.0-pmoves"
  category: document-processing
  upstream: MiniMax-AI/skills
  standards: "ECMA-376 OOXML; ISO/IEC 29500-4:2016"
---

# minimax-xlsx

Create, edit and repair XLSX workbooks.

## Routes

| intent | route |
|---|---|
| write or edit a workbook | `docs/create-edit-guide.md` |
| naming, layout and formatting conventions | `docs/conventions-guide.md` |
| formulas are stale or wrong | `docs/recalc-guide.md` |
| the library cannot express it | `docs/raw-xml-escape-hatch.md` |
| something is broken | `docs/pitfalls-index.md` |
| deeper mechanics | `docs/advanced-reference.md` |

`docs/create-edit-guide.md` is the openpyxl + xlsxwriter cookbook — the minimal
one-liners live in §3 below; go there when a one-liner is not enough (full
styling, charts, conditional formatting, in-place edits, merged cells, shared
strings).

## Worked case

`docs/superstore-multiformat-conversion-case.md`, with its fixtures under
`docs/cases/superstore-multiformat/`.

## Scripts

`scripts/recalc.py` drives formula recalculation. `scripts/office/` holds the
OOXML layer: `pack.py`, the `helpers/` (`merge_runs.py`, `simplify_redlines.py`),
and the ECMA-376 / ISO-IEC 29500-4:2016 schema set used to validate raw-XML
edits before they are written back.

## Attribution

Upstream is [`MiniMax-AI/skills`](https://github.com/MiniMax-AI/skills) (MIT),
`skills/minimax-xlsx`.

**These two share a name and nothing else.** Comparing file-by-file, the overlap
is exactly **zero of 61 local and 25 upstream files**: upstream organises around
`references/{create,edit,fix,format,read-analyze,validate}.md` plus
`scripts/formula_check.py`, while this copy organises around `docs/*-guide.md`
plus `scripts/office/` with the bundled schemas. They are two independent skills
that happen to address the same file format.

That is worth deciding deliberately rather than merging by accident — folding
upstream in under the same name would silently replace this implementation. It is
left as an open question rather than resolved here.
