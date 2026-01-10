"""Lightweight helper to query the gateway mindmap endpoint."""

import argparse
import json
import os
import sys
from typing import Any, Dict

import requests

DEFAULT_BASE = os.getenv("MINDMAP_BASE", "http://localhost:8000")
DEFAULT_CONSTELLATION = os.getenv(
    "MINDMAP_CONSTELLATION_ID", "8c1b7a8c-7b38-4a6b-9bc3-3f1fdc9a1111"
)


def _pretty_print(payload: Dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch mindmap points/media for a constellation.",
    )
    parser.add_argument("--base", default=DEFAULT_BASE, help="Gateway base URL")
    parser.add_argument(
        "--cid",
        default=DEFAULT_CONSTELLATION,
        help="Constellation identifier to query.",
    )
    parser.add_argument(
        "--modalities",
        default=os.getenv("MINDMAP_MODALITIES", "text,video,audio,doc,image"),
        help="Comma separated modalities filter.",
    )
    parser.add_argument("--minProj", type=float, default=float(os.getenv("MINDMAP_MIN_PROJ", 0.5)))
    parser.add_argument("--minConf", type=float, default=float(os.getenv("MINDMAP_MIN_CONF", 0.5)))
    parser.add_argument("--limit", type=int, default=int(os.getenv("MINDMAP_LIMIT", 50)))
    parser.add_argument("--offset", type=int, default=int(os.getenv("MINDMAP_OFFSET", 0)))
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Return raw point/media objects without notebook enrichment.",
    )

    args = parser.parse_args()

    url = f"{args.base.rstrip('/')}/mindmap/{args.cid}"
    params = {
        "modalities": args.modalities,
        "minProj": args.minProj,
        "minConf": args.minConf,
        "limit": args.limit,
        "offset": args.offset,
        "enrich": not args.no_enrich,
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - CLI utility
        sys.stderr.write(f"mindmap query failed: {exc}\n")
        return 1

    payload = response.json()
    summary = {
        "returned": payload.get("returned"),
        "total": payload.get("total"),
        "offset": payload.get("offset"),
        "remaining": payload.get("remaining"),
        "has_more": payload.get("has_more"),
    }
    sys.stderr.write(
        "Mindmap query summary: "
        + ", ".join(f"{k}={v}" for k, v in summary.items() if v is not None)
        + "\n"
    )
    stats = payload.get("stats", {}).get("per_modality") or {}
    if stats:
        sys.stderr.write(
            "Per-modality counts: "
            + ", ".join(f"{mod}={count}" for mod, count in sorted(stats.items()))
            + "\n"
        )
    _pretty_print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
