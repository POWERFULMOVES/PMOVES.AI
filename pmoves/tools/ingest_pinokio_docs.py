#!/usr/bin/env python3
"""
Ingest Pinokio documentation into Hi-RAG via Extract-Worker.

Reads PINOKIO.md (~6500 lines), splits into hierarchical chunks that
respect section boundaries and code blocks, then sends to Extract-Worker
for indexing into Qdrant (vectors) and Meilisearch (full-text).

Usage:
    python ingest_pinokio_docs.py [--dry-run] [--pinokio-path PATH] [--force]

Options:
    --dry-run         Print chunks without sending to Extract-Worker
    --pinokio-path    Path to PINOKIO.md (default: D:/pinokio/prototype/PINOKIO.md)
    --force           Re-ingest even if content hash unchanged
"""

import os
import sys
import json
import hashlib
import argparse
import re
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple

EXTRACT_WORKER_URL = os.environ.get("EXTRACT_WORKER_URL", "http://localhost:8083")
DEFAULT_PINOKIO_PATH = Path("D:/pinokio/prototype/PINOKIO.md")
HASH_FILE = Path(__file__).parent / ".pinokio-docs-hash"
NAMESPACE = "pinokio-docs"
SOURCE = "PINOKIO.md"
MAX_CHUNK_SIZE = 3000  # chars — large enough for most code blocks


def generate_chunk_id(section_path: str, chunk_index: int) -> str:
    """Generate a deterministic chunk ID from section path and index."""
    combined = f"{NAMESPACE}:{section_path}:{chunk_index}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def content_hash(content: str) -> str:
    """SHA-256 hash of file content for change detection."""
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def is_code_fence(line: str) -> bool:
    """Check if line is a markdown code fence (``` or ~~~)."""
    stripped = line.strip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def heading_level(line: str) -> int:
    """Return heading level (1-6) or 0 if not a heading."""
    match = re.match(r"^(#{1,6})\s", line)
    return len(match.group(1)) if match else 0


def extract_section_path(headings_stack: List[str]) -> str:
    """Build a section path like 'API > shell.run > params'."""
    return " > ".join(headings_stack) if headings_stack else "root"


def chunk_markdown_hierarchical(content: str) -> List[Dict[str, Any]]:
    """
    Split markdown into chunks that respect:
    1. Section boundaries (## then ### then #### headers)
    2. Code block integrity (never split mid-code-block)
    3. Paragraph boundaries as last resort
    4. MAX_CHUNK_SIZE as the soft limit

    Returns list of dicts with 'text', 'section_path', 'chunk_index'.
    """
    lines = content.split("\n")
    chunks = []
    current_lines = []
    current_size = 0
    headings_stack = []  # tracks [h1, h2, h3, ...] for section_path
    in_code_block = False
    chunk_index = 0

    def flush_chunk():
        nonlocal current_lines, current_size, chunk_index
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                chunks.append({
                    "text": text,
                    "section_path": extract_section_path(headings_stack),
                    "chunk_index": chunk_index,
                })
                chunk_index += 1
            current_lines = []
            current_size = 0

    for line in lines:
        line_size = len(line) + 1  # +1 for newline

        # Track code fences — never split inside a code block
        if is_code_fence(line):
            in_code_block = not in_code_block
            current_lines.append(line)
            current_size += line_size
            continue

        if in_code_block:
            current_lines.append(line)
            current_size += line_size
            continue

        # Check for heading
        level = heading_level(line)
        if level > 0:
            heading_text = line.lstrip("#").strip()

            # ## header (level 2) — always starts a new chunk
            if level <= 2:
                flush_chunk()
                # Reset stack to this level
                headings_stack = headings_stack[:max(0, level - 1)]
                if len(headings_stack) < level:
                    headings_stack.append(heading_text)
                else:
                    headings_stack[level - 1] = heading_text
                current_lines = [line]
                current_size = line_size
                continue

            # ### or #### header — new chunk if current is large enough
            if current_size > MAX_CHUNK_SIZE // 2:
                flush_chunk()

            # Update headings stack
            while len(headings_stack) >= level:
                headings_stack.pop()
            headings_stack.append(heading_text)

            current_lines.append(line)
            current_size += line_size
            continue

        # Regular line — check if we need to split
        if current_size + line_size > MAX_CHUNK_SIZE:
            # Try to split at paragraph boundary (blank line)
            if line.strip() == "" and current_lines:
                flush_chunk()
                continue
            # If the chunk is really large, force split at this line
            if current_size > MAX_CHUNK_SIZE * 1.5:
                flush_chunk()

        current_lines.append(line)
        current_size += line_size

    # Flush remaining
    flush_chunk()

    return chunks


def ingest_chunks(
    chunks: List[Dict[str, Any]],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Send chunks to Extract-Worker."""
    payloads = []
    for chunk in chunks:
        chunk_id = generate_chunk_id(chunk["section_path"], chunk["chunk_index"])
        payloads.append({
            "chunk_id": chunk_id,
            "text": chunk["text"],
            "namespace": NAMESPACE,
            "source": SOURCE,
            "source_type": "markdown",
            "section_path": chunk["section_path"],
            "chunk_index": chunk["chunk_index"],
            "total_chunks": len(chunks),
        })

    if dry_run:
        return {"chunks_prepared": len(payloads), "dry_run": True}

    # Send in batches of 20 to avoid overwhelming the worker
    batch_size = 20
    total_sent = 0
    errors = 0

    for i in range(0, len(payloads), batch_size):
        batch = payloads[i : i + batch_size]
        try:
            response = requests.post(
                f"{EXTRACT_WORKER_URL}/ingest",
                json={"chunks": batch, "errors": []},
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            sent = result.get("chunks", len(batch))
            total_sent += sent
            print(f"  Batch {i // batch_size + 1}: {sent} chunks indexed")
        except requests.exceptions.RequestException as e:
            errors += 1
            print(f"  Batch {i // batch_size + 1}: ERROR — {e}")

    return {"chunks_sent": total_sent, "errors": errors}


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Pinokio documentation into Hi-RAG"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without ingesting")
    parser.add_argument(
        "--pinokio-path",
        type=Path,
        default=DEFAULT_PINOKIO_PATH,
        help="Path to PINOKIO.md",
    )
    parser.add_argument("--force", action="store_true", help="Re-ingest even if unchanged")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show chunk details")
    args = parser.parse_args()

    # ── Locate source file ──
    if not args.pinokio_path.exists():
        print(f"ERROR: PINOKIO.md not found at {args.pinokio_path}")
        print("Use --pinokio-path to specify the correct location.")
        sys.exit(1)

    print(f"Source: {args.pinokio_path}")
    print(f"Target: {EXTRACT_WORKER_URL}/ingest (namespace: {NAMESPACE})")

    # ── Read content ──
    content = args.pinokio_path.read_text(encoding="utf-8", errors="ignore")
    print(f"File size: {len(content):,} chars, {content.count(chr(10)):,} lines")

    # ── Check hash for change detection ──
    current_hash = content_hash(content)
    if not args.force and HASH_FILE.exists():
        stored_hash = HASH_FILE.read_text().strip()
        if stored_hash == current_hash:
            print("Content unchanged since last ingestion. Use --force to re-ingest.")
            return

    # ── Chunk ──
    print("\nChunking with hierarchical section boundaries...")
    chunks = chunk_markdown_hierarchical(content)
    print(f"Generated {len(chunks)} chunks")

    if args.verbose:
        print("\n── Chunk Summary ──")
        for c in chunks:
            preview = c["text"][:80].replace("\n", " ")
            print(f"  [{c['chunk_index']:3d}] {c['section_path'][:50]:50s} | {len(c['text']):5d} chars | {preview}...")

    # ── Health check ──
    if not args.dry_run:
        try:
            r = requests.get(f"{EXTRACT_WORKER_URL}/healthz", timeout=5)
            r.raise_for_status()
            print(f"\nExtract-Worker healthy at {EXTRACT_WORKER_URL}")
        except Exception as e:
            print(f"\nERROR: Extract-Worker not reachable at {EXTRACT_WORKER_URL}: {e}")
            print("Start the extract-worker service first, or use --dry-run.")
            sys.exit(1)

    # ── Ingest ──
    print("\nIngesting...")
    result = ingest_chunks(chunks, dry_run=args.dry_run)

    if args.dry_run:
        print(f"\nDRY RUN: Would ingest {result['chunks_prepared']} chunks")
    else:
        print(f"\nIngested {result['chunks_sent']} chunks, {result['errors']} errors")

        # Save hash on success
        if result["errors"] == 0:
            HASH_FILE.write_text(current_hash)
            print(f"Content hash saved to {HASH_FILE}")

    print("\n" + "=" * 60)
    print("Done. Query with:")
    print('  curl -X POST http://localhost:8086/hirag/query \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"query": "pinokio LAN-Wide-Web", "top_k": 5, "namespace": "pinokio-docs"}\'')


if __name__ == "__main__":
    main()
