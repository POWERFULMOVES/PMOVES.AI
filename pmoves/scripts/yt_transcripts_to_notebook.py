#!/usr/bin/env python3
"""
Sync PMOVES.YT transcripts from Supabase into Open Notebook sources.

This helper pulls transcripts that have not yet been mirrored into Open Notebook,
creates Notebook sources (text entries), and records the resulting source IDs
back into the Supabase `transcripts` (and `youtube_transcripts`) metadata.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from notebook_ingest_utils import NotebookClient, NotebookSource


DEFAULT_SUPA = os.environ.get("SUPA_REST_URL") or os.environ.get("SUPABASE_REST_URL") or "http://localhost:3010"
DEFAULT_NOTEBOOK_API = os.environ.get("OPEN_NOTEBOOK_API_URL", "http://localhost:5055")
DEFAULT_NOTEBOOK_ID = (
    os.environ.get("YOUTUBE_NOTEBOOK_ID")
    or os.environ.get("OPEN_NOTEBOOK_NOTEBOOK_ID")
    or os.environ.get("MINDMAP_NOTEBOOK_ID")
)


def _require(name: str, value: Optional[str]) -> str:
    if value and value.strip():
        return value.strip()
    sys.stderr.write(f"ERROR: {name} must be set.\n")
    sys.exit(2)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_headers(service_key: str) -> Dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get_supabase_session(base_url: str, service_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_build_headers(service_key))
    session.base_url = base_url.rstrip("/")  # type: ignore[attr-defined]
    return session


def _supabase_request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> requests.Response:
    base_url = getattr(session, "base_url")
    url = f"{base_url}/{path.lstrip('/')}"
    response = session.request(method, url, params=params, json=json_body, timeout=timeout)
    response.raise_for_status()
    return response


def fetch_transcripts(
    session: requests.Session,
    limit: Optional[int],
    include_synced: bool,
    since: Optional[str],
    namespace: Optional[str],
    language: Optional[str],
) -> List[Dict[str, Any]]:
    params: Dict[str, str] = {
        "select": (
            "id,video_id,language,text,s3_uri,meta,created_at,"
            "videos:videos(video_id,title,source_url,meta),"
            "youtube:youtube_transcripts!left(video_id)("
            "channel,channel_id,channel_url,channel_thumbnail,channel_tags,namespace,channel_metadata"
            ")"
        ),
        "order": "created_at.asc",
    }
    if limit and limit > 0:
        params["limit"] = str(limit)
    if not include_synced:
        params["meta->>notebook_synced_at"] = "is.null"
    if since:
        params["created_at"] = f"gt.{since}"
    if namespace:
        params["meta->>namespace"] = f"eq.{namespace}"
    if language:
        params["language"] = f"eq.{language}"
    try:
        resp = _supabase_request(session, "GET", "transcripts", params=params)
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        if response is None:
            raise
        if response.status_code != 400:
            raise
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {}
        if error_payload.get("code") != "PGRST200":
            raise
        sys.stderr.write(
            "WARN: transcripts→videos relationship not found in Supabase schema; "
            "falling back to transcript rows without joined video metadata.\n"
        )
        fallback_params = dict(params)
        fallback_params["select"] = "id,video_id,language,text,s3_uri,meta,created_at"
        resp = _supabase_request(session, "GET", "transcripts", params=fallback_params)
    data = resp.json()
    if not isinstance(data, list):
        return []
    return data


def _merge_meta(existing: Any, patch: Dict[str, Any]) -> Dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    merged = dict(base)
    merged.update({k: v for k, v in patch.items() if v is not None})
    return merged


def update_transcript_meta(session: requests.Session, transcript_id: int, meta_patch: Dict[str, Any]) -> None:
    payload = {"meta": meta_patch}
    _supabase_request(
        session,
        "PATCH",
        f"transcripts?id=eq.{transcript_id}",
        json_body=payload,
        timeout=15.0,
    )


def update_youtube_meta(session: requests.Session, video_id: str, meta_patch: Dict[str, Any]) -> None:
    try:
        resp = _supabase_request(
            session,
            "GET",
            "youtube_transcripts",
            params={"select": "meta", "video_id": f"eq.{video_id}", "limit": "1"},
            timeout=15.0,
        )
        rows = resp.json()
    except requests.HTTPError:
        return
    if not isinstance(rows, list) or not rows:
        return
    meta = _merge_meta(rows[0].get("meta"), meta_patch)
    _supabase_request(
        session,
        "PATCH",
        f"youtube_transcripts?video_id=eq.{video_id}",
        json_body={"meta": meta},
        timeout=15.0,
    )


def build_source(
    transcript: Dict[str, Any],
    notebook_id: str,
    embed: bool,
    async_processing: bool,
) -> Tuple[NotebookSource, Dict[str, Any]]:
    video = transcript.get("videos") or {}
    video_id = transcript.get("video_id")
    title = video.get("title") or f"YouTube {video_id}"
    url = video.get("source_url") or f"https://youtube.com/watch?v={video_id}"
    text = (transcript.get("text") or "").strip()
    # Append URL reference to the Notebook entry for manual navigation.
    content = f"{text}\n\nSource: {url}" if text else f"Source: {url}"
    source = NotebookSource(
        title=title,
        source_type="text",
        notebooks=[notebook_id],
        url=url,
        content=content,
        embed=embed,
        async_processing=async_processing,
    )
    metadata = {
        "source_url": url,
        "video_id": video_id,
        "language": transcript.get("language"),
    }
    youtube_meta = transcript.get("youtube") or {}
    transcript_meta = transcript.get("meta") or {}
    metadata.update(
        {
            "namespace": youtube_meta.get("namespace")
            or transcript_meta.get("namespace"),
            "channel_name": youtube_meta.get("channel")
            or (video.get("meta") or {}).get("channel", {}).get("title"),
            "channel_id": youtube_meta.get("channel_id"),
            "channel_url": youtube_meta.get("channel_url"),
            "channel_tags": youtube_meta.get("channel_tags"),
            "channel_thumbnail": youtube_meta.get("channel_thumbnail"),
            "channel_metadata": youtube_meta.get("channel_metadata"),
        }
    )
    if metadata.get("channel_name") is None:
        metadata["channel_name"] = (video.get("meta") or {}).get("channel", {}).get("name")
    return source, metadata


def sync_transcripts(
    session: requests.Session,
    transcripts: List[Dict[str, Any]],
    notebook_client: NotebookClient,
    notebook_id: str,
    embed: bool,
    async_processing: bool,
    dry_run: bool,
) -> Dict[str, int]:
    existing_keys = notebook_client.fetch_existing_keys(notebook_id)
    stats = {"processed": 0, "created": 0, "skipped": 0, "updated": 0}

    for row in transcripts:
        stats["processed"] += 1
        transcript_id = row.get("id")
        if transcript_id is None:
            stats["skipped"] += 1
            continue
        text = (row.get("text") or "").strip()
        if not text:
            stats["skipped"] += 1
            continue

        source, metadata = build_source(row, notebook_id, embed, async_processing)
        dedupe_key = source.dedupe_key()
        if dedupe_key in existing_keys:
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"DRY-RUN would create source {source.title!r} for video {metadata.get('video_id')}")
            stats["created"] += 1
            continue

        try:
            notebook_id_created = notebook_client.create_source(source)
        except Exception as exc:  # pylint: disable=broad-except
            stats["skipped"] += 1
            sys.stderr.write(f"Failed to create Notebook source for transcript {transcript_id}: {exc}\n")
            continue

        stats["created"] += 1
        existing_keys.add(dedupe_key)
        synced_at = _utc_now()
        transcript_meta_patch = _merge_meta(
            row.get("meta"),
            {
                "notebook_source_id": notebook_id_created,
                "notebook_synced_at": synced_at,
                "notebook_metadata": metadata,
            },
        )
        update_transcript_meta(session, transcript_id, transcript_meta_patch)
        video_id = row.get("video_id")
        if isinstance(video_id, str):
            youtube_meta_patch = {
                "notebook_source_id": notebook_id_created,
                "notebook_synced_at": synced_at,
            }
            update_youtube_meta(session, video_id, youtube_meta_patch)
        stats["updated"] += 1

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync PMOVES.YT transcripts into Open Notebook.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum transcripts to process (default: 25)")
    parser.add_argument("--include-synced", action="store_true", help="Include transcripts already synced previously")
    parser.add_argument("--since", help="Only sync transcripts created after this ISO timestamp")
    parser.add_argument("--namespace", help="Filter transcripts by namespace stored in meta")
    parser.add_argument("--language", help="Filter transcripts by language code")
    parser.add_argument("--notebook-id", default=DEFAULT_NOTEBOOK_ID, help="Target Open Notebook ID")
    parser.add_argument("--api", default=DEFAULT_NOTEBOOK_API, help="Open Notebook API base URL")
    parser.add_argument("--supabase-url", default=DEFAULT_SUPA, help="Supabase REST base URL")
    parser.add_argument("--service-key", default=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"), help="Supabase service role key")
    parser.add_argument("--token", default=os.environ.get("OPEN_NOTEBOOK_API_TOKEN"), help="Open Notebook API token")
    parser.add_argument("--embed", dest="embed", action="store_true", help="Enable embedding during creation (default)")
    parser.add_argument("--no-embed", dest="embed", action="store_false", help="Disable embedding during creation")
    parser.set_defaults(embed=True)
    parser.add_argument("--async-processing", dest="async_processing", action="store_true", help="Enable async processing flag when creating sources")
    parser.add_argument("--sync-processing", dest="async_processing", action="store_false", help="Force synchronous processing (not recommended)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying Supabase or Notebook")
    parser.set_defaults(async_processing=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    service_key = _require("SUPABASE_SERVICE_ROLE_KEY", args.service_key)
    notebook_id = _require("notebook-id", args.notebook_id)
    notebook_token = _require("OPEN_NOTEBOOK_API_TOKEN", args.token)

    session = _get_supabase_session(args.supabase_url, service_key)
    transcripts = fetch_transcripts(
        session,
        limit=args.limit,
        include_synced=args.include_synced,
        since=args.since,
        namespace=args.namespace,
        language=args.language,
    )
    if not transcripts:
        print("No transcripts matched the current filters.")
        return 0

    client = NotebookClient(args.api, notebook_token)
    stats = sync_transcripts(
        session,
        transcripts,
        client,
        notebook_id,
        embed=args.embed,
        async_processing=args.async_processing,
        dry_run=args.dry_run,
    )
    print(
        f"Sync complete: processed={stats['processed']} created={stats['created']} "
        f"updated={stats['updated']} skipped={stats['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
