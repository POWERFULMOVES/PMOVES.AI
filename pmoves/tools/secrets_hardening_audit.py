#!/usr/bin/env python3
"""Security-focused audit for PMOVES secrets/credential plumbing."""

from __future__ import annotations

import os
import re
import subprocess
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


def _is_pruned_dir(root: Path, name: str) -> bool:
    """True for directories whose entire subtree must not be audited.

    Linked worktrees are full repo copies; auditing them double-counts every finding
    against files this checkout owns. The top-level `.worktrees` layout is the one
    actually in use and was previously not excluded at all: with 190 repo copies
    under it, the audit reported 147 errors of which 147 came from `.worktrees` and
    ZERO from files this checkout owns. A gate that is permanently red reports
    nothing -- the 12 real warnings were buried under duplicate noise.

    `.worktrees` is matched as a plain directory name; the dotted form is
    distinctive enough that an accidental skip is implausible. `.claude/worktrees`
    is matched only as that exact adjacent pair, so an unrelated directory merely
    named `worktrees` is still audited (no blind spot).
    """
    if name in {".git", ".worktrees"}:
        return True
    return name == "worktrees" and root.name == ".claude"


def candidate_files() -> Iterable[Path]:
    allowed = {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"}
    # os.walk with in-place `dirnames` pruning, not rglob("*") + filter. rglob
    # TRAVERSES every excluded subtree and only then discards the results, so
    # filtering afterwards removes the false findings but not their cost. Both were
    # measured against the real repo, same 75329 files in scope and identical
    # findings either way:
    #
    #   rglob + filter   walk 265.2s   total 904.4s
    #   os.walk + prune  walk  12.9s   total 359.2s
    #
    # That is ~20x off the walk, but the audit is still NOT fast: ~6 minutes,
    # dominated by reading the files that remain in scope rather than by the walk.
    # Pruning fixes the wrong-results problem, not the slow-audit problem.
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not _is_pruned_dir(here, d)]
        for filename in filenames:
            path = here / filename
            if path.suffix.lower() not in allowed:
                continue
            # os.walk lists broken symlinks and other non-regular entries among
            # `filenames`; read_text() would then raise FileNotFoundError and abort
            # the whole audit over one dangling link left by local tooling. The
            # rglob version got this from its `path.is_file()` guard, which the
            # rewrite dropped. Ordered AFTER the suffix test on purpose: is_file()
            # is a stat syscall, and this way it only runs for the files that are
            # actually in scope rather than for all 75329 walked.
            if not path.is_file():
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

    # 8) Production-readiness gate: tier env files must have all .example keys populated.
    #    This catches the exact TensorZero failure scenario: .example declares a key,
    #    but secrets_sync.py didn't populate it because it wasn't in the CHIT manifest.
    project_root = REPO_ROOT / "pmoves"
    tier_names = ("data", "supabase", "api", "llm", "worker", "media", "agent", "ui")
    placeholder_tokens = (
        "placeholder_until_configured",
        "PLACEHOLDER",
        "change_me",
        "CHANGE_ME",
        "your-key-here",
        "YOUR_KEY_HERE",
        "xxx",
    )
    for tier in tier_names:
        example_path = project_root / f"env.tier-{tier}.example"
        runtime_path = project_root / f"env.tier-{tier}"
        if not example_path.exists() or not runtime_path.exists():
            continue
        example_keys = set(parse_env_file(example_path).keys())
        runtime_values = parse_env_file(runtime_path)
        runtime_keys = set(runtime_values.keys())

        # 8a) Keys in .example but missing from runtime = DRIFT
        missing_keys = sorted(example_keys - runtime_keys)
        if missing_keys:
            findings.append(
                Finding(
                    "WARN",
                    f"env.tier-{tier}: {len(missing_keys)} keys in .example but missing from runtime: {', '.join(missing_keys[:5])}{'...' if len(missing_keys) > 5 else ''}. "
                    f"Fix: add to secrets_manifest_v2.yaml and run 'make secrets-funnel'.",
                    str(runtime_path.relative_to(REPO_ROOT)),
                )
            )

        # 8b) Runtime keys with empty or placeholder values
        for key in sorted(runtime_keys):
            value = runtime_values.get(key, "")
            if not value:
                continue  # Empty is OK for optional keys
            if any(token in value for token in placeholder_tokens):
                findings.append(
                    Finding(
                        "WARN",
                        f"env.tier-{tier}: key {key} has placeholder value '{value[:30]}...'. "
                        f"Fix: set real value in env.shared and run 'make secrets-funnel'.",
                        str(runtime_path.relative_to(REPO_ROOT)),
                    )
                )

    # 8c) An alias and its canonical label both set in the shared env, with
    #     DIFFERENT values. Reported by SPARK on PR #2605: that node carries both
    #     CHIT names with different key material, so compose interpolation (which
    #     reads the shared env directly) hands containers one value while the
    #     host signing chain resolves the other — and signatures produced on the
    #     two sides cannot cross-verify. Nothing detected it, because every
    #     individual check sees a populated key and passes.
    #
    #     The manifest alias mechanism only governs GENERATED outputs. A
    #     hand-set divergent value in the shared env wins for every compose
    #     interpolation regardless, so this is not something the funnel can fix
    #     on its own — it needs a human to decide which value is authoritative.
    #
    #     WARN rather than ERROR: erroring would exit non-zero at funnel step 6
    #     and strand the very nodes that have the problem. Lengths are reported
    #     because they are enough to tell the two apart (SPARK saw 43 vs 64)
    #     without disclosing key material.
    shared_env = REPO_ROOT / "pmoves" / "env.shared"
    manifest_v2 = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"
    if shared_env.exists() and manifest_v2.exists():
        shared_values = parse_env_file(shared_env)
        try:
            import yaml  # type: ignore[import-untyped]

            entries = (yaml.safe_load(manifest_v2.read_text(encoding="utf-8")) or {}).get(
                "entries", []
            )
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            entries = []
            findings.append(
                Finding(
                    "WARN",
                    f"alias-divergence check skipped: cannot read the v2 manifest ({type(exc).__name__}: {exc})",
                    "pmoves/chit/secrets_manifest_v2.yaml",
                )
            )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source") or {}
            names = [source.get("label")] + list(source.get("aliases") or [])
            present = {
                n: shared_values[n]
                for n in names
                if n and shared_values.get(n, "").strip()
            }
            if len(set(present.values())) > 1:
                shape = ", ".join(
                    f"{n} (len {len(v)})" for n, v in sorted(present.items())
                )
                findings.append(
                    Finding(
                        "WARN",
                        f"alias divergence in env.shared: {shape} are the same manifest "
                        f"entry '{entry.get('id')}' but hold DIFFERENT values. Compose reads "
                        f"env.shared directly, so containers and host tooling can end up on "
                        f"different key material and signatures will not cross-verify. "
                        f"Fix: decide which value your existing receipts were signed "
                        f"with, then clear the other with "
                        f"'python pmoves/scripts/bootstrap_env.py --clear <KEY>' and run "
                        f"'make -C pmoves secrets-funnel'. Deleting the line by hand is "
                        f"NOT enough: secrets-local-hydrate treats an absent or empty "
                        f"value as a placeholder and writes the stale local.env value "
                        f"straight back on the next funnel run. --clear also records the "
                        f"key in pmoves/configs/secrets_cleared.yaml, which is what stops "
                        f"that re-population.",
                        "pmoves/env.shared",
                    )
                )

    # 9) Secret env files must NEVER be git-tracked. They are generated locally by
    #    secrets_sync and are gitignored — but git keeps tracking files added before
    #    an ignore rule was introduced, which is exactly how pmoves/env.tier-media
    #    leaked a live MinIO secret + a real Supabase service-role key into history
    #    (closed #1988, untracked in #1992). This CI-safe check fails hard on any
    #    tracked secret-env file so the leak class is caught automatically going
    #    forward. `.example` templates are meant to be tracked and are exempt.
    # `:(glob)` magic keeps `*` from crossing `/`, so these match only top-level
    # generated secret files under pmoves/ — not example templates nested under
    # pmoves/examples/**/*.env (a separate category). `env.shared.*` catches the
    # .generated / .pre-funnel snapshots (the pre-funnel snapshot is a real leak
    # Codex flagged on #1996); the .example exemption below keeps templates safe.
    tracked_pathspecs = [
        ":(glob)pmoves/env.shared",
        ":(glob)pmoves/env.shared.*",
        ":(glob)pmoves/env.tier-*",
        ":(glob)pmoves/.env",
        ":(glob)pmoves/.env.*",
    ]
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--", *tracked_pathspecs],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()
    except OSError:
        tracked = []  # git unavailable (non-repo context) — skip this check
    for rel in tracked:
        rel = rel.strip().replace("\\", "/")
        if not rel or rel.endswith(".example"):
            continue  # .example templates are supposed to be tracked
        findings.append(
            Finding(
                "ERROR",
                f"Secret env file is git-tracked (must be gitignored + local-only): {rel}. "
                "Fix: `git rm --cached` it, then rotate any exposed keys "
                "(pmoves/docs/handoffs/SECRET_ROTATION_RUNBOOK.md).",
                rel,
            )
        )

    if findings:
        errors = [f for f in findings if f.level == "ERROR"]
        warns = [f for f in findings if f.level == "WARN"]
        print(f"Secrets hardening audit: {'FAILED' if errors else 'WARN'} ({len(errors)} errors, {len(warns)} warnings)")
        for finding in findings:
            if finding.path:
                print(f"[{finding.level}] {finding.path}: {finding.message}")
            else:
                print(f"[{finding.level}] {finding.message}")
        return 1 if errors else 0

    print("Secrets hardening audit: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
