#!/usr/bin/env python3
"""
Backfill Jellyfin metadata and republish `content.published.v1` events.

Integrates with PMOVES.yt YouTube transcript corpus for semantic content linking.

Usage examples:
  python pmoves/scripts/backfill_jellyfin_metadata.py --limit 5 --dry-run
  python pmoves/scripts/backfill_jellyfin_metadata.py --limit 10 --sleep 1.5 --link-youtube
  python pmoves/scripts/backfill_jellyfin_metadata.py --limit 25 --youtube-threshold 0.75
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import httpx
except ImportError as exc:  # pragma: no cover - easy failure mode
    raise SystemExit(
        "httpx is required for the Jellyfin backfill script. Install it via "
        "`pip install httpx` inside your PMOVES environment."
    ) from exc

try:
    from services.common.events import envelope
except Exception as exc:  # pragma: no cover
    raise SystemExit("Unable to import services.common.events.envelope") from exc

from services.publisher.publisher import build_published_payload, slugify


BACKFILL_VERSION = "2025-10-17"
DEFAULT_LIMIT = 10
JELLYFIN_IMAGE_ROUTE = "/Items/{item_id}/Images/Primary?tag={tag}"
YOUTUBE_SIMILARITY_THRESHOLD = 0.70
PMOVES_YT_BASE_URL = "http://localhost:8077"


def load_env() -> Dict[str, str]:
    env = {
        "SUPA_REST_URL": os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_REST_URL"),
        "SUPABASE_SERVICE_ROLE_KEY": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        "AGENT_ZERO_BASE_URL": os.environ.get("AGENT_ZERO_BASE_URL", "http://localhost:8080").rstrip("/"),
        "PMOVES_YT_URL": os.environ.get("PMOVES_YT_URL", "http://localhost:8077").rstrip("/"),
        "JELLYFIN_URL": os.environ.get("JELLYFIN_URL"),
        "JELLYFIN_PUBLIC_BASE_URL": os.environ.get("JELLYFIN_PUBLIC_BASE_URL"),
        "JELLYFIN_API_KEY": os.environ.get("JELLYFIN_API_KEY"),
        "MCP_DOCKER_URL": os.environ.get("MCP_DOCKER_URL", MCP_DOCKER_BASE_URL).rstrip("/"),
    }
    missing = [key for key, value in env.items() if value in (None, "", [])]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    env["SUPA_REST_URL"] = env["SUPA_REST_URL"].rstrip("/")
    env["JELLYFIN_URL"] = env["JELLYFIN_URL"].rstrip("/")
    if not env.get("JELLYFIN_PUBLIC_BASE_URL"):
        env["JELLYFIN_PUBLIC_BASE_URL"] = env["JELLYFIN_URL"]
    env["JELLYFIN_PUBLIC_BASE_URL"] = env["JELLYFIN_PUBLIC_BASE_URL"].rstrip("/")
    return env  # type: ignore[return-value]


def _safe_meta(row: Dict[str, Any]) -> Dict[str, Any]:
    meta = row.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


def _artifact_and_path(row: Dict[str, Any], meta: Dict[str, Any]) -> Tuple[str, str]:
    artifact = (
        meta.get("artifact_uri")
        or row.get("artifact_uri")
        or row.get("content_url")
        or ""
    )
    if not artifact:
        raise ValueError(f"Row {row.get('id')} missing artifact URI")
    published_path = (
        meta.get("published_path")
        or row.get("published_path")
        or row.get("public_url")
        or ""
    )
    if not published_path:
        # Derive from artifact path
        parsed = urlparse(artifact)
        published_path = parsed.path.lstrip("/") or Path(parsed.path).name
    return artifact, published_path


def _derive_namespace(row: Dict[str, Any], meta: Dict[str, Any]) -> str:
    return (
        row.get("namespace")
        or meta.get("namespace")
        or os.environ.get("DEFAULT_NAMESPACE", "pmoves")
    )


def _derive_title(row: Dict[str, Any], meta: Dict[str, Any]) -> str:
    return row.get("title") or meta.get("title") or row.get("content_title") or "Untitled"


def _extract_tags(meta: Dict[str, Any]) -> Optional[List[str]]:
    tags = meta.get("tags")
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    if isinstance(tags, str):
        return [tag.strip() for tag in tags.split(",") if tag.strip()]
    return None


def _extension_from_path(path: str) -> str:
    parsed = urlparse(path)
    suffix = Path(parsed.path).suffix
    return suffix


def _filename_from_path(path: str) -> str:
    parsed = urlparse(path)
    return Path(parsed.path).name or "asset"


def _build_thumbnail_url(jellyfin_url: str, item: Dict[str, Any]) -> Optional[str]:
    image_tags = item.get("ImageTags") or {}
    primary_tag = image_tags.get("Primary")
    if not primary_tag:
        return None
    return f"{jellyfin_url}{JELLYFIN_IMAGE_ROUTE.format(item_id=item.get('Id'), tag=primary_tag)}"


def _ticks_to_seconds(value: Any) -> Optional[float]:
    try:
        ticks = float(value)
        return ticks / 10_000_000.0
    except (TypeError, ValueError):
        return None


async def fetch_candidates(client: httpx.AsyncClient, limit: int, start_after: Optional[str]) -> List[Dict[str, Any]]:
    params = {
        "select": "id,title,content_url,namespace,meta",
        "status": "eq.published",
        "order": "id.asc",
        "limit": str(limit),
        "meta->>jellyfin_public_url": "is.null",
    }
    if start_after:
        params["id"] = f"gt.{start_after}"
    resp = await client.get("/studio_board", params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_jellyfin_item(client: httpx.AsyncClient, item_id: str) -> Dict[str, Any]:
    resp = await client.get(f"/Items/{item_id}")
    resp.raise_for_status()
    return resp.json()


async def publish_event(agent_client: httpx.AsyncClient, payload: Dict[str, Any]) -> str:
    resp = await agent_client.post("/events/publish", json={"topic": "content.published.v1", "payload": payload, "source": "backfill"})
    resp.raise_for_status()
    data = resp.json()
    return data.get("id") or ""


async def update_supabase(client: httpx.AsyncClient, row_id: str, meta: Dict[str, Any]) -> None:
    resp = await client.patch(
        f"/studio_board?id=eq.{row_id}",
        content=json.dumps({"meta": meta}),
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()


async def search_youtube_transcripts(client: httpx.AsyncClient, query: str, limit: int = 5, threshold: float = YOUTUBE_SIMILARITY_THRESHOLD) -> List[Dict[str, Any]]:
    """Search YouTube transcript corpus for semantically similar content via pmoves-yt."""
    try:
        resp = await client.post(
            "/yt/search",
            json={"query": query, "limit": limit, "threshold": threshold},
            timeout=30.0
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        print(f"⚠️  YouTube search failed: {exc}")
        return []


def build_payload(row: Dict[str, Any], meta: Dict[str, Any], jellyfin_item: Dict[str, Any], env: Dict[str, str], youtube_links: Optional[List[Dict[str, Any]]] = None) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    jellyfin_id = (
        meta.get("jellyfin_item_id")
        or row.get("jellyfin_item_id")
        or jellyfin_item.get("Id")
    )
    if not jellyfin_id:
        raise ValueError(f"Row {row.get('id')} is missing jellyfin_item_id")

    artifact_uri, published_path = _artifact_and_path(row, meta)
    namespace = _derive_namespace(row, meta)
    title = _derive_title(row, meta)
    description = meta.get("description") or row.get("description")
    tags = _extract_tags(meta) or []
    slug = slugify(meta.get("slug") or title)
    namespace_slug = slugify(meta.get("namespace_slug") or namespace)
    filename = meta.get("filename") or _filename_from_path(published_path)
    extension = meta.get("extension") or _extension_from_path(published_path)
    public_url = meta.get("public_url") or row.get("public_url")

    duration = _ticks_to_seconds(jellyfin_item.get("RunTimeTicks"))
    thumbnail_url = _build_thumbnail_url(env["JELLYFIN_URL"], jellyfin_item)
    jellyfin_public_url = f"{env['JELLYFIN_PUBLIC_BASE_URL']}/web/index.html#!/details?id={jellyfin_id}"
    jellyfin_meta = {
        "id": jellyfin_item.get("Id"),
        "path": jellyfin_item.get("Path"),
        "container": jellyfin_item.get("Container"),
        "premiere_date": jellyfin_item.get("PremiereDate"),
        "production_year": jellyfin_item.get("ProductionYear"),
        "name": jellyfin_item.get("Name"),
    }

    # Add YouTube transcript links if available
    if youtube_links:
        jellyfin_meta["related_youtube"] = [
            {
                "video_id": link.get("video_id"),
                "title": link.get("title"),
                "url": link.get("url"),
                "similarity": link.get("similarity"),
                "transcript_excerpt": link.get("excerpt", "")[:200]
            }
            for link in youtube_links[:3]  # Top 3 results
        ]
        tags = list(set(tags + ["youtube-linked"]))

    payload = build_published_payload(
        artifact_uri=artifact_uri,
        published_path=published_path,
        namespace=namespace,
        title=title,
        description=description,
        tags=tags,
        incoming_meta=meta,
        public_url=public_url,
        jellyfin_item_id=jellyfin_id,
        jellyfin_public_url=jellyfin_public_url,
        thumbnail_url=thumbnail_url,
        duration=duration,
        jellyfin_meta=jellyfin_meta,
        slug=slug,
        namespace_slug=namespace_slug,
        filename=filename,
        extension=extension.lstrip("."),
    )
    
    summary = {
        "jellyfin_public_url": jellyfin_public_url,
        "jellyfin_item_id": jellyfin_id,
        "thumbnail_url": thumbnail_url,
        "duration": duration,
    }
    
    if youtube_links:
        summary["youtube_linked_count"] = len(youtube_links)
        summary["youtube_top_match"] = youtube_links[0].get("video_id") if youtube_links else None
    
    return payload, jellyfin_meta, summary


async def backfill(limit: int, dry_run: bool, sleep: float, start_after: Optional[str], link_youtube: bool, youtube_threshold: float) -> None:
    env = load_env()
    supabase_headers = {
        "apikey": env["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}",
    }
    async with httpx.AsyncClient(base_url=env["SUPA_REST_URL"], headers=supabase_headers, timeout=15.0) as supa_client, \
        httpx.AsyncClient(base_url=env["JELLYFIN_URL"], headers={"X-Emby-Token": env["JELLYFIN_API_KEY"]}, timeout=10.0) as jellyfin_client, \
        httpx.AsyncClient(base_url=env["AGENT_ZERO_BASE_URL"], timeout=10.0) as agent_client, \
        httpx.AsyncClient(base_url=env["PMOVES_YT_URL"], timeout=30.0) as yt_client:

        rows = await fetch_candidates(supa_client, limit=limit, start_after=start_after)
        if not rows:
            print("✅ No rows require backfill.")
            return

        print(f"Found {len(rows)} candidate(s) for Jellyfin backfill.")
        if link_youtube:
            print(f"🔗 YouTube transcript linking enabled (threshold: {youtube_threshold})")
        
        for row in rows:
            row_id = row.get("id")
            meta = _safe_meta(row)
            jellyfin_id = meta.get("jellyfin_item_id") or row.get("jellyfin_item_id")
            if not jellyfin_id:
                print(f"⚠️  Skipping row {row_id}: no jellyfin_item_id present.")
                continue
            try:
                jellyfin_item = await fetch_jellyfin_item(jellyfin_client, jellyfin_id)
            except httpx.HTTPStatusError as exc:
                print(f"❌ Jellyfin lookup failed for {row_id}: {exc.response.status_code}")
                continue

            # Perform YouTube transcript search if enabled
            youtube_links = None
            if link_youtube:
                title = _derive_title(row, meta)
                description = meta.get("description") or row.get("description") or ""
                search_query = f"{title} {description}".strip()
                
                if search_query:
                    youtube_links = await search_youtube_transcripts(yt_client, search_query, limit=5, threshold=youtube_threshold)
                    if youtube_links:
                        print(f"  🎥 Found {len(youtube_links)} YouTube matches for '{title[:50]}...'")

            try:
                payload, jellyfin_meta, summary = build_payload(row, meta, jellyfin_item, env, youtube_links)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"❌ Failed to build payload for {row_id}: {exc}")
                continue

            if dry_run:
                yt_info = f", youtube_links={summary.get('youtube_linked_count', 0)}" if link_youtube else ""
                print(f"📝 Dry-run row {row_id}: would publish Jellyfin {summary['jellyfin_item_id']} with duration={summary['duration']}{yt_info}")
                continue

            try:
                envelope_id = await publish_event(agent_client, payload)
                print(f"📤 Published envelope {envelope_id} for row {row_id}")
            except httpx.HTTPStatusError as exc:
                print(f"❌ Agent Zero publish failed for {row_id}: {exc.response.status_code}")
                continue

            now_iso = datetime.now(timezone.utc).isoformat()
            updated_meta = {**meta}
            updated_meta.update(summary)
            updated_meta["backfill_version"] = BACKFILL_VERSION
            updated_meta["publish_event_sent_at"] = now_iso
            try:
                await update_supabase(supa_client, row_id, updated_meta)
            except httpx.HTTPStatusError as exc:
                print(f"❌ Supabase update failed for {row_id}: {exc.response.status_code}")
                continue

            if sleep:
                await asyncio.sleep(sleep)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Jellyfin metadata and republish content.published.v1 events.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum number of rows to process (default: 10).")
    parser.add_argument("--dry-run", action="store_true", help="Do not publish or update Supabase; log planned actions.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Delay between publishes (seconds).")
    parser.add_argument("--start-after", help="Resume after the specified studio_board id.")
    parser.add_argument("--link-youtube", action="store_true", help="Enable YouTube transcript linking via PMOVES.yt corpus.")
    parser.add_argument("--youtube-threshold", type=float, default=YOUTUBE_SIMILARITY_THRESHOLD, help=f"Semantic similarity threshold for YouTube matches (default: {YOUTUBE_SIMILARITY_THRESHOLD}).")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        asyncio.run(backfill(
            limit=args.limit,
            dry_run=args.dry_run,
            sleep=args.sleep,
            start_after=args.start_after,
            link_youtube=args.link_youtube,
            youtube_threshold=args.youtube_threshold
        ))
        return 0
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
