"""CLI helper to register Archon provider credentials via the admin endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from getpass import getpass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set an Archon provider API key using the FastAPI admin endpoint.",
    )
    default_port = os.getenv("ARCHON_SERVER_PORT", "8091")
    parser.add_argument("--provider", required=True, help="Provider name (e.g. openai, google, anthropic)")
    parser.add_argument(
        "--key",
        help="API key value. If omitted, the tool prompts for it interactively.",
    )
    parser.add_argument(
        "--server-url",
        default=f"http://localhost:{default_port}",
        help="Base URL for the Archon server (default: http://localhost:<ARCHON_SERVER_PORT or 8091>).",
    )
    parser.add_argument(
        "--service-type",
        choices=["llm", "embedding"],
        default="llm",
        help="Archon service type to mark as default when --make-default is set.",
    )
    parser.add_argument(
        "--make-default",
        action="store_true",
        help="Mark the provided provider as the active provider for the selected service type.",
    )
    parser.add_argument(
        "--category",
        default="credentials",
        help="Optional archon_settings category name for the stored credential.",
    )
    parser.add_argument(
        "--description",
        help="Optional description stored alongside the credential.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request payload without sending it to the server.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    provider = args.provider.strip().lower()
    if not provider:
        parser.error("--provider must not be empty")

    api_key = args.key.strip() if args.key else ""
    if not api_key and not args.dry_run:
        api_key = getpass("Enter API key: ").strip()

    if not api_key and not args.dry_run:
        parser.error("API key is required (provide --key or enter it interactively)")

    payload = {
        "provider": provider,
        "api_key": api_key,
        "service_type": args.service_type,
        "make_default": args.make_default,
        "category": args.category,
    }
    if args.description:
        payload["description"] = args.description

    if args.dry_run:
        print("[dry-run] POST", json.dumps(payload, indent=2))
        return 0

    base_url = args.server_url.rstrip("/")
    endpoint = f"{base_url}/api/credentials/provider"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            if not body:
                print("No response body received.")
                return 0
            parsed = json.loads(body)
    except urllib.error.HTTPError as http_error:
        error_body = http_error.read().decode("utf-8", errors="ignore")
        print(f"HTTP {http_error.code}: {error_body or http_error.reason}", file=sys.stderr)
        return http_error.code or 1
    except urllib.error.URLError as url_error:
        print(f"Failed to reach Archon server: {url_error.reason}", file=sys.stderr)
        return 1

    print(json.dumps(parsed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
