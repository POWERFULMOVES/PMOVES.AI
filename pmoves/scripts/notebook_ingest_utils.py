#!/usr/bin/env python3
"""
Shared helpers for syncing PMOVES artifacts into Open Notebook.

This module centralizes the bearer-authenticated client, dedupe helpers,
and source creation logic so individual ingestion scripts (mindmap, Hi-RAG
search, etc.) can focus on shaping the payloads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import requests


@dataclass
class NotebookSource:
    """Canonical representation of a Notebook source payload."""

    title: str
    source_type: str  # "link" or "text"
    notebooks: List[str]
    url: Optional[str] = None
    content: Optional[str] = None
    embed: bool = True
    async_processing: bool = True

    def dedupe_key(self) -> str:
        if self.source_type == "link" and self.url:
            return f"url:{self.url}"
        return f"title:{self.title.lower().strip()}"


class NotebookClient:
    def __init__(self, api_base: str, token: str) -> None:
        self.api_base = api_base.rstrip("/") + "/api"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    def fetch_existing_keys(self, notebook_id: str) -> Set[str]:
        """Return a set of dedupe keys (url/title) for existing sources."""
        existing: Set[str] = set()
        offset = 0
        page_size = 100
        while True:
            params = {"notebook_id": notebook_id, "limit": page_size, "offset": offset}
            resp = requests.get(
                f"{self.api_base}/sources", params=params, headers=self.headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for src in data:
                asset = src.get("asset") or {}
                url = asset.get("url")
                if url:
                    existing.add(f"url:{url}")
                title = (src.get("title") or "").strip().lower()
                if title:
                    existing.add(f"title:{title}")
            offset += len(data)
            if len(data) < page_size:
                break
        return existing

    def create_source(self, source: NotebookSource, dry_run: bool = False) -> Optional[str]:
        payload: Dict[str, object] = {
            "type": source.source_type,
            "title": source.title,
            "notebooks": source.notebooks,
            "embed": source.embed,
            "async_processing": source.async_processing,
        }
        if source.source_type == "link":
            payload["url"] = source.url
            if source.content:
                payload["content"] = source.content
        else:
            payload["content"] = source.content

        if dry_run:
            return None

        resp = requests.post(
            f"{self.api_base}/sources/json", json=payload, headers=self.headers, timeout=60
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"Notebook source creation failed: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("id")
