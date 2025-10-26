#!/usr/bin/env python3
"""
Sync mindmap entries into Open Notebook as sources.

Relies on:
  - /mindmap/{constellation_id} for enriched geometry points
  - Open Notebook `/api/sources/json` for ingestion
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Optional

import requests

from notebook_ingest_utils import NotebookClient, NotebookSource

DEFAULT_MINDMAP_BASE = os.environ.get("MINDMAP_BASE", "http://localhost:8086")
DEFAULT_NOTEBOOK_API = os.environ.get("OPEN_NOTEBOOK_API_URL", "http://localhost:5055")
DEFAULT_CONSTELLATION = os.environ.get("MINDMAP_CONSTELLATION_ID")
DEFAULT_NOTEBOOK_ID = os.environ.get("MINDMAP_NOTEBOOK_ID")
DEFAULT_MODALITIES = os.environ.get("MINDMAP_MODALITIES", "text,video,audio,doc,image")


def _require(name: str, value: Optional[str]) -> str:
    if value:
        return value
    sys.stderr.write(f"ERROR: {name} must be set via env or CLI.\n")
    sys.exit(2)


def fetch_mindmap_items(
    base: str,
    constellation_id: str,
    modalities: str,
    limit: int,
    offset: int,
    min_proj: float,
    min_conf: float,
) -> Dict[str, object]:
    url = f"{base.rstrip('/')}/mindmap/{constellation_id}"
    params = {
        "modalities": modalities,
        "limit": limit,
        "offset": offset,
        "minProj": min_proj,
        "minConf": min_conf,
        "enrich": "true",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_source(item: Dict[str, object], notebook_id: str, embed: bool, async_processing: bool) -> Optional[NotebookSource]:
    point = item.get("point") or {}
    media_url = item.get("media_url") or (item.get("media") or {}).get("url")
    title = str(point.get("text") or point.get("id") or "Mindmap Node").strip()[:200]
    if not title:
        title = "Mindmap Node"
    text_content = str(point.get("text") or "").strip()

    if media_url:
        return NotebookSource(
            title=title,
            source_type="link",
            notebooks=[notebook_id],
            url=str(media_url),
            content=text_content or None,
            embed=embed,
            async_processing=async_processing,
        )
    if text_content:
        return NotebookSource(
            title=title,
            source_type="text",
            notebooks=[notebook_id],
            content=text_content,
            embed=embed,
            async_processing=async_processing,
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync mindmap entries into Open Notebook sources")
    parser.add_argument("--base", default=DEFAULT_MINDMAP_BASE, help="Mindmap base URL")
    parser.add_argument("--cid", default=DEFAULT_CONSTELLATION, help="Constellation ID")
    parser.add_argument("--modalities", default=DEFAULT_MODALITIES, help="Modalities filter")
    parser.add_argument("--min-proj", type=float, default=0.5)
    parser.add_argument("--min-conf", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=100, help="page size while fetching mindmap data")
    parser.add_argument("--max-items", type=int, default=0, help="Stop after syncing this many entries (0 = no cap)")
    parser.add_argument("--offset", type=int, default=0, help="Initial mindmap offset")
    parser.add_argument("--notebook-id", default=DEFAULT_NOTEBOOK_ID, help="Target Open Notebook ID")
    parser.add_argument("--api", default=DEFAULT_NOTEBOOK_API, help="Open Notebook API base")
    parser.add_argument("--token", default=os.environ.get("OPEN_NOTEBOOK_API_TOKEN"), help="Notebook API token")
    parser.add_argument("--embed", dest="embed", action="store_true", help="Request embeddings during source creation")
    parser.add_argument("--no-embed", dest="embed", action="store_false")
    parser.set_defaults(embed=True)
    parser.add_argument("--async-processing", action="store_true", help="Let Notebook queue processing jobs")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without calling the Notebook API")
    args = parser.parse_args()

    constellation_id = _require("MINDMAP_CONSTELLATION_ID", args.cid)
    notebook_id = _require("MINDMAP_NOTEBOOK_ID", args.notebook_id)
    token = _require("OPEN_NOTEBOOK_API_TOKEN", args.token)

    mindmap_base = args.base.rstrip("/")
    client = NotebookClient(args.api, token)
    existing = client.fetch_existing_keys(notebook_id)

    processed = created = skipped = 0
    offset = args.offset
    remaining_cap = args.max_items if args.max_items > 0 else None

    while True:
        page_limit = args.limit
        if remaining_cap is not None and remaining_cap < page_limit:
            page_limit = remaining_cap
        if page_limit <= 0:
            break

        payload = fetch_mindmap_items(
            mindmap_base,
            constellation_id,
            args.modalities,
            page_limit,
            offset,
            args.min_proj,
            args.min_conf,
        )
        items = payload.get("items") or []
        if not items:
            break

        for item in items:
            processed += 1
            source = build_source(item, notebook_id, args.embed, args.async_processing)
            if not source:
                skipped += 1
                continue
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
                    sys.stdout.write(f"Created source {new_id} ({source.title})\n")
                except Exception as exc:  # pylint: disable=broad-except
                    skipped += 1
                    sys.stderr.write(f"WARN: failed to create source ({exc})\n")
            if remaining_cap is not None:
                remaining_cap -= 1
                if remaining_cap <= 0:
                    break
        offset += payload.get("returned") or len(items)
        if remaining_cap is not None and remaining_cap <= 0:
            break
        if not payload.get("has_more"):
            break

    sys.stdout.write(
        f"Mindmap sync complete: processed={processed}, created={created}, skipped={skipped}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
