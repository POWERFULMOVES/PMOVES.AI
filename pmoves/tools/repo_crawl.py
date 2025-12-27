#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


DEFAULT_EXTENSIONS = (
    ".md",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "playwright-browsers",
    "playwright-deps",
    "data",
    "tmp",
}

_GITMODULES_PATH_RE = re.compile(r"^\s*path\s*=\s*(?P<path>.+?)\s*$")


@dataclass(frozen=True)
class DocChunk:
    doc_id: str
    section_id: str
    chunk_id: str
    namespace: str
    text: str

    def to_json(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "section_id": self.section_id,
            "chunk_id": self.chunk_id,
            "namespace": self.namespace,
            "text": self.text,
        }


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize excessive blank lines.
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()

def _load_git_submodule_paths(repo_root: Path) -> set[str]:
    """
    Best-effort parse of .gitmodules to avoid crawling large submodule trees.

    Returns a set of submodule paths as posix strings (relative to repo_root).
    """
    gitmodules = repo_root / ".gitmodules"
    if not gitmodules.exists():
        return set()
    try:
        raw = gitmodules.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    out: set[str] = set()
    for line in raw.splitlines():
        m = _GITMODULES_PATH_RE.match(line)
        if not m:
            continue
        p = m.group("path").strip().strip('"').strip("'")
        if not p:
            continue
        out.add(p.replace("\\", "/").rstrip("/"))
    return out


def _iter_files(
    root: Path,
    extensions: tuple[str, ...],
    max_bytes: int,
    *,
    skip_submodules: bool,
) -> Iterator[Path]:
    submodules = _load_git_submodule_paths(root) if skip_submodules else set()
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        # Prune
        if submodules:
            try:
                rel_dp = dp.resolve().relative_to(root.resolve()).as_posix()
            except Exception:
                rel_dp = ""
        else:
            rel_dp = ""

        pruned: list[str] = []
        for d in dirnames:
            if d in SKIP_DIRS or d.startswith(".git"):
                continue
            if submodules:
                child_rel = d if not rel_dp else f"{rel_dp}/{d}"
                if child_rel in submodules:
                    continue
            pruned.append(d)
        dirnames[:] = pruned
        for fn in filenames:
            p = dp / fn
            if p.suffix.lower() not in extensions:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size <= 0 or st.st_size > max_bytes:
                continue
            yield p


def _chunk_text(text: str, *, max_chars: int, overlap_chars: int) -> Iterator[str]:
    text = _clean_text(text)
    if not text:
        return

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    buf: list[str] = []
    size = 0

    def flush() -> str:
        nonlocal buf, size
        out = "\n\n".join(buf).strip()
        buf = []
        size = 0
        return out

    for para in paragraphs:
        if not para:
            continue

        # If a single paragraph is huge, hard-split it.
        if len(para) > max_chars:
            if buf:
                yield flush()
            stride = max(1, max_chars - max(0, overlap_chars))
            for start in range(0, len(para), stride):
                end = min(len(para), start + max_chars)
                yield para[start:end].strip()
            continue

        if size + len(para) + (2 if buf else 0) > max_chars:
            out = flush()
            if out:
                yield out

        buf.append(para)
        size += len(para)

    out = flush()
    if out:
        yield out


def _read_text(path: Path) -> str:
    # Best-effort: prefer utf-8, fall back to latin-1 to avoid dropping files.
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def build_chunks(
    *,
    root: Path,
    namespace: str,
    extensions: tuple[str, ...],
    max_bytes: int,
    max_chars: int,
    overlap_chars: int,
    skip_submodules: bool = True,
    include: tuple[str, ...] = (),
    max_files: int = 0,
    progress_every_files: int = 0,
) -> Iterable[DocChunk]:
    base = root.resolve()
    if include:
        include_paths = [base / p for p in include]
    else:
        include_paths = [base]

    files_processed = 0
    for inc in include_paths:
        if not inc.exists():
            continue
        if inc.is_file():
            paths = [inc]
        else:
            paths = _iter_files(
                inc,
                extensions=extensions,
                max_bytes=max_bytes,
                skip_submodules=skip_submodules,
            )

        for path in paths:
            files_processed += 1
            if max_files and files_processed > max_files:
                return
            if progress_every_files and files_processed % progress_every_files == 0:
                print(f"[repo_crawl] processed {files_processed} files...", flush=True)
            try:
                rel = str(path.resolve().relative_to(base)).replace("\\", "/")
            except Exception:
                continue
            raw = _read_text(path)
            for idx, chunk in enumerate(
                _chunk_text(raw, max_chars=max_chars, overlap_chars=overlap_chars),
                start=1,
            ):
                section_id = f"s{idx:04d}"
                chunk_id = f"{rel}#{section_id}"
                yield DocChunk(
                    doc_id=rel,
                    section_id=section_id,
                    chunk_id=chunk_id,
                    namespace=namespace,
                    text=chunk,
                )


def main() -> int:
    ap = argparse.ArgumentParser(description="Crawl repo docs/code into a JSONL file for indexing.")
    ap.add_argument("--root", required=True, help="Repository root to crawl")
    ap.add_argument("--out", required=True, help="Output JSONL file path")
    ap.add_argument("--namespace", default="pmoves.docs", help="Namespace for emitted chunks")
    ap.add_argument(
        "--ext",
        action="append",
        default=list(DEFAULT_EXTENSIONS),
        help=f"File extension to include (repeatable). Default: {', '.join(DEFAULT_EXTENSIONS)}",
    )
    ap.add_argument("--max-bytes", type=int, default=512 * 1024, help="Skip files larger than this (bytes)")
    ap.add_argument("--max-chars", type=int, default=2000, help="Max chars per chunk")
    ap.add_argument("--overlap-chars", type=int, default=200, help="Overlap chars for hard-splits")
    ap.add_argument(
        "--include-submodules",
        action="store_true",
        help="Include git submodules (default: skip them for speed)",
    )
    ap.add_argument(
        "--include",
        action="append",
        default=[],
        help="Relative path to include (repeatable). If set, only these subtrees are crawled.",
    )
    ap.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Maximum number of files to process (0 = unlimited).",
    )
    ap.add_argument(
        "--progress-every-files",
        type=int,
        default=0,
        help="Print a progress line every N files (0 = disabled).",
    )
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    extensions = tuple(e if e.startswith(".") else f".{e}" for e in args.ext)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for chunk in build_chunks(
            root=root,
            namespace=args.namespace,
            extensions=extensions,
            max_bytes=args.max_bytes,
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
            skip_submodules=(not args.include_submodules),
            include=tuple(args.include),
            max_files=args.max_files,
            progress_every_files=args.progress_every_files,
        ):
            fh.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")
            n += 1

    print(f"wrote {n} chunks to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
