#!/usr/bin/env python3
"""Shared helpers for reading submodule metadata."""

from __future__ import annotations

import configparser
from pathlib import Path


def parse_gitmodules_rows(path: Path) -> list[dict[str, str]]:
    """Return normalized `.gitmodules` rows sorted by submodule path."""
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    rows: list[dict[str, str]] = []
    for section in cfg.sections():
        if not section.startswith("submodule "):
            continue
        name = section[len("submodule ") :].strip().strip('"')
        rows.append(
            {
                "section": section,
                "name": name,
                "path": cfg.get(section, "path", fallback="").strip(),
                "url": cfg.get(section, "url", fallback="").strip(),
                "branch": cfg.get(section, "branch", fallback="").strip(),
            }
        )
    rows = [row for row in rows if row.get("path")]
    rows.sort(key=lambda row: row["path"].lower())
    return rows
