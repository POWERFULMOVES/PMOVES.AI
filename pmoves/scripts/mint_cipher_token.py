#!/usr/bin/env python3
"""Mint a per-agent cipher token and insert it into Supabase cipher_agent_tokens."""

import argparse
import json
import os
import sys
import uuid

import urllib.request
import urllib.error


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a per-agent cipher token")
    parser.add_argument("--agent", required=True, help="Agent identifier (e.g. crush-spark)")
    parser.add_argument("--scopes", default="memory:read,memory:write", help="Comma-separated scopes")
    parser.add_argument("--rest-url", default=os.environ.get("SUPABASE_REST_URL", "http://localhost:8000/rest/v1"))
    parser.add_argument("--service-key", default=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SERVICE_ROLE_KEY", "")))
    args = parser.parse_args()

    if not args.service_key:
        print("error: SUPABASE_SERVICE_KEY or SERVICE_ROLE_KEY must be set", file=sys.stderr)
        return 1

    token_uuid = uuid.uuid4()
    token = f"cipher_{token_uuid.hex}"
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]

    payload = {
        "token_uuid": str(token_uuid),
        "agent_id": args.agent,
        "scopes": scopes,
    }

    body = json.dumps(payload).encode("utf-8")
    url = f"{args.rest_url}/cipher_agent_tokens"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": args.service_key,
            "Authorization": f"Bearer {args.service_key}",
            "Content-Profile": "pmoves_core",
            "Prefer": "return=representation",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            print(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"error: Supabase returned {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1

    print(f"CIPHER_TOKEN={token}")
    print(f"AGENT={args.agent}")
    print(f"SCOPES={','.join(scopes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
