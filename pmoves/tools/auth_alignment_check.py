#!/usr/bin/env python3
"""Cross-tier credential consistency validator for PMOVES.AI.

Validates that credentials are consistent across all env tier files:
- JWT secrets match across all references
- NATS URLs include credentials
- MinIO access keys align with root user
- URL-embedded passwords are URL-encoded or safe
- No placeholder values in non-example files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Characters unsafe in the password segment of a URL
URL_UNSAFE_CHARS = set("/:@?#=+&")

# Patterns that indicate a placeholder value
PLACEHOLDER_PATTERNS = [
    re.compile(r".*_HERE$", re.IGNORECASE),
    re.compile(r"^changeme$", re.IGNORECASE),
    re.compile(r"^change_me$", re.IGNORECASE),
    re.compile(r"^your_", re.IGNORECASE),
    re.compile(r"^placeholder", re.IGNORECASE),
    re.compile(r"^example", re.IGNORECASE),
    re.compile(r"^none$", re.IGNORECASE),
    re.compile(r"^null$", re.IGNORECASE),
    re.compile(r"@example\.com$", re.IGNORECASE),
]


class Finding:
    """A single validation finding."""

    def __init__(self, group: str, level: str, message: str) -> None:
        self.group = group
        self.level = level  # "error", "warn", "ok"
        self.message = message

    def __str__(self) -> str:
        icon = {"error": "X", "warn": "!", "ok": "OK"}[self.level]
        return f"  [{icon}] {self.message}"


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    for pat in PLACEHOLDER_PATTERNS:
        if pat.match(value):
            return True
    return False


def _load_all_env_files(root: Path) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    """Load all env tier files and env.shared.

    Returns:
        (dict of filename -> key/value pairs, list of loaded filenames)
    """
    env_files = {}
    loaded = []

    candidates = [
        "env.shared",
        "env.tier-data",
        "env.tier-supabase",
        "env.tier-supabase.urlencoded",
        "env.tier-api",
        "env.tier-llm",
        "env.tier-worker",
        "env.tier-media",
        "env.tier-agent",
        "env.tier-ui",
    ]

    for name in candidates:
        path = root / name
        if path.exists():
            env_files[name] = _parse_env_file(path)
            loaded.append(name)

    return env_files, loaded


def _merged_values(env_files: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Merge all env files into a single dict (later files override)."""
    merged: Dict[str, str] = {}
    for values in env_files.values():
        merged.update(values)
    return merged


def check_jwt_alignment(merged: Dict[str, str]) -> List[Finding]:
    """Check JWT secret consistency across all aliases."""
    findings: List[Finding] = []
    jwt_keys = [
        "JWT_SECRET",
        "SUPABASE_JWT_SECRET",
        "GOTRUE_JWT_SECRET",
        "PGRST_JWT_SECRET",
    ]

    values = {}
    for key in jwt_keys:
        val = merged.get(key, "").strip()
        if val:
            values[key] = val

    if not values:
        findings.append(Finding("jwt", "warn", "No JWT secrets found in any env file"))
        return findings

    unique = set(values.values())
    if len(unique) == 1:
        findings.append(Finding("jwt", "ok", f"All {len(values)} JWT secret references match"))
    else:
        findings.append(Finding("jwt", "error",
            f"JWT secret mismatch: {len(unique)} distinct values across {list(values.keys())}"))

    return findings


def check_nats_auth(merged: Dict[str, str]) -> List[Finding]:
    """Check all NATS_URL values include credentials."""
    findings: List[Finding] = []
    nats_keys = [k for k in merged if "NATS_URL" in k.upper()]

    if not nats_keys:
        findings.append(Finding("nats", "warn", "No NATS_URL found in env files"))
        return findings

    all_good = True
    for key in nats_keys:
        val = merged[key]
        if "nats://" in val and "@" not in val:
            findings.append(Finding("nats", "error",
                f"{key}={val} — missing credentials (expected nats://user:pass@host)"))
            all_good = False

    if all_good:
        findings.append(Finding("nats", "ok", f"All {len(nats_keys)} NATS URL(s) include credentials"))

    return findings


def check_minio_alignment(merged: Dict[str, str]) -> List[Finding]:
    """Check MinIO credential consistency."""
    findings: List[Finding] = []

    access_key = merged.get("MINIO_ACCESS_KEY", "").strip()
    root_user = merged.get("MINIO_ROOT_USER", "").strip()
    secret_key = merged.get("MINIO_SECRET_KEY", "").strip()
    root_password = merged.get("MINIO_ROOT_PASSWORD", "").strip()

    if access_key and root_user and access_key != root_user:
        findings.append(Finding("minio", "error",
            f"MINIO_ACCESS_KEY ({access_key[:8]}...) != MINIO_ROOT_USER ({root_user[:8]}...)"))
    elif access_key and root_user:
        findings.append(Finding("minio", "ok", "MINIO_ACCESS_KEY matches MINIO_ROOT_USER"))
    elif not access_key and not root_user:
        findings.append(Finding("minio", "warn", "Neither MINIO_ACCESS_KEY nor MINIO_ROOT_USER set"))

    if secret_key and root_password and secret_key != root_password:
        findings.append(Finding("minio", "error",
            f"MINIO_SECRET_KEY != MINIO_ROOT_PASSWORD"))
    elif secret_key and root_password:
        findings.append(Finding("minio", "ok", "MINIO_SECRET_KEY matches MINIO_ROOT_PASSWORD"))

    return findings


def check_url_safe_passwords(merged: Dict[str, str]) -> List[Finding]:
    """Check passwords embedded in URLs are URL-safe or have encoded variants."""
    findings: List[Finding] = []

    password_keys = [
        "POSTGRES_PASSWORD",
        "SUPABASE_DB_PASSWORD",
    ]

    all_safe = True
    for key in password_keys:
        val = merged.get(key, "").strip()
        if not val:
            continue
        if URL_UNSAFE_CHARS & set(val):
            encoded_key = f"{key}_URLENCODED"
            encoded_val = merged.get(encoded_key, "").strip()
            expected = quote(val, safe="")
            if encoded_val == expected:
                findings.append(Finding("url-safe", "ok",
                    f"{key} has URL-unsafe chars but {encoded_key} is correctly set"))
            elif encoded_val:
                findings.append(Finding("url-safe", "error",
                    f"{encoded_key} exists but doesn't match expected encoding"))
                all_safe = False
            else:
                findings.append(Finding("url-safe", "error",
                    f"{key} contains URL-unsafe chars but {encoded_key} is missing. "
                    f"Run: make -C pmoves secrets-funnel"))
                all_safe = False

    if all_safe and not findings:
        findings.append(Finding("url-safe", "ok", "All URL-embedded passwords are safe"))

    return findings


def check_placeholders(
    env_files: Dict[str, Dict[str, str]],
) -> List[Finding]:
    """Check for placeholder values in non-example files."""
    findings: List[Finding] = []
    found = False

    for filename, values in env_files.items():
        if ".example" in filename:
            continue
        for key, val in values.items():
            if _is_placeholder(val):
                findings.append(Finding("placeholders", "warn",
                    f"{filename}: {key} looks like a placeholder ({val[:40]})"))
                found = True

    if not found:
        findings.append(Finding("placeholders", "ok", "No placeholder values detected"))

    return findings


def run_checks(root: Path) -> Tuple[Dict[str, List[Finding]], int]:
    """Run all alignment checks.

    Returns:
        (grouped findings, error count)
    """
    env_files, loaded = _load_all_env_files(root)
    if not loaded:
        return {"setup": [Finding("setup", "error", "No env files found")]}, 1

    merged = _merged_values(env_files)

    groups: Dict[str, List[Finding]] = {
        "jwt": check_jwt_alignment(merged),
        "nats": check_nats_auth(merged),
        "minio": check_minio_alignment(merged),
        "url-safe": check_url_safe_passwords(merged),
        "placeholders": check_placeholders(env_files),
    }

    errors = sum(1 for findings in groups.values() for f in findings if f.level == "error")
    return groups, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Project root")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings too")
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    groups, errors = run_checks(root)

    print("PMOVES.AI Auth Alignment Check")
    print("=" * 50)
    for group_name, findings in groups.items():
        status = "ERROR" if any(f.level == "error" for f in findings) else \
                 "WARN" if any(f.level == "warn" for f in findings) else "OK"
        print(f"\n[{status}] {group_name.upper()}")
        for f in findings:
            print(str(f))

    warnings = sum(1 for findings in groups.values() for f in findings if f.level == "warn")
    print(f"\n{'=' * 50}")
    print(f"Results: {errors} error(s), {warnings} warning(s)")

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
