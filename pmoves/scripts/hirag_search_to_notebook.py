#!/usr/bin/env python3
"""
Send Hi-RAG search hits to Open Notebook.

For each query we call POST /hirag/query, dedupe the resulting chunks, and
mirror them into Notebook sources (link/text) using the shared ingestion helper.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set

import requests

from notebook_ingest_utils import NotebookClient, NotebookSource

DEFAULT_HIRAG = os.environ.get("HIRAG_URL", "http://localhost:8086")
DEFAULT_NAMESPACE = os.environ.get("INDEXER_NAMESPACE", "pmoves")
DEFAULT_NOTEBOOK_API = os.environ.get("OPEN_NOTEBOOK_API_URL", "http://localhost:5055")
DEFAULT_NOTEBOOK_ID = os.environ.get("HIRAG_NOTEBOOK_ID") or os.environ.get("MINDMAP_NOTEBOOK_ID")


def _require(name: str, value: Optional[str]) -> str:
    if value:
        return value
    sys.stderr.write(f"ERROR: {name} must be set via env or CLI.\n")
    sys.exit(2)


def _load_queries(args_queries: Sequence[str], queries_file: Optional[str]) -> List[str]:
    queries: List[str] = list(args_queries)
    if queries_file:
        with open(queries_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    queries.append(line)
    if not queries:
        sys.stderr.write("Provide at least one --query or --queries-file entry.\n")
        sys.exit(2)
    return queries


def _doc_url_from_payload(payload: Dict[str, object]) -> Optional[str]:
    ref_id = payload.get("ref_id") or (payload.get("payload") or {}).get("ref_id")
    if isinstance(ref_id, str) and ref_id.startswith("yt:"):
        vid = ref_id.split(":", 1)[1] or ref_id
        return f"https://youtube.com/watch?v={vid}"
    doc_id = payload.get("doc_id") or payload.get("chunk_id")
    if isinstance(doc_id, str) and doc_id.startswith("yt:"):
        vid = doc_id.split(":", 1)[1]
        return f"https://youtube.com/watch?v={vid}"
    url = payload.get("url")
    return str(url) if isinstance(url, str) else None


def hirag_query(
    base: str,
    query: str,
    namespace: str,
    k: int,
    alpha: float,
    use_rerank: Optional[bool] = None,
) -> Dict[str, object]:
    payload: Dict[str, object] = {"query": query, "namespace": namespace, "k": k, "alpha": alpha}
    if use_rerank is not None:
        payload["use_rerank"] = use_rerank
    resp = requests.post(f"{base.rstrip('/')}/hirag/query", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_sources_from_hits(
    hits: Iterable[Dict[str, object]],
    notebook_id: str,
    embed: bool,
    async_processing: bool,
    title_prefix: Optional[str],
) -> List[NotebookSource]:
    sources: List[NotebookSource] = []
    for hit in hits:
        payload = hit.get("payload") or {}
        text = str(hit.get("text") or payload.get("text") or "").strip()
        if not text:
            continue
        url = _doc_url_from_payload(payload)
        chunk_id = str(payload.get("chunk_id") or hit.get("chunk_id") or hit.get("id") or "")
        title = text.split("\n", 1)[0][:160] if text else (url or chunk_id or "Hi-RAG Chunk")
        if title_prefix:
            title = f"{title_prefix} · {title}"
        source_type = "link" if url else "text"
        sources.append(
            NotebookSource(
                title=title,
                source_type=source_type,
                notebooks=[notebook_id],
                url=url,
                content=text,
                embed=embed,
                async_processing=async_processing,
            )
        )
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Hi-RAG search hits into Open Notebook")
    parser.add_argument("--hirag", default=DEFAULT_HIRAG, help="Hi-RAG base URL")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE, help="Hi-RAG namespace")
    parser.add_argument("--k", type=int, default=25, help="Hits per query")
    parser.add_argument("--alpha", type=float, default=0.7, help="Hybrid alpha value")
    parser.add_argument("--query", action="append", default=[], help="Query string (repeatable)")
    parser.add_argument("--queries-file", help="Path to newline-delimited queries")
    parser.add_argument("--title-prefix", help="Optional prefix appended to each Notebook title")
    parser.add_argument("--api", default=DEFAULT_NOTEBOOK_API, help="Open Notebook API base URL")
    parser.add_argument("--token", default=os.environ.get("OPEN_NOTEBOOK_API_TOKEN"), help="Notebook API token")
    parser.add_argument("--notebook-id", default=DEFAULT_NOTEBOOK_ID, help="Target Notebook ID")
    parser.add_argument("--embed", dest="embed", action="store_true", help="Embed content during creation")
    parser.add_argument("--no-embed", dest="embed", action="store_false")
    parser.set_defaults(embed=True)
    parser.add_argument("--async-processing", action="store_true", help="Use async processing in Notebook")
    parser.add_argument("--max-items", type=int, default=0, help="Cap total creations (0 = unlimited)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without calling APIs")
    args = parser.parse_args()

    notebook_id = _require("HIRAG_NOTEBOOK_ID or MINDMAP_NOTEBOOK_ID", args.notebook_id)
    token = _require("OPEN_NOTEBOOK_API_TOKEN", args.token)
    queries = _load_queries(args.query, args.queries_file)

    client = NotebookClient(args.api, token)
    existing = client.fetch_existing_keys(notebook_id)

    processed = created = skipped = 0
    remaining_cap = args.max_items if args.max_items > 0 else None

    for query in queries:
        if remaining_cap is not None and remaining_cap <= 0:
            break
        resp = hirag_query(args.hirag, query, args.namespace, args.k, args.alpha)
        hits = resp.get("hits") or []
        sources = build_sources_from_hits(
            hits,
            notebook_id,
            args.embed,
            args.async_processing,
            args.title_prefix or query if len(queries) > 1 else args.title_prefix,
        )
        for source in sources:
            processed += 1
            dedupe_key = source.dedupe_key()
            if dedupe_key in existing:
                skipped += 1
                continue
            if args.dry_run:
                sys.stdout.write(f"DRY-RUN would create {source}\n")
                created += 1
                existing.add(dedupe_key)
            else:
                try:
                    new_id = client.create_source(source)
                    created += 1
                    existing.add(dedupe_key)
                    sys.stdout.write(f"[{query}] created {new_id} ({source.title})\n")
                except Exception as exc:  # pylint: disable=broad-except
                    skipped += 1
                    sys.stderr.write(f"WARN: failed to create source ({exc})\n")
            if remaining_cap is not None:
                remaining_cap -= 1
                if remaining_cap <= 0:
                    break

    sys.stdout.write(
        f"Hi-RAG sync complete: processed={processed}, created={created}, skipped={skipped}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
