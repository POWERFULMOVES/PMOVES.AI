# vision-guide — `read_pdf_vision.py` reference

> Detailed reference for the only in-skill wrapped read route — `read_pdf_vision.py`.
> It prepares byte-bounded PNG chunks from selected PDF pages. The agent runtime's
> image-understanding tool performs the actual visual interpretation. All other
> read scenarios (text / tables / coordinates / raster / decrypt / metadata)
> are cookbook recipes in [`SKILL.md`](../SKILL.md) §3-§4 and §7. There is no
> wrapped script for them — pdfplumber, pypdfium2, poppler, and qpdf are called
> directly from a few lines of Python or shell.

## Why a script instead of a recipe

`vision` cannot be expressed as a one-liner: it has to render selected pages with
poppler / pdf2image and pack them into multi-page chunks under a per-request byte
ceiling. The chunking and spill-to-disk rule are too much to ask the LLM to
re-derive every time. Hence the wrapped script.

The script deliberately does **not** call a separate CLI, local daemon, or hand-written tool endpoint.
After it emits chunk image paths, call the agent runtime's built-in image-understanding tool on each
chunk with the prompt shown in the output.

## Command

```bash
python3 -m scripts.read_pdf_vision --input file.pdf [opts]
```

Run from the `minimax-pdf` skill root (where `scripts/` lives) so the
`scripts` package is importable.

## Common parameters

| Argument | Purpose | Default |
|---|---|---|
| `--input <path>` | Path to the PDF (required) | — |
| `--pages <spec>` | Page range: `1-20` / `1,3,5` / `1-3,7,10-15` / `all`. Out-of-range pages are silently dropped with a stderr warning — e.g. `--pages 1-50` on a 26-page PDF runs on 1-26 and warns about 27-50. The script aborts only if **every** requested page is past the end. | `all` |
| `--json` | Emit structured JSON instead of Markdown | Markdown |
| `--max-stdout-bytes <n>` | Spill outputs larger than `n` bytes to `~/.cache/agent-server/pdf-out/<hash>.{md,json}` and return only a preview + path. `0` disables spilling and writes the full output to stdout. | `2048` |

## Mode-specific arguments

| Argument | Purpose | Default |
|---|---|---|
| `--dpi <n>` | Page-to-PNG render DPI | `150` |
| `--max-bytes <n>` | Per-chunk byte ceiling (default ~3 MB; upstream nginx caps near 5 MB) | `3000000` |
| `--prompt <text>` | Prompt to use when calling the agent image-understanding tool per chunk | see below |
| `--output-dir <dir>` | Persist chunk PNGs to this directory | `~/.cache/agent-server/pdf-vision-chunks/<file-hash>/` |
| `--keep-pages` | Also persist individual page PNGs for debugging | off |

Default prompt (in Chinese, baked into the script):

> Please output every piece of text in this image in reading order while
> preserving paragraphs, lists, and tables. Briefly describe any charts.

## Internal chunking

1. `pdf2image` renders the selected pages to PNGs (poppler / pdftoppm backend).
2. **Stitch-and-grow:** assemble one image, measure its true byte size, append
   the next page if there is room, roll back one page on overflow. Each chunk
   sits as close to `--max-bytes` as possible.
3. Multi-page chunks are stitched vertically with PIL (no page cap; only bytes).
4. A single page that already exceeds the limit is re-rendered at 100 DPI.
5. Each chunk is written as a PNG and listed in the manifest / Markdown output.
6. The caller sends each chunk path to the agent runtime's image-understanding tool.

## Time budget

| Page count | Typical runtime | Suggested caller timeout |
|---|---|---|
| 5 pages | 30 s – 1 min | 3 min |
| 10 pages | ~1 min | 5 min |
| 30 pages | 3 – 5 min | 10 min |
| 50 pages | 5 – 8 min | 15 min |
| 100 pages | 10 – 15 min | 25 min |

The script applies its own 25-minute per-chunk timeout, but the **outer caller**
(bash / agent harness) must also raise its timeout — the default 2-minute bash
timeout will cut a long run in half. For 100+ pages, batch with `--pages 1-30`,
`--pages 31-60`, etc., and call the script once per batch.

## Error handling

| Error | Meaning | Action |
|---|---|---|
| emitted chunk is too large for the image tool | The stitched PNG exceeds the runtime's upload/input limit | Add `--max-bytes 2000000` (or 1500000), shrink `--pages`, drop to `--dpi 100` |
| `pdf2image` / `pdftoppm` failure | Poppler is missing or the PDF cannot be rendered | Install poppler or repair/decrypt the PDF first |
| image-understanding tool failure | Runtime image tool is temporarily unavailable or rejected the image | Retry with smaller chunks; if still unavailable, return the pdfplumber text-only result and state that visual content could not be interpreted |

## Dependencies

```bash
pip3 install --user pdf2image pillow
brew install poppler        # pdftoppm (pdf2image backend) + pdfinfo
```

## Output spill (preventing context blow-up)

**Default:** when the output exceeds 2 KB, the script does NOT print the full
text to stdout. Instead it:

1. Writes the full content to `~/.cache/agent-server/pdf-out/<sha256-prefix>.{md,json}`
   (named by content hash so identical outputs reuse the same file).
2. Returns the first 2 KB as a preview plus the absolute path on stdout.
3. Lets the model decide what to do next:
    - Read the whole file: `cat ~/.cache/agent-server/pdf-out/abc...md`
    - Search for something specific: `grep -i "keyword" ~/.cache/agent-server/pdf-out/abc...md`
   - Re-extract a narrower range: `python3 -m scripts.read_pdf_vision --input <file> --pages 14-18`

**Markdown mode** prepends the preview with:

```markdown
<!-- minimax-pdf: output truncated, full text spilled to disk -->
> Full output: 12,345 bytes -> /Users/.../<hash>.md
> Showing first 2,048 bytes below.
> Read the file with `cat` / `grep`, or re-run with narrower `--pages`.
```

**JSON mode** wraps the spilled output:

```json
{
  "truncated": true,
  "totalBytes": 12345,
  "outputFile": "/Users/.../<hash>.json",
  "previewBytes": 2048,
  "preview": "..."
}
```

**Disable truncation** (full output to stdout): `--max-stdout-bytes 0`.
**Adjust threshold:** `--max-stdout-bytes 8192`, etc.

## JSON output schema

```jsonc
{
  "mode": "vision",
  "file": "/abs/path.pdf",
  "pageCount": 18,
  "selectedPages": [1, 2, ..., 18],
  "dpi": 150,
  "chunks": [
    {
      "pages": [1, 2, ..., 7],
      "sizeBytes": 2870055,
      "width": 1241,
      "height": 12278,
      "text": "...",
      "isError": false
    }
  ]
}
```

When truncated by `--max-stdout-bytes`, stdout returns the wrapper:

```jsonc
{
  "truncated": true,
  "totalBytes": 12345,
  "outputFile": "/Users/.../<hash>.json",
  "previewBytes": 2048,
  "preview": "..."   // first 2 KB of the full JSON above; trailing bytes may be invalid JSON
}
```

## Shared helper module

`scripts/_pdf_read_lib.py` — helpers used by `read_pdf_vision.py`:

- `parse_pages(raw)` / `validate_pages(pages, total)` / `format_pages(pages)`
- `maybe_spill_to_file(content, ext, max_bytes)`
- `add_common_args(parser)` / `emit(content, ext, max_bytes)`
- `info(msg)` / `warn(msg)` / `die(msg)` for stderr progress

Kept under the original name `_pdf_read_lib.py` even though `vision` is now the
only consumer — the helpers are read-side concerns (page spec parsing, output
spill, stderr progress) and the leading underscore already signals "internal".
