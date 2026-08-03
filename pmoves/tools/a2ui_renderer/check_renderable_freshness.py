#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
check_renderable_freshness.py — report renderable living docs that are stale.

Lane 2228 (2026-08-02): the living-docs hook for the a2ui-renderer compose lane.
Reads the `renderable:` section of pmoves/configs/living_docs_registry.yaml and
emits a structured report listing each entry whose source markdown file is older
than its `ttl_days` threshold (or has no rendered artifact yet).

This is intentionally read-only — it never re-renders anything. The companion
script `render_living_doc.py` does the actual rendering; this script is the
advisor that says "these docs are due for a re-render". Wire it into
`make docs-reconcile-check` and the docs-freshness village-gate (advisory).

Output is JSON to stdout; a one-line summary is printed to stderr. Exit code:
  0 — all entries fresh (or no renderable entries defined)
  1 — one or more entries are stale
  2 — registry file missing or malformed

Usage:
  python check_renderable_freshness.py \\
      --registry pmoves/configs/living_docs_registry.yaml \\
      --repo-root .
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Reuse the registry loader + the renderable section schema.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from a2ui_renderer import render_living_doc as rld  # noqa: E402

# Force UTF-8 on stdout/stderr so the JSON report doesn't break on Windows
# charmap when a source_doc path contains non-ASCII characters.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def _classify_freshness(
    entry: dict[str, str], source: Path, now_epoch: float
) -> dict[str, object]:
    """Return a structured record describing the freshness of one entry."""
    ttl_days = int(entry.get("ttl_days", "30") or "30")
    ttl_seconds = ttl_days * 86400
    if not source.exists():
        return {
            "id": entry.get("id", ""),
            "source": str(source),
            "exists": False,
            "stale": True,
            "reason": "source markdown missing",
            "ttl_days": ttl_days,
        }
    mtime = source.stat().st_mtime
    age_seconds = now_epoch - mtime
    stale = age_seconds > ttl_seconds
    return {
        "id": entry.get("id", ""),
        "source": str(source),
        "exists": True,
        "stale": stale,
        "age_seconds": int(age_seconds),
        "age_days": round(age_seconds / 86400, 2),
        "ttl_days": ttl_days,
        "reason": (
            f"source is {round(age_seconds/86400, 1)}d old, ttl={ttl_days}d"
            if stale
            else f"within ttl ({ttl_days}d)"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="check_renderable_freshness",
        description="Report stale entries in living_docs_registry.yaml (renderable: section).",
    )
    p.add_argument(
        "--registry",
        type=Path,
        default=Path("pmoves/configs/living_docs_registry.yaml"),
        help="path to living_docs_registry.yaml",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="root for resolving source_doc paths",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any entry is stale (default: print report only)",
    )
    args = p.parse_args(argv)

    if not args.registry.exists():
        print(
            json.dumps({"ok": False, "error": f"registry not found: {args.registry}"}),
            file=sys.stdout,
        )
        return 2

    try:
        entries = rld.load_renderable_registry(args.registry)
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps({"ok": False, "error": f"failed to parse registry: {exc}"}),
            file=sys.stdout,
        )
        return 2

    now_epoch = time.time()
    repo_root = args.repo_root.resolve()
    records = []
    for entry in entries:
        source_rel = entry.get("source_doc", "").strip()
        if not source_rel:
            records.append({
                "id": entry.get("id", ""),
                "stale": True,
                "reason": "missing source_doc",
                "ttl_days": int(entry.get("ttl_days", "30") or "30"),
            })
            continue
        source = (repo_root / source_rel).resolve()
        records.append(_classify_freshness(entry, source, now_epoch))

    stale_count = sum(1 for r in records if r.get("stale"))
    summary = {
        "ok": True,
        "registry": str(args.registry),
        "total": len(records),
        "stale": stale_count,
        "fresh": len(records) - stale_count,
        "entries": records,
    }
    print(json.dumps(summary, indent=2))
    print(
        f"[check_renderable_freshness] {len(records)} entries, {stale_count} stale",
        file=sys.stderr,
    )

    if stale_count and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
