#!/usr/bin/env python3
"""read_pdf_vision.py — prepare PDF page images for agent vision tools.

Renders selected pages with pdf2image (poppler), stitches them vertically into
≤ --max-bytes images (3 MB default; page-count uncapped), and writes a
manifest pointing at the generated PNG chunks. The agent runtime is responsible
for sending those images to its built-in image-understanding tool.

This is the only wrapped read script in minimax-pdf: vision needs page
rendering and byte-budget chunking that don't fit in a cookbook recipe. Other
read scenarios (text / tables / coordinates / raster / decrypt / metadata) live
as inline recipes in docs/read-guide.md.

Usage (run from the minimax-pdf skill root):
    python3 -m scripts.read_pdf_vision --input file.pdf [--pages 1-20]
                                       [--dpi 150] [--max-bytes 3000000]
                                       [--prompt "..."] [--output-dir DIR]
                                       [--json] [--max-stdout-bytes N]

Dependencies (all `pip3 install --user`):
  - pdf2image (also needs `brew install poppler` for the pdftoppm backend)
  - Pillow

After the script returns, call the agent runtime's image-understanding tool on
each chunk image path using the emitted prompt. Do not call a separate daemon
or hand-written tool endpoint from this skill.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts._pdf_read_lib import (
    add_common_args,
    cache_dir,
    die,
    emit,
    format_pages,
    info,
    resolve_input_or_exit,
    resolve_pages_or_exit,
    to_ranges,
    warn,
)

try:
    from pdf2image import convert_from_path  # type: ignore
except ImportError:
    die("pdf2image not installed. Install: pip3 install --user pdf2image (and brew install poppler)")

try:
    from PIL import Image  # type: ignore
except ImportError:
    die("Pillow not installed. Install: pip3 install --user pillow")

DEFAULT_DPI = 150
FALLBACK_DPI = 100
DEFAULT_MAX_BYTES = 3_000_000
DEFAULT_PROMPT = (
    "请把这张图里的全部文字按阅读顺序输出，保留段落、列表、表格等结构。"
    "如有图表请简要描述。"
)


def _safe_tmp_root() -> Path:
    env_tmp = os.environ.get("TMPDIR", "")
    if env_tmp and not env_tmp.startswith("/tmp"):
        return Path(env_tmp)
    return cache_dir().parent  # ~/.cache/agent-server/


def _default_output_dir(pdf: Path, pages: list[int], dpi: int) -> Path:
    key = hashlib.sha256(f"{pdf.resolve()}|{format_pages(pages)}|{dpi}".encode("utf-8")).hexdigest()[:16]
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", pdf.stem).strip("-") or "pdf"
    return cache_dir().parent / "pdf-vision-chunks" / f"{safe_stem}-{key}"


def _render(pdf: Path, pages: list[int], dpi: int, tmp_root: Path) -> list[tuple[int, Image.Image, int]]:
    """Render selected pages → list of (page_num, PIL Image, png_bytes)."""
    rendered: list[tuple[int, Image.Image, int]] = []
    for lo, hi in to_ranges(pages):
        # pdf2image numbers from `first_page`; results length == hi - lo + 1
        imgs = convert_from_path(
            str(pdf),
            dpi=dpi,
            first_page=lo,
            last_page=hi,
            fmt="png",
            output_folder=str(tmp_root),
            paths_only=False,
        )
        for i, img in enumerate(imgs):
            page_num = lo + i
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=False)
            rendered.append((page_num, img, len(buf.getvalue())))
    return rendered


def _stitch(images: list[Image.Image]) -> tuple[Image.Image, bytes, int]:
    """Vertically stitch a list of PIL images. Returns (stitched_image, png_bytes, byte_size)."""
    if len(images) == 1:
        only = images[0]
        buf = io.BytesIO()
        only.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        return only, data, len(data)
    target_w = max(img.width for img in images)
    total_h = sum(img.height for img in images)
    stitched = Image.new("RGB", (target_w, total_h), color=(255, 255, 255))
    y = 0
    for img in images:
        # Paste left-aligned (anchor x=0).
        stitched.paste(img.convert("RGB"), (0, y))
        y += img.height
    buf = io.BytesIO()
    stitched.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    return stitched, data, len(data)


def _stitch_and_grow(
    rendered: list[tuple[int, Image.Image, int]],
    max_bytes: int,
) -> tuple[list[dict], list[int]]:
    """Pack pages into byte-bounded chunks via measure-then-grow.

    Returns:
      chunks: [{pages, buffer (bytes), width, height, bytes}, ...]
      oversize_indices: chunk indices whose stitched PNG still > max_bytes
    """
    chunks: list[dict] = []
    oversize_indices: list[int] = []
    i = 0
    n = len(rendered)
    while i < n:
        count = 1
        imgs = [rendered[i][1]]
        stitched_img, data, sz = _stitch(imgs)
        if sz > max_bytes:
            # Single page over budget — accept alone and warn.
            chunks.append(
                {
                    "pages": [rendered[i][0]],
                    "buffer": data,
                    "width": stitched_img.width,
                    "height": stitched_img.height,
                    "bytes": sz,
                }
            )
            oversize_indices.append(len(chunks) - 1)
            i += 1
            continue
        # Greedy grow.
        while i + count < n:
            trial_imgs = imgs + [rendered[i + count][1]]
            trial_img, trial_data, trial_sz = _stitch(trial_imgs)
            if trial_sz > max_bytes:
                break
            imgs = trial_imgs
            stitched_img = trial_img
            data = trial_data
            sz = trial_sz
            count += 1
        chunks.append(
            {
                "pages": [rendered[i + k][0] for k in range(count)],
                "buffer": data,
                "width": stitched_img.width,
                "height": stitched_img.height,
                "bytes": sz,
            }
        )
        i += count
    return chunks, oversize_indices


def _downscale_oversize(
    pdf: Path,
    rendered: list[tuple[int, Image.Image, int]],
    max_bytes: int,
    tmp_root: Path,
) -> list[tuple[int, Image.Image, int]]:
    """Re-render any single page that exceeds max_bytes at FALLBACK_DPI."""
    out: list[tuple[int, Image.Image, int]] = []
    for n, img, sz in rendered:
        if sz <= max_bytes:
            out.append((n, img, sz))
            continue
        warn(f"page {n} {sz} bytes > {max_bytes}; re-rendering at {FALLBACK_DPI} DPI")
        re_imgs = convert_from_path(
            str(pdf),
            dpi=FALLBACK_DPI,
            first_page=n,
            last_page=n,
            fmt="png",
            output_folder=str(tmp_root),
            paths_only=False,
        )
        if not re_imgs:
            die(f"failed to re-render page {n}")
        re_img = re_imgs[0]
        buf = io.BytesIO()
        re_img.save(buf, format="PNG", optimize=False)
        out.append((n, re_img, len(buf.getvalue())))
    return out


def _dump_keep_tmp(
    keep_dir: Path,
    rendered: list[tuple[int, Image.Image, int]],
    chunks: list[dict],
) -> None:
    keep_dir.mkdir(parents=True, exist_ok=True)
    for n, img, _ in rendered:
        img.save(keep_dir / f"page_{n:04d}.png", format="PNG")
    for i, c in enumerate(chunks, 1):
        first, last = c["pages"][0], c["pages"][-1]
        (keep_dir / f"chunk_{i:02d}_p{first:04d}-p{last:04d}.png").write_bytes(c["buffer"])


def _write_chunk_images(out_dir: Path, chunks: list[dict]) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for i, c in enumerate(chunks, 1):
        first, last = c["pages"][0], c["pages"][-1]
        path = out_dir / f"chunk_{i:02d}_p{first:04d}-p{last:04d}.png"
        path.write_bytes(c["buffer"])
        out.append(
            {
                "pages": c["pages"],
                "sizeBytes": c["bytes"],
                "width": c["width"],
                "height": c["height"],
                "imagePath": str(path),
            }
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description="Prepare PDF page images for the agent runtime's image-understanding tool.",
    )
    add_common_args(p)
    p.add_argument(
        "--dpi", type=int, default=DEFAULT_DPI, help=f"Render DPI (default {DEFAULT_DPI})."
    )
    p.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Per-chunk byte budget (default {DEFAULT_MAX_BYTES}).",
    )
    p.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Recommended prompt to use when calling the agent image-understanding tool per chunk.",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Directory for persisted chunk PNGs. Defaults to ~/.cache/agent-server/pdf-vision-chunks/<file-hash>/.",
    )
    p.add_argument(
        "--keep-pages",
        action="store_true",
        help="Also persist individual page PNGs next to the chunk PNGs for debugging.",
    )
    args = p.parse_args()

    if shutil.which("pdftoppm") is None:
        die("'pdftoppm' (poppler) not found. Install: brew install poppler")

    pdf_path = resolve_input_or_exit(args.input)

    # Probe the PDF with pdfinfo *before* anything heavy — this is the
    # double-safety net: page count, encryption status, and a corrupt-PDF
    # detector that runs in milliseconds. Downstream code (page clamping,
    # render budgeting) depends on `total_pages` being trustworthy.
    if shutil.which("pdfinfo") is None:
        die("'pdfinfo' (poppler) not found. Install: brew install poppler")
    try:
        out = subprocess.check_output(
            ["pdfinfo", str(pdf_path)], stderr=subprocess.STDOUT
        ).decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        err_tail = (e.output or b"").decode("utf-8", errors="ignore").strip()[-300:]
        die(
            f"pdfinfo failed on {pdf_path} (exit {e.returncode}). "
            f"PDF may be corrupt or password-protected. pdfinfo said: {err_tail}"
        )
    except FileNotFoundError:
        die("'pdfinfo' (poppler) not found. Install: brew install poppler")

    total_pages = next(
        (int(line.split(":", 1)[1].strip()) for line in out.splitlines() if line.startswith("Pages:")),
        0,
    )
    if total_pages == 0:
        die(f"Could not determine page count for {pdf_path} (pdfinfo output had no 'Pages:' line)")
    info(f"PDF probe: {total_pages} page(s) total")

    selected = resolve_pages_or_exit(args.pages, total_pages)

    tmp_root = _safe_tmp_root()
    tmp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pdf-vis-", dir=tmp_root) as tmp:
        info(f"Rendering {len(selected)} page(s) at {args.dpi} DPI…")
        rendered = _render(pdf_path, selected, args.dpi, Path(tmp))
        rendered = _downscale_oversize(pdf_path, rendered, args.max_bytes, Path(tmp))

        info("Stitching pages into chunks…")
        chunks, oversize_idx = _stitch_and_grow(rendered, args.max_bytes)
        info(f"Built {len(chunks)} chunk(s)")
        if oversize_idx:
            warn(
                f"{len(oversize_idx)} chunk(s) still exceed {args.max_bytes} bytes; "
                f"the image-understanding tool may reject them."
            )

        out_dir = Path(args.output_dir) if args.output_dir else _default_output_dir(pdf_path, selected, args.dpi)
        chunk_results = _write_chunk_images(out_dir, chunks)
        if args.keep_pages:
            _dump_keep_tmp(out_dir / "debug-pages", rendered, chunks)
        info(f"Wrote chunk images to {out_dir}")

    result = {
        "mode": "vision",
        "file": str(pdf_path),
        "pageCount": total_pages,
        "selectedPages": selected,
        "dpi": args.dpi,
        "prompt": args.prompt,
        "instruction": "Call the agent runtime image-understanding tool once per chunk imagePath, using prompt as the per-image question. Do not call a separate CLI, daemon, or hand-written tool endpoint.",
        "chunks": chunk_results,
    }

    if args.json:
        emit(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            "json",
            args.max_stdout_bytes,
        )
        return

    sel_spec = format_pages(selected)
    out_lines: list[str] = [
        f"# {pdf_path.name}",
        "",
        f"> {total_pages} pages • selected {sel_spec} • {len(chunk_results)} image chunk(s) @ {args.dpi} DPI",
        "",
        "Use the agent runtime image-understanding tool on each chunk below. Do not call a separate CLI, daemon, or hand-written tool endpoint.",
        "",
        f"Prompt: {args.prompt}",
        "",
    ]
    for i, c in enumerate(chunk_results, 1):
        out_lines.append(f"## Chunk {i}/{len(chunk_results)} — pages {format_pages(c['pages'])}")
        out_lines.append("")
        out_lines.append(f"Image: `{c['imagePath']}`")
        out_lines.append(f"Size: {c['width']}×{c['height']} px, {c['sizeBytes']} bytes")
        out_lines.append("")
        out_lines.append("---")
        out_lines.append("")
    emit("\n".join(out_lines), "md", args.max_stdout_bytes)


if __name__ == "__main__":
    main()
