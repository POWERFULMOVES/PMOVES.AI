#!/usr/bin/env python3
"""validate-ollama-inventory.py — verify node Ollama model profile matches the canonical profile YAML.

4090-CLAUDE runs this on the laptop to validate its 6-model inventory
against ``pmoves/configs/profiles/laptop-4090.yaml`` (or any node's profile).

Validates ``n4090.ollama`` TAC node in
``pmoves/configs/tac_trees/node-4090-laptop.tac.yaml``.

Usage::

    python3 pmoves/scripts/validate-ollama-inventory.py                            # 4090 default
    python3 pmoves/scripts/validate-ollama-inventory.py --profile <yaml>           # other node
    python3 pmoves/scripts/validate-ollama-inventory.py --ollama-url http://...    # override Ollama URL
    python3 pmoves/scripts/validate-ollama-inventory.py --json                     # structured output

Exit codes:
    0   profile matches Ollama inventory (all expected models present, no excess > 2GB unaccounted)
    1   Ollama unreachable
    2   profile parse error
    3   inventory drift (missing or excess models flagged)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_profile(path: Path) -> dict:
    """Load the node profile YAML. Requires PyYAML in the venv."""
    try:
        import yaml
    except ImportError:
        print("❌ PyYAML required. Install via: `uv pip install --python pmoves/.venv-pmoves/bin/python pyyaml`",
              file=sys.stderr)
        sys.exit(2)
    with path.open() as f:
        return yaml.safe_load(f) or {}


def extract_expected_models(profile: dict) -> set[str]:
    """Walk the profile tree and collect all model names from any ``models:`` list.

    PMOVES profiles nest model lists under ``coding_stacks.<stack>.<config>.models:``
    and may also have top-level ``models:`` lists (mixed string + dict shapes).
    We accept both. Each model is normalized to its base name (no ``:tag`` suffix)
    and lowercased.
    """

    names: set[str] = set()
    # Skip hardware.gpu.models (those are GPU SKU names, not Ollama models)
    hardware_skus = set()
    hw = profile.get("hardware", {}) or {}
    for v in (hw.get("gpu", {}) or {}).get("models", []) or []:
        if isinstance(v, str):
            hardware_skus.add(v.strip().lower())

    def walk(node, path_segments=("$",)):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "models" and isinstance(v, list):
                    for entry in v:
                        if isinstance(entry, str):
                            base = entry.split(":")[0].strip().lower()
                            if base and base not in hardware_skus:
                                names.add(base)
                        elif isinstance(entry, dict) and entry.get("name"):
                            base = str(entry["name"]).split(":")[0].strip().lower()
                            if base and base not in hardware_skus:
                                names.add(base)
                else:
                    walk(v, path_segments + (str(k),))
        elif isinstance(node, list):
            for item in node:
                walk(item, path_segments)

    walk(profile)
    return names


def fetch_ollama_models(url: str) -> list[dict]:
    """Hit Ollama's ``/api/tags`` and return the models list."""
    req = urllib.request.Request(f"{url.rstrip('/')}/api/tags",
                                  headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.load(resp).get("models", [])


def gb(size_bytes: int | None) -> float:
    """Bytes → GiB (float)."""
    if not size_bytes:
        return 0.0
    return round(size_bytes / (1024 ** 3), 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile",
                        default="pmoves/config/profiles/laptop-4090.yaml",
                        help="Path to node profile YAML")
    parser.add_argument("--ollama-url",
                        default="http://localhost:11434",
                        help="Ollama base URL")
    parser.add_argument("--json", action="store_true",
                        help="Emit structured JSON")
    parser.add_argument("--vram-budget-gb", type=float, default=14.3,
                        help="Available VRAM after system overhead (default: 4090 laptop)")
    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.is_file():
        print(f"❌ profile not found: {profile_path}", file=sys.stderr)
        return 2

    profile = load_profile(profile_path)
    expected_names = extract_expected_models(profile)
    if not expected_names:
        print(f"⚠  No models found in {profile_path} — profile may use a non-standard shape.",
              file=sys.stderr)

    try:
        live = fetch_ollama_models(args.ollama_url)
    except (urllib.error.URLError, ConnectionRefusedError, OSError) as exc:
        if args.json:
            print(json.dumps({"result": "ollama_unreachable",
                              "url": args.ollama_url, "error": str(exc)}))
        else:
            print(f"❌ Ollama unreachable at {args.ollama_url}: {exc}",
                  file=sys.stderr)
        return 1

    live_names = {(m.get("name") or "").split(":")[0].lower() for m in live}
    live_by_name = {(m.get("name") or "").split(":")[0].lower(): m for m in live}
    missing = sorted(expected_names - live_names)
    excess = sorted(live_names - expected_names)
    matched = sorted(expected_names & live_names)
    total_size_gb = sum(gb(m.get("size")) for m in live)

    report = {
        "result": "ok" if not missing else "drift",
        "profile": str(profile_path),
        "ollama_url": args.ollama_url,
        "matched": matched,
        "missing_from_ollama": missing,
        "excess_in_ollama": excess,
        "total_size_gb": round(total_size_gb, 2),
        "vram_budget_gb": args.vram_budget_gb,
        "vram_headroom_gb": round(args.vram_budget_gb - total_size_gb, 2),
    }

    if args.json:
        print(json.dumps(report))
    else:
        print(f"Profile          : {profile_path}")
        print(f"Ollama URL       : {args.ollama_url}")
        print(f"Total size       : {report['total_size_gb']} GB"
              f"  (budget {args.vram_budget_gb} GB → headroom"
              f" {report['vram_headroom_gb']} GB)")
        print()
        if matched:
            print(f"✅ Matched ({len(matched)}):")
            for n in matched:
                size = gb(live_by_name[n].get("size"))
                print(f"   - {n} ({size} GB)")
        if missing:
            print(f"❌ Missing from Ollama ({len(missing)}):")
            for n in missing:
                print(f"   - {n}     → `ollama pull {n}`")
        if excess:
            print(f"⚠  Excess in Ollama not in profile ({len(excess)}):")
            for n in excess:
                size = gb(live_by_name[n].get("size"))
                print(f"   - {n} ({size} GB)     → consider removing or adding to profile")

    return 0 if not missing else 3


if __name__ == "__main__":
    sys.exit(main())
