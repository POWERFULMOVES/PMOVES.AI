#!/usr/bin/env python3
"""Mint a per-agent cipher token and insert it into Supabase cipher_agent_tokens."""

import argparse
import json
import os
import sys
import uuid

import urllib.request
import urllib.error


def _redact(text: str, token_uuid: uuid.UUID) -> str:
    """Blank both spellings of the uuid: stored form is dashed, bearer form is not."""
    for form in (str(token_uuid), token_uuid.hex):
        text = text.replace(form, "<redacted:token_uuid>")
    return text


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
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        # A duplicate-key or constraint error quotes the offending VALUE back,
        # and that value is token_uuid. Server-controlled text is not a safe
        # place to assume the credential is absent.
        print(
            f"error: Supabase returned {e.code}: {_redact(detail, token_uuid)}",
            file=sys.stderr,
        )
        return 1

    # The response body is deliberately NOT printed.
    #
    # The insert is sent with `Prefer: return=representation`, so Supabase echoes
    # the stored row -- and that row carries token_uuid, from which the bearer
    # `cipher_{token_uuid.hex}` is reconstructable in full. There is no hash
    # column (migration 20260728100000: `token_uuid UUID PRIMARY KEY`), so the
    # stored row IS the credential.
    #
    # Printing it put a SECOND copy on stdout wearing no label. An operator or
    # log scrubber redacting `CIPHER_TOKEN=` removed the copy they could see and
    # left the one they could not. Two emissions, one invisible to redaction, is
    # strictly worse than one: it makes the transcript look clean.
    #
    # The body is still parsed, because "accepted but stored nothing" has to be
    # an error rather than a token the operator will try to use.
    if raw.strip():
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            print("error: Supabase response was not JSON", file=sys.stderr)
            return 1
        if isinstance(rows, list) and not rows:
            print(
                "error: Supabase accepted the insert but returned no row; "
                "the token was NOT registered",
                file=sys.stderr,
            )
            return 1

    print(f"CIPHER_TOKEN={token}")
    print(f"AGENT={args.agent}")
    print(f"SCOPES={','.join(scopes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
