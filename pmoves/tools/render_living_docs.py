#!/usr/bin/env python3
"""Render living docs dashboard via a2ui-renderer POST /render/provenance.

Calls the a2ui-renderer service with the current living docs state to produce
a visual dashboard. Requires a2ui-renderer running (creator profile).
"""
import argparse
import json
import os
import sys
import urllib.request

A2UI_URL = os.environ.get("A2UI_RENDERER_URL", "http://localhost:8107")


def main():
    parser = argparse.ArgumentParser(description="Render living docs via a2ui-renderer")
    parser.add_argument("--format", default="png", choices=["png", "mp4", "webm"])
    parser.add_argument("--output", default="docs-living-dashboard")
    args = parser.parse_args()

    payload = {
        "format": args.format,
        "title": "PMOVES Living Docs Dashboard",
        "source": "docs-render-living",
    }

    try:
        req = urllib.request.Request(
            f"{A2UI_URL}/render/provenance",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            print(f"Rendered: {result.get('uri', 'unknown')}")
            print(f"Format: {args.format}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
