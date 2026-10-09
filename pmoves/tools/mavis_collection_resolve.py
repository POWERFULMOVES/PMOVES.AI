#!/usr/bin/env python3
"""Mavis Collection — Manifest resolver + 3-step probe gate.

Companion to pmoves/configs/mavis_collection/manifest.schema.yaml (v1.0).

Subcommands:
    validate    Validate a manifest YAML against manifest.schema.yaml (subset).
    resolve     Resolve auth + quota + chat via the 3-step probe gate.
    probe       Run the 3-step probe gate without manifest context (smoke test).

Per DARKXSIDE practice (2026-09-16, no-workarounds + SDK + doc provenance):
the probe IS the contract. Before treating a credential as wired-up, run all
three steps. A credential that passes auth but fails quota (e.g. pay-as-you-go
key on a Token Plan subscription) is NOT wired-up.

Per agent memory entry "MiniMax API key formats: sk-cp vs sk-api" (2026-10-05):
Token Plan keys (sk-cp-...) and pay-as-you-go keys (sk-api-...) are not
interchangeable. Auth passes for both; only Token Plan keys have credit in
the `model_name: general` quota bucket.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("[error] PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# Paths
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "pmoves" / "configs" / "mavis_collection" / "manifest.schema.yaml"
DEFAULT_MANIFEST = Path.home() / ".mavis" / "collection" / "manifest.yaml"
MMX_CONFIG = Path.home() / ".mmx" / "config.json"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Validate manifest against the schema. Returns list of errors (empty = OK).

    Subset of JSON Schema 2020-12 — enough for our needs without external
    dependency. Each error is human-readable.
    """
    errors: list[str] = []

    # Top-level required keys
    for k in ("spec", "meta", "identity", "super_nodes"):
        if k not in manifest:
            errors.append(f"missing required field: {k}")

    # spec must be pmoves.bootstrap/v1
    if manifest.get("spec") != "pmoves.bootstrap/v1":
        errors.append(
            f"spec must be 'pmoves.bootstrap/v1' (got {manifest.get('spec')!r})"
        )

    # meta required fields
    meta = manifest.get("meta", {})
    for k in ("schema_version", "created", "operator", "home"):
        if k not in meta:
            errors.append(f"meta missing required field: {k}")
    if "schema_version" in meta and not re.match(r"^[0-9]+\.[0-9]+$", str(meta["schema_version"])):
        errors.append(f"meta.schema_version must match major.minor (got {meta['schema_version']!r})")

    # identity required fields
    identity = manifest.get("identity", {})
    if "agent" not in identity:
        errors.append("identity.agent required")
    if "form_ref" not in identity:
        errors.append("identity.form_ref required")

    # super_nodes — each section must be a list (if present)
    super_nodes = manifest.get("super_nodes", {})
    if not isinstance(super_nodes, dict):
        errors.append(f"super_nodes must be an object (got {type(super_nodes).__name__})")
        return errors

    for section, entries in super_nodes.items():
        if not isinstance(entries, list):
            errors.append(f"super_nodes.{section} must be a list (got {type(entries).__name__})")
            continue
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"super_nodes.{section}[{i}] must be an object")
                continue
            # Each entry must have at least one pointer (ref / source / spec / design / endpoint / constellation_id / provider)
            pointer_keys = {"ref", "source", "spec", "design", "endpoint", "constellation_id", "provider"}
            if not (set(entry.keys()) & pointer_keys):
                errors.append(f"super_nodes.{section}[{i}] has no pointer key")

    return errors


def read_mmx_config() -> dict[str, Any] | None:
    """Read mmx auth state from ~/.mmx/config.json. Returns None if missing."""
    if not MMX_CONFIG.exists():
        return None
    try:
        return load_json(MMX_CONFIG)
    except (json.JSONDecodeError, OSError):
        return None


def run_mmx_auth_status() -> dict[str, Any]:
    """Run `mmx auth status` and parse JSON output. Returns dict or empty dict on error."""
    try:
        result = subprocess.run(
            ["mmx", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        pass
    return {}


def run_mmx_quota_show() -> dict[str, Any]:
    """Run `mmx quota show` and parse JSON output."""
    try:
        result = subprocess.run(
            ["mmx", "quota", "show", "--non-interactive", "--quiet"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        pass
    return {}


def run_mmx_text_chat(message: str, model: str = "MiniMax-M3") -> dict[str, Any]:
    """Run `mmx text chat` and return response or error dict."""
    try:
        result = subprocess.run(
            [
                "mmx", "text", "chat",
                "--message", message,
                "--model", model,
                "--non-interactive",
                "--quiet",
                "--max-tokens", "16",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                return {"ok": True, "response": json.loads(result.stdout)}
            except json.JSONDecodeError:
                return {"ok": True, "response": result.stdout.strip()}
        return {
            "ok": False,
            "error_code": result.returncode,
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}


def three_step_probe(provider: str = "minimax") -> dict[str, Any]:
    """The 3-step probe gate. Per memory entry 2026-10-05.

    Steps:
      1. auth status — does the key authenticate?
      2. quota show — does the key have credit in the expected bucket?
      3. text chat ping — does the key pass the billing gate end-to-end?

    Returns dict with per-step results + overall verdict.
    """
    result: dict[str, Any] = {
        "provider": provider,
        "step_1_auth": {},
        "step_2_quota": {},
        "step_3_chat": {},
        "wired_up": False,
        "errors": [],
    }

    # Step 1: auth
    auth = run_mmx_auth_status()
    result["step_1_auth"] = auth
    if auth.get("base_resp", {}).get("status_code") != 0:
        result["errors"].append("step_1_auth_failed")
        return result

    # Step 2: quota — check for Token Plan bucket (general model)
    quota = run_mmx_quota_show()
    result["step_2_quota"] = quota
    model_remains = quota.get("model_remains", [])
    general_bucket = next((m for m in model_remains if m.get("model_name") == "general"), None)
    if not general_bucket:
        result["errors"].append("step_2_no_general_quota_bucket")
        return result

    # Check that status indicates active quota
    if general_bucket.get("current_interval_status") not in (1,):  # 1 = active
        result["errors"].append(
            f"step_2_quota_status={general_bucket.get('current_interval_status')} (expected 1=active)"
        )
        return result

    # Step 3: chat ping
    chat = run_mmx_text_chat("ping from mavis orchestrator", model="MiniMax-M3")
    result["step_3_chat"] = chat
    if not chat.get("ok"):
        result["errors"].append(f"step_3_chat_failed: {chat.get('error') or chat.get('stderr')}")
        return result

    result["wired_up"] = True
    return result


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a manifest YAML against the schema."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[error] manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = load_yaml(manifest_path)
    except yaml.YAMLError as e:
        print(f"[error] YAML parse failed: {e}", file=sys.stderr)
        return 2

    errors = validate_manifest(manifest)
    if errors:
        print(f"[FAIL] {manifest_path}", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[OK] {manifest_path} validates against pmoves.bootstrap/v1 (schema v{manifest['meta']['schema_version']})")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Resolve auth + quota + chat for the manifest's auth entries."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[error] manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        manifest = load_yaml(manifest_path)
    except yaml.YAMLError as e:
        print(f"[error] YAML parse failed: {e}", file=sys.stderr)
        return 2

    auth_entries = manifest.get("super_nodes", {}).get("auth", [])
    if not auth_entries:
        print("[warn] no auth entries in manifest", file=sys.stderr)
        return 0

    overall_ok = True
    for entry in auth_entries:
        provider = entry.get("provider", "unknown")
        probe = entry.get("probe", "none")

        print(f"[resolve] provider={provider}  probe={probe}")

        if probe == "3-step-gate":
            result = three_step_probe(provider=provider)
            print(f"  step_1_auth: status_code={result['step_1_auth'].get('base_resp', {}).get('status_code')}")
            quota_bucket = next(
                    (m for m in result["step_2_quota"].get("model_remains", []) if m.get("model_name") == "general"),
                    {},
                )
            print(
                f"  step_2_quota: general bucket active={quota_bucket.get('current_interval_status') == 1}"
                f" remaining={quota_bucket.get('current_interval_remaining_percent')}%"
            )
            chat_resp = result["step_3_chat"].get("response", {})
            chat_preview = (
                chat_resp.get("content", "")[:60]
                if isinstance(chat_resp, dict)
                else str(chat_resp)[:60]
            )
            print(f"  step_3_chat: ok={result['step_3_chat'].get('ok')}  preview={chat_preview!r}")

            if not result["wired_up"]:
                print(f"  - FAIL: {', '.join(result['errors'])}", file=sys.stderr)
                overall_ok = False
            else:
                print("  - PASS: 3-step probe green")
        elif probe == "online-status-only":
            print(f"  - SKIP: probe=online-status-only (operator trust)")
        else:
            print(f"  - SKIP: probe=none (operator trust)")

    return 0 if overall_ok else 1


def cmd_probe(args: argparse.Namespace) -> int:
    """Run the 3-step probe gate without manifest context."""
    provider = args.provider or "minimax"
    print(f"[probe] 3-step gate for provider={provider}")
    result = three_step_probe(provider=provider)

    print(f"  step_1_auth: {result['step_1_auth'].get('method', 'unknown')} source={result['step_1_auth'].get('source', 'unknown')}")
    quota = next(
        (m for m in result["step_2_quota"].get("model_remains", []) if m.get("model_name") == "general"),
        {},
    )
    print(f"  step_2_quota: general={quota.get('current_interval_remaining_percent', '?')}% weekly={quota.get('current_weekly_remaining_percent', '?')}%")
    chat_ok = result["step_3_chat"].get("ok")
    print(f"  step_3_chat: ok={chat_ok}")
    print(f"  wired_up: {result['wired_up']}")
    if result["errors"]:
        print(f"  errors: {', '.join(result['errors'])}")

    return 0 if result["wired_up"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mavis_collection_resolve.py",
        description="Validate + resolve the Mavis Collection manifest.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate manifest against schema")
    p_validate.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p_validate.set_defaults(func=cmd_validate)

    p_resolve = sub.add_parser("resolve", help="Resolve auth entries via 3-step probe")
    p_resolve.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p_resolve.set_defaults(func=cmd_resolve)

    p_probe = sub.add_parser("probe", help="Run 3-step probe gate standalone")
    p_probe.add_argument("--provider", default="minimax")
    p_probe.set_defaults(func=cmd_probe)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())