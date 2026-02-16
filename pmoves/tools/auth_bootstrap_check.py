#!/usr/bin/env python3
"""Validate PMOVES auth bootstrap readiness and secondary setup state."""

from __future__ import annotations

import argparse
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / "env.shared"
DEFAULT_AUTH_HEALTH_URL = "http://127.0.0.1:65421/auth/v1/health"
DEFAULT_BOOT_EMAIL = "operator@pmoves.local"


@dataclass
class Finding:
    level: str  # "error" | "warn" | "ok"
    code: str
    message: str


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


def _is_true(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _looks_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    trimmed = value.strip()
    if not trimmed:
        return True
    lowered = trimmed.lower()
    looks_example_email = lowered.endswith("@example.com")
    host = ""
    try:
        candidate = trimmed if "://" in trimmed else f"https://{trimmed}"
        host = (urllib.parse.urlparse(candidate).hostname or "").lower()
    except Exception:
        host = ""
    looks_example_host = host in {"example.com", "www.example.com"}
    return (
        lowered.startswith("placeholder_")
        or "your_" in lowered
        or looks_example_email
        or looks_example_host
        or lowered in {"changeme", "change_me", "none", "null"}
    )


def _looks_email(value: str | None) -> bool:
    if value is None:
        return False
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()) is not None


def _http_ok(url: str, timeout: float = 4.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            code = getattr(response, "status", 200)
            if code == 200:
                return True, f"http {code}"
            return False, f"http {code}"
    except urllib.error.HTTPError as exc:
        return False, f"http {exc.code}"
    except Exception as exc:  # pragma: no cover - network edge behavior
        return False, str(exc)


def _require_key(
    env: Dict[str, str],
    *,
    key: str,
    findings: List[Finding],
    code: str,
    label: str,
) -> bool:
    value = env.get(key, "")
    if _looks_placeholder(value):
        findings.append(Finding("error", code, f"{label} is missing or placeholder ({key})."))
        return False
    findings.append(Finding("ok", code, f"{label} is set ({key})."))
    return True


def run_checks(
    env: Dict[str, str],
    *,
    mode: str,
    auth_health_url: str,
) -> List[Finding]:
    findings: List[Finding] = []

    ok, detail = _http_ok(auth_health_url)
    if ok:
        findings.append(Finding("ok", "auth.health", f"Supabase auth health reachable ({detail}) at {auth_health_url}"))
    else:
        findings.append(Finding("error", "auth.health", f"Supabase auth health check failed ({detail}) at {auth_health_url}"))

    boot_email = env.get("SUPABASE_BOOT_USER_EMAIL", "").strip()
    if mode in {"jwt", "hybrid"}:
        if not _looks_email(boot_email):
            findings.append(Finding("error", "auth.boot_email", "SUPABASE_BOOT_USER_EMAIL is missing or invalid."))
        else:
            findings.append(Finding("ok", "auth.boot_email", f"Boot user email configured: {boot_email}"))
    elif mode == "google":
        if _looks_email(boot_email):
            findings.append(Finding("ok", "auth.boot_email", f"Boot user email configured (optional in google mode): {boot_email}"))
        else:
            findings.append(Finding("warn", "auth.boot_email", "Boot user email not set (optional in google mode)."))

    if boot_email and boot_email.lower() == DEFAULT_BOOT_EMAIL.lower():
        findings.append(
            Finding(
                "warn",
                "auth.default_email",
                f"Using default boot email ({DEFAULT_BOOT_EMAIL}); set your real email via SUPABASE_BOOT_USER_EMAIL.",
            )
        )

    has_jwt = not _looks_placeholder(env.get("SUPABASE_BOOT_USER_JWT")) or not _looks_placeholder(
        env.get("NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT")
    )
    if mode == "jwt":
        if has_jwt:
            findings.append(Finding("ok", "auth.jwt", "Boot JWT present for password/JWT mode."))
        else:
            findings.append(Finding("error", "auth.jwt", "Boot JWT missing (SUPABASE_BOOT_USER_JWT / NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT)."))

    google_enabled = _is_true(env.get("SUPABASE_AUTH_EXTERNAL_GOOGLE_ENABLED"))
    google_client_ok = not _looks_placeholder(env.get("SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID"))
    google_secret_ok = not _looks_placeholder(env.get("SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET"))

    if mode == "google":
        if not google_enabled:
            findings.append(Finding("error", "auth.google_enabled", "SUPABASE_AUTH_EXTERNAL_GOOGLE_ENABLED is not true."))
        if not google_client_ok:
            findings.append(Finding("error", "auth.google_client_id", "SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID missing/placeholder."))
        if not google_secret_ok:
            findings.append(Finding("error", "auth.google_secret", "SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET missing/placeholder."))
        if google_enabled and google_client_ok and google_secret_ok:
            findings.append(Finding("ok", "auth.google", "Google OAuth settings look ready."))

    if mode == "hybrid":
        if has_jwt:
            findings.append(Finding("ok", "auth.jwt", "Boot JWT present (hybrid mode)."))
        if google_enabled and google_client_ok and google_secret_ok:
            findings.append(Finding("ok", "auth.google", "Google OAuth settings present (hybrid mode)."))
        if not has_jwt and not (google_enabled and google_client_ok and google_secret_ok):
            findings.append(
                Finding(
                    "error",
                    "auth.hybrid",
                    "Hybrid mode requires either boot JWT or complete Google OAuth config.",
                )
            )

    _require_key(
        env,
        key="MEILI_MASTER_KEY",
        findings=findings,
        code="secondary.meili",
        label="Meilisearch master key",
    )
    _require_key(
        env,
        key="FIREFLY_APP_KEY",
        findings=findings,
        code="secondary.firefly",
        label="PMOVES-Wealth app key",
    )
    _require_key(
        env,
        key="AGENT_ZERO_EVENTS_TOKEN",
        findings=findings,
        code="secondary.agent_zero",
        label="Agent Zero events token",
    )

    return findings


def _print_report(findings: Iterable[Finding], *, mode: str, strict: bool) -> int:
    findings_list = list(findings)
    errors = [item for item in findings_list if item.level == "error"]
    warns = [item for item in findings_list if item.level == "warn"]
    oks = [item for item in findings_list if item.level == "ok"]

    print("Auth Bootstrap Check")
    print(f"- mode: {mode}")
    print(f"- strict: {'true' if strict else 'false'}")
    print("")

    for item in findings_list:
        prefix = "✅" if item.level == "ok" else ("⚠️ " if item.level == "warn" else "❌")
        print(f"{prefix} [{item.code}] {item.message}")

    print("")
    print(f"Summary: ok={len(oks)} warn={len(warns)} error={len(errors)}")

    if errors:
        return 1
    if strict and warns:
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Path to env file to check.")
    parser.add_argument(
        "--mode",
        default="jwt",
        choices=("jwt", "google", "hybrid", "skip"),
        help="Auth mode for checks (default: jwt).",
    )
    parser.add_argument(
        "--auth-health-url",
        default=DEFAULT_AUTH_HEALTH_URL,
        help="Supabase auth health endpoint (default: local CLI stack).",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args(argv)

    if args.mode == "skip":
        print("Auth Bootstrap Check")
        print("- mode: skip")
        print("")
        print("⚠️  Auth checks skipped by mode.")
        return 0

    env_file = args.env_file.expanduser().resolve()
    env = _parse_env_file(env_file)
    findings = run_checks(env, mode=args.mode, auth_health_url=args.auth_health_url)
    return _print_report(findings, mode=args.mode, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
