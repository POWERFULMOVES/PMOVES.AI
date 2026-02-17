#!/usr/bin/env python3
"""Security-focused audit for PMOVES secrets/credential plumbing."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Finding:
    level: str
    message: str
    path: str | None = None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def candidate_files() -> Iterable[Path]:
    allowed = {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"}
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() not in allowed:
            continue
        yield path


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in read_text(path).splitlines():
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_placeholder(value: str) -> bool:
    if not value:
        return True
    lower = value.lower()
    placeholders = (
        "change_me",
        "placeholder",
        "your-",
        "your_",
        "replace",
        "example",
        "${",
    )
    return any(token in lower for token in placeholders)


def main() -> int:
    findings: list[Finding] = []
    legacy_path_allowlist = {
        "pmoves/tools/secrets_hardening_audit.py",
        "pmoves/docs/SECRETS_CREDENTIALS_AUDIT_2026-02-14.md",
    }

    # 1) Legacy double-pmoves CGP path should be gone.
    legacy_token = "pmoves/pmoves/data/chit/env.cgp.json"
    for path in candidate_files():
        relative = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if relative in legacy_path_allowlist:
            continue
        text = read_text(path)
        if legacy_token in text:
            findings.append(
                Finding(
                    "ERROR",
                    "Legacy CHIT path still present; use pmoves/data/chit/env.cgp.json.",
                    relative,
                )
            )

    # 2) Workflow should write local bundles outside the repo tree.
    sync_workflow = REPO_ROOT / ".github/workflows/sync-secrets-local.yml"
    if sync_workflow.exists():
        workflow_text = read_text(sync_workflow)
        if "/home/pmoves/PMOVES.AI/pmoves/data/chit" in workflow_text:
            findings.append(
                Finding(
                    "ERROR",
                    "sync-secrets-local workflow writes secret material inside repo path.",
                    str(sync_workflow.relative_to(REPO_ROOT)),
                )
            )
        if "include_cleartext=False" not in workflow_text:
            findings.append(
                Finding(
                    "ERROR",
                    "sync-secrets-local workflow does not enforce no-cleartext CHIT encoding.",
                    str(sync_workflow.relative_to(REPO_ROOT)),
                )
            )

    # 3) Hostinger exports must not carry session cookies.
    cos_dir = REPO_ROOT / "docs/Hostingerapi/COS"
    cookie_pattern = re.compile(r'"cookie"\s*:\s*"(?!REDACTED_SESSION_COOKIE)[^"]+"')
    if cos_dir.exists():
        for path in cos_dir.glob("*.json"):
            text = read_text(path)
            if cookie_pattern.search(text):
                findings.append(
                    Finding(
                        "ERROR",
                        "JSON export still contains raw cookie header.",
                        str(path.relative_to(REPO_ROOT)),
                    )
                )
            if "n8n-auth=" in text:
                findings.append(
                    Finding(
                        "ERROR",
                        "JSON export still contains n8n-auth token material.",
                        str(path.relative_to(REPO_ROOT)),
                    )
                )

    # 4) env.supabase should be template-style only in git.
    env_supabase = REPO_ROOT / "pmoves/env.supabase"
    if env_supabase.exists():
        values = parse_env_file(env_supabase)
        critical = [
            "POSTGRES_PASSWORD",
            "JWT_SECRET",
            "ANON_KEY",
            "SERVICE_ROLE_KEY",
            "DASHBOARD_PASSWORD",
            "SECRET_KEY_BASE",
            "VAULT_ENC_KEY",
            "PG_META_CRYPTO_KEY",
            "LOGFLARE_PUBLIC_ACCESS_TOKEN",
            "LOGFLARE_PRIVATE_ACCESS_TOKEN",
        ]
        for key in critical:
            value = values.get(key, "")
            if not is_placeholder(value):
                findings.append(
                    Finding(
                        "ERROR",
                        f"pmoves/env.supabase has non-placeholder value for {key}.",
                        str(env_supabase.relative_to(REPO_ROOT)),
                    )
                )

    # 5) bootstrap script should include user-scoped CHIT lookup paths.
    bootstrap_script = REPO_ROOT / "scripts/bootstrap_credentials.sh"
    if bootstrap_script.exists():
        text = read_text(bootstrap_script)
        has_user_path = "pmoves/chit/env.cgp.json" in text and (
            "XDG_CONFIG_HOME" in text or "$HOME/.config" in text
        )
        if not has_user_path:
            findings.append(
                Finding(
                    "ERROR",
                    "bootstrap_credentials.sh missing user config CHIT lookup path.",
                    str(bootstrap_script.relative_to(REPO_ROOT)),
                )
            )

    # 6) root gitignore should protect repo-local CHIT bundle.
    gitignore = REPO_ROOT / ".gitignore"
    if gitignore.exists():
        text = read_text(gitignore)
        if "pmoves/data/chit/env.cgp.json" not in text:
            findings.append(
                Finding(
                    "ERROR",
                    ".gitignore missing pmoves/data/chit/env.cgp.json entry.",
                    str(gitignore.relative_to(REPO_ROOT)),
                )
            )

    # 7) Focus services should use services.common.env helpers for secret vars.
    secret_env_keys = (
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
        "CHIT_PASSPHRASE",
        "FLUTE_API_KEY",
        "OPENAI_API_KEY",
        "TENSORZERO_API_KEY",
        "ARCHON_API_TOKEN",
        "E2B_API_KEY",
        "NEO4J_PASSWORD",
        "NEO4J_PASS",
    )
    sensitive_pattern = re.compile(
        r'os\.(?:getenv|environ\.get)\(\s*[\'"]('
        + "|".join(re.escape(key) for key in secret_env_keys)
        + r')[\'"]'
    )
    focus_roots = (
        REPO_ROOT / "pmoves/services/common",
        REPO_ROOT / "pmoves/services/gateway",
        REPO_ROOT / "pmoves/services/flute-gateway",
        REPO_ROOT / "pmoves/services/evo-controller",
        REPO_ROOT / "pmoves/services/evoswarm",
        REPO_ROOT / "pmoves/services/agent-zero",
        REPO_ROOT / "pmoves/services/archon",
    )
    for root in focus_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            relative = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            if "/tests/" in relative or relative.endswith("_test.py") or relative.endswith("conftest.py"):
                continue
            text = read_text(path)
            for match in sensitive_pattern.finditer(text):
                findings.append(
                    Finding(
                        "ERROR",
                        f"Direct os.getenv/os.environ.get on secret key '{match.group(1)}'; use services.common.env helpers for *_FILE support.",
                        relative,
                    )
                )
                break

    if findings:
        print("Secrets hardening audit: FAILED")
        for finding in findings:
            if finding.path:
                print(f"[{finding.level}] {finding.path}: {finding.message}")
            else:
                print(f"[{finding.level}] {finding.message}")
        return 1

    print("Secrets hardening audit: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
