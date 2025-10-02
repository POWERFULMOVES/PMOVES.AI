#!/usr/bin/env python3
"""Backfill Publisher audit records with enriched Jellyfin metadata.

This script reads `publisher_audit` rows from Supabase, fetches Jellyfin item
metadata when available, and merges duration/thumbnail/Jellyfin URLs into the
stored JSON `meta` payload. By default it runs in dry-run mode; pass
`--apply` to persist the updates.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]

try:  # pragma: no cover - optional supabase helper
    from services.common import supabase as supabase_common
except Exception as exc:  # pragma: no cover - ensures script fails fast with context
    raise RuntimeError("Supabase client helpers are required for this script") from exc

JELLYFIN_URL = os.environ.get("JELLYFIN_URL")
JELLYFIN_PUBLIC_BASE_URL = os.environ.get("JELLYFIN_PUBLIC_BASE_URL", JELLYFIN_URL)
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY")


@dataclasses.dataclass
class AuditRow:
    publish_event_id: str
    artifact_uri: Optional[str]
    namespace: Optional[str]
    public_url: Optional[str]
    jellyfin_item_id: Optional[str]
    meta: Dict[str, Any]

    @classmethod
    def from_supabase(cls, raw: Dict[str, Any]) -> "AuditRow":
        return cls(
            publish_event_id=str(raw.get("publish_event_id")),
            artifact_uri=raw.get("artifact_uri"),
            namespace=raw.get("namespace"),
            public_url=raw.get("public_url"),
            jellyfin_item_id=raw.get("jellyfin_item_id") or (raw.get("meta") or {}).get("jellyfin_item_id"),
            meta=dict(raw.get("meta") or {}),
        )


def _fetch_rows(limit: Optional[int]) -> List[AuditRow]:
    client = supabase_common.client()
    query = client.table("publisher_audit").select(
        "publish_event_id, artifact_uri, namespace, public_url, jellyfin_item_id, meta"
    )
    if limit:
        query = query.limit(limit)
    response = query.execute()
    data = getattr(response, "data", None) or getattr(response, "json", lambda: {}).get("data")
    rows = data or []
    return [AuditRow.from_supabase(item) for item in rows]


def _fetch_jellyfin_item(item_id: str) -> Optional[Dict[str, Any]]:
    if not (JELLYFIN_URL and JELLYFIN_API_KEY and requests):
        return None
    url = urljoin(JELLYFIN_URL.rstrip("/") + "/", f"Items/{item_id}")
    try:
        response = requests.get(
            url,
            params={"Fields": "PrimaryImageAspectRatio,CanDelete,Path"},
            headers={"X-Emby-Token": JELLYFIN_API_KEY},
            timeout=15,
        )
        response.raise_for_status()
    except Exception:
        return None
    with contextlib.suppress(Exception):
        return response.json()
    return None


def _seconds_from_ticks(runtime_ticks: Any) -> Optional[float]:
    try:
        if runtime_ticks is None:
            return None
        return float(runtime_ticks) / 10_000_000
    except (TypeError, ValueError):
        return None


def _derive_thumbnail_url(item_id: str, image_tag: Optional[str]) -> Optional[str]:
    if not image_tag:
        return None
    base = (JELLYFIN_PUBLIC_BASE_URL or JELLYFIN_URL or "").rstrip("/")
    if not base:
        return None
    return urljoin(base + "/", f"Items/{item_id}/Images/Primary?tag={image_tag}")


def _merge_meta(meta: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(meta)
    for key, value in updates.items():
        if value is not None:
            merged[key] = value
    return merged


def enrich_row(row: AuditRow) -> Dict[str, Any]:
    meta_updates: Dict[str, Any] = {}
    public_url_update: Optional[str] = None

    jellyfin_public_url = row.meta.get("jellyfin_public_url")
    if row.jellyfin_item_id and not jellyfin_public_url:
        base = (JELLYFIN_PUBLIC_BASE_URL or JELLYFIN_URL or "").rstrip("/")
        if base:
            jellyfin_public_url = urljoin(base + "/", f"web/index.html#!/details?id={row.jellyfin_item_id}&serverId=local")
            meta_updates["jellyfin_public_url"] = jellyfin_public_url
    if jellyfin_public_url and not row.public_url:
        public_url_update = jellyfin_public_url

    duration = row.meta.get("duration")
    thumbnail_url = row.meta.get("thumbnail_url")
    if row.jellyfin_item_id:
        item = _fetch_jellyfin_item(row.jellyfin_item_id)
        if item:
            if duration is None:
                duration = _seconds_from_ticks(item.get("RunTimeTicks") or item.get("RuntimeTicks"))
            image_tag = None
            if isinstance(item.get("ImageTags"), dict):
                image_tag = item["ImageTags"].get("Primary")
            if not thumbnail_url:
                thumbnail_url = _derive_thumbnail_url(row.jellyfin_item_id, image_tag)
    if duration is not None:
        meta_updates["duration"] = duration
    if thumbnail_url:
        meta_updates["thumbnail_url"] = thumbnail_url

    result: Dict[str, Any] = {}
    if meta_updates:
        result["meta"] = _merge_meta(row.meta, meta_updates)
    if public_url_update:
        result["public_url"] = public_url_update
    return result


def apply_updates(row: AuditRow, updates: Dict[str, Any], *, dry_run: bool) -> None:
    if not updates:
        return
    pretty = json.dumps(updates, indent=2, sort_keys=True)
    action = "DRY-RUN" if dry_run else "APPLY"
    print(f"[{action}] {row.publish_event_id}: {pretty}")
    if dry_run:
        return
    client = supabase_common.client()
    client.table("publisher_audit").update(updates).eq("publish_event_id", row.publish_event_id).execute()


-def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
+def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
     parser = argparse.ArgumentParser(description="Backfill publisher metadata in Supabase")
     parser.add_argument("--limit", type=int, default=100, help="Maximum rows to scan (default: 100)")
     parser.add_argument(
         "--apply",
         action="store_true",
         help="Persist updates instead of printing dry-run diffs",
     )
     return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
+    if requests is None:
+        print("requests is required for Jellyfin lookups; install it or run inside the publisher environment", file=sys.stderr)
+        return 2
     args = parse_args(argv)
     rows = _fetch_rows(args.limit)
     if not rows:
         print("No publisher_audit rows returned; nothing to backfill")
         return 0

     dry_run = not args.apply
     for row in rows:
         updates = enrich_row(row)
         apply_updates(row, updates, dry_run=dry_run)

     if dry_run:
         print("Dry run complete. Re-run with --apply to persist changes.")
     else:
         print("Updates applied to Supabase publisher_audit")
     return 0


 if __name__ == "__main__":
     raise SystemExit(main(sys.argv[1:]))
