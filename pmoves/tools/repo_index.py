#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            text = (obj.get("text") or obj.get("content") or "").strip()
            if not text:
                continue
            # Normalize shape expected by extract-worker
            chunks.append(
                {
                    "chunk_id": obj.get("chunk_id") or obj.get("id") or obj.get("doc_id"),
                    "doc_id": obj.get("doc_id") or obj.get("document_id") or "doc",
                    "section_id": obj.get("section_id") or obj.get("section") or "sec",
                    "namespace": obj.get("namespace"),
                    "text": text,
                }
            )
    return chunks


def main() -> int:
    ap = argparse.ArgumentParser(description="Index a JSONL into extract-worker (Qdrant + Meili).")
    ap.add_argument("--jsonl", required=True, help="Path to JSONL produced by repo_crawl.py")
    host_port = os.environ.get("EXTRACT_WORKER_HOST_PORT", "8083")
    ap.add_argument(
        "--extract-url",
        default=os.environ.get("EXTRACT_WORKER_INGEST_URL", f"http://localhost:{host_port}/ingest"),
        help="Extract-worker ingest URL (default: http://localhost:${EXTRACT_WORKER_HOST_PORT:-8083}/ingest)",
    )
    ap.add_argument("--batch-size", type=int, default=250, help="Chunks per request")
    ap.add_argument(
        "--timeout-secs",
        type=int,
        default=int(os.environ.get("EXTRACT_WORKER_INGEST_TIMEOUT_SECS", "600")),
        help="HTTP timeout per ingest request (default: 600)",
    )
    ap.add_argument(
        "--max-chunks",
        type=int,
        default=0,
        help="Maximum number of chunks to index (0 = all). Useful for quick smoke runs.",
    )
    args = ap.parse_args()

    jsonl_path = Path(args.jsonl)
    chunks = _iter_jsonl(jsonl_path)
    if not chunks:
        print("no chunks parsed; nothing to index")
        return 1
    if args.max_chunks and args.max_chunks > 0:
        chunks = chunks[: args.max_chunks]

    url = args.extract_url
    ok_total = 0
    for i in range(0, len(chunks), args.batch_size):
        batch = chunks[i : i + args.batch_size]
        print(f"sending batch {i//args.batch_size+1} ({i+1}-{min(i+len(batch), len(chunks))}/{len(chunks)}) → {url}", flush=True)
        resp = requests.post(url, json={"chunks": batch}, timeout=args.timeout_secs)
        resp.raise_for_status()
        data = resp.json()
        ok_total += int(data.get("chunks") or 0)
        print(f"indexed batch {i//args.batch_size+1}: {data}")

    print(f"indexed {ok_total} total chunks into extract-worker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
