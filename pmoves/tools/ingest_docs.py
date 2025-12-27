#!/usr/bin/env python3
"""
Batch ingestion script for PMOVES documentation.

Reads markdown files from the repo and ingests them into the Extract-Worker
for indexing in Qdrant (vectors) and Meilisearch (full-text).

Usage:
    python ingest_docs.py [--dry-run] [--priority-only]

Options:
    --dry-run       Print files that would be ingested without sending
    --priority-only Only ingest priority files (CLAUDE.md, context/*.md, etc.)
"""

import os
import sys
import json
import hashlib
import argparse
import requests
from pathlib import Path
from typing import List, Dict, Any

EXTRACT_WORKER_URL = os.environ.get("EXTRACT_WORKER_URL", "http://localhost:8083")
REPO_ROOT = Path(__file__).parent.parent.parent  # /home/pmoves/PMOVES.AI

# Priority files for initial ingestion
PRIORITY_PATTERNS = [
    ".claude/CLAUDE.md",
    ".claude/README.md",
    ".claude/context/*.md",
    ".claude/learnings/*.md",
    "pmoves/docs/FIRST_RUN.md",
    "pmoves/docs/ROADMAP.md",
    "pmoves/docs/PMOVESCHIT/*.md",
    "pmoves/docs/services/README.md",
    "pmoves/docs/services/*/README.md",
    "docs/*.md",
    "docs/architecture/*.md",
    "docs/testing/*.md",
]

# Directories to exclude
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".next",
}


def chunk_markdown(content: str, max_chunk_size: int = 2000) -> List[str]:
    """Split markdown content into chunks, respecting section boundaries."""
    lines = content.split("\n")
    chunks = []
    current_chunk = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1  # +1 for newline

        # Start new chunk on headers if current chunk is getting large
        if line.startswith("#") and current_size > max_chunk_size // 2:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_size = line_size
        # Start new chunk if we exceed max size
        elif current_size + line_size > max_chunk_size:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size

    # Don't forget the last chunk
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return [c for c in chunks if c.strip()]


def generate_chunk_id(file_path: str, chunk_index: int) -> str:
    """Generate a deterministic chunk ID from file path and index."""
    combined = f"{file_path}:{chunk_index}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def find_priority_files(repo_root: Path) -> List[Path]:
    """Find files matching priority patterns."""
    files = []
    for pattern in PRIORITY_PATTERNS:
        matches = list(repo_root.glob(pattern))
        files.extend(matches)
    return sorted(set(files))


def find_all_markdown_files(repo_root: Path) -> List[Path]:
    """Find all markdown files, excluding dependency directories."""
    files = []
    for md_file in repo_root.rglob("*.md"):
        # Skip excluded directories
        if any(excl in md_file.parts for excl in EXCLUDE_DIRS):
            continue
        files.append(md_file)
    return sorted(files)


def ingest_file(file_path: Path, repo_root: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Ingest a single markdown file."""
    relative_path = file_path.relative_to(repo_root)

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"file": str(relative_path), "error": str(e), "chunks_sent": 0}

    if not content.strip():
        return {"file": str(relative_path), "skipped": "empty", "chunks_sent": 0}

    # Chunk the content
    text_chunks = chunk_markdown(content)

    # Prepare chunks for Extract-Worker
    chunks = []
    for i, text in enumerate(text_chunks):
        chunk_id = generate_chunk_id(str(relative_path), i)
        chunks.append({
            "chunk_id": chunk_id,
            "text": text,
            "namespace": "pmoves-docs",
            "source": str(relative_path),
            "source_type": "markdown",
            "chunk_index": i,
            "total_chunks": len(text_chunks),
        })

    if dry_run:
        return {
            "file": str(relative_path),
            "chunks_prepared": len(chunks),
            "dry_run": True,
        }

    # Send to Extract-Worker
    try:
        response = requests.post(
            f"{EXTRACT_WORKER_URL}/ingest",
            json={"chunks": chunks, "errors": []},
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        return {
            "file": str(relative_path),
            "chunks_sent": result.get("chunks", len(chunks)),
            "ok": result.get("ok", True),
        }
    except requests.exceptions.RequestException as e:
        return {"file": str(relative_path), "error": str(e), "chunks_sent": 0}


def main():
    parser = argparse.ArgumentParser(description="Ingest PMOVES documentation")
    parser.add_argument("--dry-run", action="store_true", help="Print without ingesting")
    parser.add_argument("--priority-only", action="store_true", help="Only priority files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    repo_root = REPO_ROOT

    if args.priority_only:
        files = find_priority_files(repo_root)
        print(f"Found {len(files)} priority files")
    else:
        files = find_all_markdown_files(repo_root)
        print(f"Found {len(files)} markdown files")

    if not files:
        print("No files to ingest")
        return

    # Check Extract-Worker health
    if not args.dry_run:
        try:
            r = requests.get(f"{EXTRACT_WORKER_URL}/healthz", timeout=5)
            r.raise_for_status()
            print(f"Extract-Worker healthy at {EXTRACT_WORKER_URL}")
        except Exception as e:
            print(f"ERROR: Extract-Worker not reachable: {e}")
            sys.exit(1)

    # Process files
    total_chunks = 0
    errors = 0

    for i, file_path in enumerate(files, 1):
        result = ingest_file(file_path, repo_root, dry_run=args.dry_run)

        if result.get("error"):
            errors += 1
            print(f"[{i}/{len(files)}] ERROR {result['file']}: {result['error']}")
        elif result.get("skipped"):
            if args.verbose:
                print(f"[{i}/{len(files)}] SKIP {result['file']}: {result['skipped']}")
        else:
            chunks = result.get("chunks_sent") or result.get("chunks_prepared", 0)
            total_chunks += chunks
            print(f"[{i}/{len(files)}] OK {result['file']} ({chunks} chunks)")

    # Summary
    print()
    print("=" * 60)
    if args.dry_run:
        print(f"DRY RUN: Would ingest {len(files)} files ({total_chunks} chunks)")
    else:
        print(f"Ingested {len(files)} files ({total_chunks} chunks), {errors} errors")


if __name__ == "__main__":
    main()
