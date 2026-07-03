#!/usr/bin/env python3
"""Splice model-registry-generated [models.*] blocks into tensorzero.toml.

The static file owns everything outside the marker pair; the registry owns
everything inside. Only model tables whose key starts with ``registry_`` are
spliced, so the registry cannot clobber static cloud provider blocks.

CLI:
    python pmoves/tools/tz_registry_sync.py [--registry-url http://127.0.0.1:8110] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]
TZ_TOML = PMOVES / "tensorzero" / "config" / "tensorzero.toml"
BEGIN_RE = re.compile(r"^# BEGIN REGISTRY-MANAGED MODELS.*$", re.M)
END_RE = re.compile(r"^# END REGISTRY-MANAGED MODELS.*$", re.M)


def _extract_registry_tables(registry_toml_text: str) -> str:
    """Return only [models.registry_*] tables (with their provider subtables)."""
    lines = registry_toml_text.splitlines()
    out: list[str] = []
    keep = False
    for line in lines:
        header = re.match(r"^\[([A-Za-z0-9_.\-]+)\]", line)
        if header:
            keep = header.group(1).startswith("models.registry_")
        if keep:
            out.append(line)
    return "\n".join(out).strip() + ("\n" if out else "")


def synthesize_lane_blocks(models_payload: dict) -> str:
    """Build [models.registry_*] TOML from /api/models items carrying
    registry_* aliases. Data-driven: model ids, api_base, and lane names all
    come from Supabase rows — nothing hardcoded here."""
    out: list[str] = []
    for item in models_payload.get("items", []):
        aliases = [
            a.get("alias") for a in (item.get("aliases") or [])
            if isinstance(a, dict) and str(a.get("alias", "")).startswith("registry_")
        ]
        if not aliases:
            continue
        api_base = item.get("api_base") or "http://pmoves-ollama:11434/v1"
        provider_type = "openai"  # all local backends are OpenAI-compatible
        for alias in aliases:
            out.extend([
                f"[models.{alias}]",
                'routing = ["local_active"]',
                "",
                f"[models.{alias}.providers.local_active]",
                f'type = "{provider_type}"',
                f'api_base = "{api_base}"',
                f'model_name = "{item["model_id"]}"',
                'api_key_location = "none"',
                "",
            ])
    return "\n".join(out).strip() + ("\n" if out else "")


def _table_names(body: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^\[models\.(registry_[A-Za-z0-9_]+)\]", body, re.M)}


def sync_registry_section(static_toml_text: str, registry_toml_text: str) -> str:
    begin = BEGIN_RE.search(static_toml_text)
    end = END_RE.search(static_toml_text)
    if not begin or not end or end.start() < begin.end():
        raise ValueError("REGISTRY-MANAGED MODELS markers missing or malformed")
    body = _extract_registry_tables(registry_toml_text)
    # Merge: lanes absent from the registry payload keep their existing
    # (bootstrap cloud-parent) blocks so function references never dangle.
    existing = _extract_registry_tables(static_toml_text[begin.end():end.start()])
    incoming = _table_names(body)
    kept: list[str] = []
    keep = False
    for line in existing.splitlines():
        header = re.match(r"^\[models\.(registry_[A-Za-z0-9_]+)", line)
        if header:
            keep = header.group(1) not in incoming
        if keep:
            kept.append(line)
    if kept:
        body = (body.rstrip() + "\n\n" + "\n".join(kept).strip() + "\n") if body.strip() else "\n".join(kept).strip() + "\n"
    return (
        static_toml_text[: begin.end()]
        + "\n\n"
        + body
        + "\n"
        + static_toml_text[end.start() :]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry-url", default="http://127.0.0.1:8110")
    ap.add_argument("--models-json", help="Path to a saved /api/models JSON payload; lane blocks are synthesized from aliases instead of fetching the registry TOML")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.models_json:
        import json
        payload = json.loads(Path(args.models_json).read_text(encoding="utf-8"))
        registry_text = synthesize_lane_blocks(payload)
    else:
        with urllib.request.urlopen(
            f"{args.registry_url}/api/tensorzero/config", timeout=15
        ) as resp:
            registry_text = resp.read().decode("utf-8")
    static_text = TZ_TOML.read_text(encoding="utf-8")
    merged = sync_registry_section(static_text, registry_text)
    if args.dry_run:
        sys.stdout.write(merged)
        return 0
    TZ_TOML.write_text(merged, encoding="utf-8")
    print(f"synced registry-managed models into {TZ_TOML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
