#!/usr/bin/env python3
"""Retire cipher tokens for an agent by setting ``revoked_at``.

WHY THIS EXISTS, AND WHY IT IS NOT A NEW FEATURE
------------------------------------------------
Two of three legs were already built. Measured 2026-09-17:

    the schema STORES it     20260728100000_cipher_agent_tokens.sql:10
    auth.ts HONOURS it       :68  ?token_uuid=eq.<uuid>&revoked_at=is.null
    auth.ts REJECTS on it    :122 401 'Unauthorized — invalid or revoked token'
    nothing SET it           tree-wide grep: DDL + two test fixtures, no writer

So the system was fully prepared to reject a revoked token with no way to revoke
one. A compromised credential stayed valid because the only act that retires it
had no implementation. That is worse than a missing feature: a signing card is a
LIVING record of provenance -- checkable and current -- and a credential you
cannot retire stays current in the document whose whole job is being current.

THE SPEC IS SET BY THE PARTS. TAC_CIPHER_VILLAGE.md names `revoked_at` once, as
a column, and specifies no revoke act -- but the doc is a summary, and summaries
go stale. The PARTS specify the operation precisely:

    idx_cipher_agent_tokens_agent ON (agent_id, revoked_at)
    -- "Agent index for audit and revocation"

That index exists FOR revocation and is keyed on agent_id. So revocation is
BY AGENT, indexed, with revoked_at as the discriminator. --token-uuid narrows to
one row for the case where a single credential is known-compromised.

NEVER PRINTS token_uuid
-----------------------
The stored uuid IS the bearer: mint builds `cipher_{token_uuid.hex}` and stores
that same uuid, and the migration has no hash column (grep -c hash = 0). So
listing "which tokens exist" would reprint every live credential. This tool
reports COUNTS and agent_id only. That is not caution, it is the same property
the mint's redaction protects.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def _request(url: str, key: str, method: str, body: bytes | None = None) -> str:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Profile": "pmoves_core",
        "Accept-Profile": "pmoves_core",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Revoke cipher tokens for an agent")
    p.add_argument("--agent", required=True, help="Agent identifier whose tokens to revoke")
    p.add_argument(
        "--token-uuid",
        default="",
        help="narrow to ONE token (for a known-compromised credential). "
             "Accepted but never echoed back.",
    )
    p.add_argument("--rest-url", default=os.environ.get("SUPABASE_REST_URL", "http://localhost:8000/rest/v1"))
    p.add_argument(
        "--service-key",
        default=os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SERVICE_ROLE_KEY", "")),
    )
    p.add_argument("--dry-run", action="store_true", help="count what WOULD be revoked; change nothing")
    args = p.parse_args()

    if not args.service_key:
        print("error: SUPABASE_SERVICE_KEY or SERVICE_ROLE_KEY must be set", file=sys.stderr)
        return 1

    # Only ACTIVE rows are targets. Re-revoking an already-revoked token would
    # move its revoked_at forward and destroy when it was actually retired --
    # the one fact an audit of a compromise needs.
    filt = f"agent_id=eq.{args.agent}&revoked_at=is.null"
    if args.token_uuid:
        filt += f"&token_uuid=eq.{args.token_uuid}"

    # select=agent_id ONLY. Never token_uuid: the stored uuid is the bearer.
    try:
        raw = _request(f"{args.rest_url}/cipher_agent_tokens?{filt}&select=agent_id", args.service_key, "GET")
        active = json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"error: Supabase returned {e.code} listing active tokens", file=sys.stderr)
        return 1
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"error: could not list active tokens: {e}", file=sys.stderr)
        return 1

    n = len(active) if isinstance(active, list) else 0
    if n == 0:
        print(f"AGENT={args.agent}")
        print("REVOKED=0")
        print("note: no active tokens matched; nothing to retire")
        return 0

    if args.dry_run:
        print(f"AGENT={args.agent}")
        print(f"WOULD_REVOKE={n}")
        return 0

    stamp = datetime.now(timezone.utc).isoformat()
    try:
        raw = _request(
            f"{args.rest_url}/cipher_agent_tokens?{filt}",
            args.service_key,
            "PATCH",
            json.dumps({"revoked_at": stamp}).encode("utf-8"),
        )
    except urllib.error.HTTPError as e:
        # Never echo the error body: PostgREST quotes offending values back, and
        # the offending value here would be a token_uuid.
        print(f"error: Supabase returned {e.code} revoking tokens for {args.agent!r}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"error: could not reach Supabase: {e}", file=sys.stderr)
        return 1

    try:
        revoked = len(json.loads(raw))
    except json.JSONDecodeError:
        revoked = n  # representation not returned; the PATCH itself succeeded

    print(f"AGENT={args.agent}")
    print(f"REVOKED={revoked}")
    print(f"REVOKED_AT={stamp}")
    print("note: auth.ts rejects these on the next request (401 invalid or revoked token)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
