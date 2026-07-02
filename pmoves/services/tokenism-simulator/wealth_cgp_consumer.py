#!/usr/bin/env python3
"""PMOVES Wealth CGP Consumer.

Reads signed CGP export payloads (produced by the tokenism simulator) and
persists them to the Supabase `pmoves_core.wealth_cgp_exports` table.

Modes:
  --file <path>        : one-shot insert of a single CGP export JSON file.
  --watch <directory>  : watch a directory and import any new .cgp.json files.

The script posts to the Supabase REST endpoint using the service role key.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests


def get_supabase_url() -> str:
    # Prefer the public URL used by browser/clients; fall back to internal kong URL.
    return os.environ.get(
        "SUPABASE_PUBLIC_URL",
        os.environ.get("SUPABASE_REST_URL", "http://localhost:8000"),
    ).rstrip("/")


def get_service_role_key() -> str:
    # Accept either the explicit Supabase key or the generic service role key.
    return os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY",
        os.environ.get("SUPABASE_SECRET_KEY", os.environ.get("SERVICE_ROLE_KEY", "")),
    )


def headers(service_role_key: str, schema: str = "pmoves_core") -> dict:
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Content-Profile": schema,
        "Accept-Profile": schema,
        "Prefer": "return=minimal",
    }


def insert_cgp_export(payload: dict, url: str, key: str) -> None:
    """Insert a CGP export payload into Supabase."""
    row = {
        "run_id": payload.get("run_id", "unknown"),
        "label": payload.get("label", "unknown"),
        "schema_version": payload.get("schema_version", "chit.cgp.v0.2"),
        "envelope_type": payload.get("envelope_type", "geometry.wealth.v1"),
        "state_vector": payload.get("state_vector", {}),
        "anchor": payload.get("anchor", []),
        "payload": payload,
        "signature": payload.get("signature"),
        "signed_at": payload.get("signed_at"),
        "source_simulation_id": payload.get("source_simulation_id"),
        "source_url": payload.get("source_url"),
    }

    endpoint = f"{url}/rest/v1/wealth_cgp_exports"
    response = requests.post(endpoint, headers=headers(key), json=row)
    response.raise_for_status()
    print(f"Inserted CGP export: run_id={row['run_id']} label={row['label']} status={response.status_code}")


def import_file(path: Path, url: str, key: str) -> None:
    payload = json.loads(path.read_text())
    insert_cgp_export(payload, url, key)


def watch_directory(directory: Path, url: str, key: str, interval: int = 5) -> None:
    seen = {p.stat().st_mtime for p in directory.glob("*.cgp.json")}
    print(f"Watching {directory} for *.cgp.json files (interval={interval}s)")
    while True:
        for path in directory.glob("*.cgp.json"):
            mtime = path.stat().st_mtime
            if mtime in seen:
                continue
            try:
                import_file(path, url, key)
                seen.add(mtime)
            except Exception as exc:
                print(f"Failed to import {path}: {exc}", file=sys.stderr)
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="PMOVES Wealth CGP Consumer")
    parser.add_argument("--file", type=Path, help="Path to a single CGP export JSON file")
    parser.add_argument("--watch", type=Path, help="Directory to watch for .cgp.json files")
    parser.add_argument("--interval", type=int, default=5, help="Watch poll interval in seconds")
    args = parser.parse_args()

    if not args.file and not args.watch:
        parser.error("Specify either --file or --watch")

    url = get_supabase_url()
    key = get_service_role_key()
    if not key:
        raise SystemExit("No Supabase service role key found in environment")

    if args.file:
        import_file(args.file, url, key)
    elif args.watch:
        if not args.watch.is_dir():
            raise SystemExit(f"Watch path is not a directory: {args.watch}")
        watch_directory(args.watch, url, key, args.interval)


if __name__ == "__main__":
    main()
