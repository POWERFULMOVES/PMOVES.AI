#!/usr/bin/env python3
"""
Secrets Funnel Populate -- Provider Key Validation + Delivery

Validates provider API keys and delivers them into the SANCTIONED secrets
pipeline. This tool never writes CGP bundles or tier env files itself --
delivery rides the existing funnel:

    <filled receipt template> --import-file--> local.env
    local.env --`make -C pmoves secrets-funnel`--> env.shared
             --chit-export--> CHIT bundle --secrets-funnel-sync--> tier envs

Ground truth (do not re-invent):
  - local.env is the canonical operator entry point. Resolution order is
    pmoves/secrets/local.env (project-local, written by the
    sync-secrets-local.yml runner), else <host-config>/pmoves/secrets/local.env
    -- the same file `make -C pmoves secrets-funnel` hydrates env.shared from
    (tools/secrets_local_hydrate.py).
  - The CHIT bundle written by `make chit-export` lives at the USER-SCOPED
    path <host-config>/pmoves/chit/env.cgp.json (mk/codex.mk CHIT_EXPORT_PATH),
    not inside the repository.
  - CGP is base16 ENCODING, not encryption (see pmoves/chit/__init__.py).
    Nothing in this tool claims cryptographic protection; real encryption
    lives in pmoves/tools/chit_security.py.

Usage:
    # Validate keys currently visible to the funnel (report only)
    python pmoves/tools/secrets_funnel_populate.py --validate-only

    # Merge a filled KEY_RECEIPT_FORM template into local.env
    # (values are never printed; the source file should be shredded after)
    python pmoves/tools/secrets_funnel_populate.py --import-file /path/to/filled.env

    # Show what an import would change without writing
    python pmoves/tools/secrets_funnel_populate.py --import-file /path/to/filled.env --dry-run

    # Verify the exported CHIT bundle carries the expected provider keys
    python pmoves/tools/secrets_funnel_populate.py --verify

Security:
    - Key values are NEVER printed to stdout/stderr
    - Redaction pattern: sk-xx...xx (first 5 + last 4 chars shown)
    - Validation failures are logged with key name only
    - Key values are NEVER passed as CLI arguments (file-based import only)
    - local.env is written with 0600 permissions
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import stat
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import (  # noqa: E402
    host_config_dir,
    local_env_path,
    parse_env_file,
)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------
__all__ = [
    "KeyEntry",
    "KeyStatus",
    "ProviderCatalog",
    "discover_keys",
    "validate_all",
    "merge_into_local_env",
    "verify_bundle",
    "main",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sentinel values that indicate "not set"
SENTINEL_VALUES = frozenset({
    "unset-pending-key",
    "local-disabled",
    "placeholder",
    "",
    "null",
    "none",
    "todo",
    "changeme",
})

# Deprecated aliases -> (canonical_name, sunset_date)
DEPRECATED_ALIASES = {
    "KIMI_API_KEY": ("MOONSHOT_API_KEY", "2026-10-01"),
    "ZAI_API_KEY": ("Z_AI_API_KEY", "2026-10-01"),
    "ALIBABA_API_KEY": ("ALIBABA_PRO_CODING_PLAN", "2026-10-01"),
    "HUGGINGFACE_TOKEN": ("HF_TOKEN", "2026-10-01"),
}

# Provider key validation patterns
KEY_VALIDATORS = {
    # Zhipu / Z.AI
    "Z_AI_API_KEY": re.compile(r"^.{20,}$"),
    "ZAI_API_KEY": re.compile(r"^.{20,}$"),
    # Moonshot / KIMI
    "MOONSHOT_API_KEY": re.compile(r"^sk-[a-zA-Z0-9]{32,}$"),
    "KIMI_API_KEY": re.compile(r"^sk-[a-zA-Z0-9]{32,}$"),
    # Alibaba / Qwen
    "ALIBABA_PRO_CODING_PLAN": re.compile(r"^sk-[a-zA-Z0-9]{32,}$"),
    # KiloCode
    "KILOCODE_API_KEY": re.compile(r"^.{20,}$"),
    # Ollama
    "OLLAMA_API_KEY": re.compile(r"^.{10,}$"),
    # HuggingFace
    "HF_TOKEN": re.compile(r"^hf_[A-Za-z0-9]{30,40}$"),
    "HUGGINGFACE_TOKEN": re.compile(r"^hf_[A-Za-z0-9]{30,40}$"),
    # MiniMax
    "MINIMAX_API_KEY": re.compile(r"^.{20,}$"),
    "MINIMAX_TOKEN_PLAN_API_KEY": re.compile(r"^.{20,}$"),
    # OpenRouter
    "OPENROUTER_API_KEY": re.compile(r"^sk-or-[a-zA-Z0-9]{32,}$"),
    # Groq
    "GROQ_API_KEY": re.compile(r"^gsk_[A-Za-z0-9]{28,36}$"),
    # NVIDIA
    "NVIDIA_API_KEY": re.compile(r"^nvapi-[a-zA-Z0-9]{32,}$"),
    # Agent Zero MCP Token (fleet-canonical)
    "AGENT_ZERO_MCP_TOKEN": re.compile(r"^.{20,}$"),
    # MCP Server Token (legacy, use AGENT_ZERO_MCP_TOKEN)
    "MCP_SERVER_TOKEN": re.compile(r"^.{20,}$"),
}


def default_bundle_path() -> Path:
    """User-scoped CHIT bundle path, mirroring mk/codex.mk CHIT_EXPORT_PATH."""
    return host_config_dir() / "chit" / "env.cgp.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class KeyStatus(str, Enum):
    ACTIVE = "active"
    MISSING = "missing"
    EMPTY = "empty"
    INVALID = "invalid"
    DEPRECATED_ALIAS = "deprecated_alias"
    UNKNOWN = "unknown"


@dataclass
class KeyEntry:
    """A single provider key entry with full metadata."""

    name: str
    value: str = ""
    canonical_name: Optional[str] = None
    provider: str = "unknown"
    status: KeyStatus = KeyStatus.UNKNOWN
    error_message: Optional[str] = None
    sunset_date: Optional[str] = None
    source_file: Optional[str] = None
    validator: Optional[re.Pattern] = None

    def redacted_value(self) -> str:
        """Return a redacted version of the key value for logging."""
        if not self.value:
            return "<empty>"
        if len(self.value) <= 10:
            return "***"
        return f"{self.value[:5]}...{self.value[-4:]}"

    def is_set(self) -> bool:
        """True if the key has a non-sentinel value."""
        if not self.value:
            return False
        return self.value.strip().lower() not in SENTINEL_VALUES


# ---------------------------------------------------------------------------
# Logging (redacting -- never emits key values)
# ---------------------------------------------------------------------------

class _RedactingLoggerAdapter(logging.LoggerAdapter):
    """Redacts secrets from log messages at format time.

    Uses LoggerAdapter instead of Filter to avoid mutating LogRecord
    objects in-place (which would poison all handlers globally).
    """

    _SENSITIVE_RE = (
        r"((?:api[_-]?key|apikey|secret|token|password|auth)[^=]*)=\S+"
    )

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        msg = re.sub(self._SENSITIVE_RE, r"\1=***REDACTED***", str(msg))
        if "extra" in kwargs and isinstance(kwargs["extra"], dict):
            kwargs["extra"] = self._redact_dict(kwargs["extra"])
        return msg, kwargs

    def _redact_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        for k, v in d.items():
            if isinstance(v, dict):
                redacted[k] = self._redact_dict(v)
            elif any(s in k.lower() for s in ("key", "secret", "token", "password")):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = v
        return redacted


def _setup_logging(verbose: bool = False) -> None:
    """Configure module logging with redacting handler.

    Logs go to stderr so stdout stays clean for --json-output consumers.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("[%(name)s] %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger("secrets_funnel")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)


log = _RedactingLoggerAdapter(logging.getLogger("secrets_funnel"), {})


# ---------------------------------------------------------------------------
# Provider catalog
# ---------------------------------------------------------------------------

class ProviderCatalog:
    """Manages the provider key catalog -- which keys exist, their status,
    and how they map to model suits and TensorZero functions."""

    # Key -> (provider_display, model_suits, tensorzero_functions)
    # Model suits are synced with pmoves/configs/model-suits/*.yaml on main branch.
    KEY_PROVIDERS: dict[str, tuple[str, list[str], list[str]]] = {
        "Z_AI_API_KEY": (
            "Zhipu AI (Z.AI)",
            ["glm-4-air", "glm-4-flash", "glm-4-plus", "glm-4.7", "glm-5-turbo", "glm-5.1"],
            ["pmoves_orchestrator_coding", "pmoves_worker_glm"],
        ),
        "MOONSHOT_API_KEY": (
            "Moonshot AI (KIMI)",
            ["kimi-k2"],
            ["pmoves_worker_kimi"],
        ),
        "ALIBABA_PRO_CODING_PLAN": (
            "Alibaba (Qwen)",
            [],  # No matching model-suit YAMLs on main branch
            ["pmoves_worker_qwen"],
        ),
        "KILOCODE_API_KEY": (
            "KiloCode",
            [],  # No model-suit YAML
            ["pmoves_worker_kilocode"],
        ),
        "OLLAMA_API_KEY": (
            "Ollama Cloud",
            [],  # No model-suit YAML
            ["pmoves_worker_ollama"],
        ),
        "HF_TOKEN": (
            "HuggingFace",
            [],  # No model-suit YAML
            ["pmoves_worker_hf"],
        ),
        "MINIMAX_API_KEY": (
            "MiniMax",
            [],  # No matching model-suit YAMLs on main branch
            ["pmoves_worker_minimax"],
        ),
        "OPENROUTER_API_KEY": (
            "OpenRouter",
            [],  # No model-suit YAML
            ["pmoves_worker_openrouter"],
        ),
        "GROQ_API_KEY": (
            "Groq",
            [],  # No model-suit YAML
            ["pmoves_worker_groq"],
        ),
        "NVIDIA_API_KEY": (
            "NVIDIA",
            ["nemotron-3-super"],  # Synced with nemotron-3-super.yaml
            ["pmoves_worker_nemotron"],
        ),
        "AGENT_ZERO_MCP_TOKEN": (
            "Agent Zero MCP (fleet-canonical)",
            [],  # No model-suit YAML
            ["pmoves_mcp_agent_zero"],
        ),
        "MCP_SERVER_TOKEN": (
            "MCP Server (A2A, legacy)",
            [],  # No model-suit YAML
            ["pmoves_mcp_server"],
        ),
    }

    @classmethod
    def get_provider_info(cls, key_name: str) -> tuple[str, list[str], list[str]]:
        return cls.KEY_PROVIDERS.get(
            key_name, ("unknown", [], [])
        )

    @classmethod
    def all_expected_keys(cls) -> list[str]:
        return list(cls.KEY_PROVIDERS.keys())


# ---------------------------------------------------------------------------
# Key discovery
# ---------------------------------------------------------------------------

def discover_keys(source: Path) -> Dict[str, KeyEntry]:
    """Read provider keys from a single dotenv-style source file.

    The source is either the canonical local.env or an operator-filled
    receipt template. Generated pipeline OUTPUTS (env.shared, env.tier-*)
    are deliberately NOT read here -- feeding outputs back in as inputs
    is circular and masks a stale local.env.
    """
    entries: Dict[str, KeyEntry] = {}
    if not source.exists():
        log.debug("Source file not found: %s", source)
        return entries

    log.info("Scanning %s for provider keys ...", source)
    for key_name, value in parse_env_file(source).items():
        if not _is_provider_key(key_name):
            continue
        entries[key_name] = KeyEntry(
            name=key_name,
            value=value,
            source_file=str(source),
            validator=KEY_VALIDATORS.get(key_name),
        )
    return entries


def _is_provider_key(name: str) -> bool:
    """Check if a key name is a known provider API key."""
    return name in KEY_VALIDATORS or name in DEPRECATED_ALIASES


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_key(entry: KeyEntry) -> KeyEntry:
    """Validate a single key entry, returning an updated entry with status.

    Handles:
    - Empty/sentinel detection
    - Deprecated alias migration
    - Regex format validation
    """
    name = entry.name
    value = entry.value

    # Check deprecated aliases
    if name in DEPRECATED_ALIASES:
        canonical, sunset = DEPRECATED_ALIASES[name]
        entry.canonical_name = canonical
        entry.sunset_date = sunset

        if value and value.strip():
            # Auto-migrate: the alias has a value, migrate to canonical
            log.info(
                "Migrating deprecated alias '%s' -> '%s' (sunset: %s)",
                name, canonical, sunset,
            )
            entry.name = canonical  # Switch to canonical name
            entry.validator = KEY_VALIDATORS.get(canonical)
            name = canonical
            # Continue validation with canonical name
        else:
            entry.status = KeyStatus.EMPTY
            entry.error_message = (
                f"'{name}' is deprecated, use '{canonical}' (sunset: {sunset})"
            )
            return entry

    # Check empty/sentinel
    if not value or not value.strip():
        entry.status = KeyStatus.MISSING
        entry.error_message = f"{name} is not set"
        return entry

    if value.strip().lower() in SENTINEL_VALUES:
        entry.status = KeyStatus.EMPTY
        entry.error_message = f"{name} has sentinel value: {value.strip()[:20]}"
        return entry

    # Regex validation
    validator = entry.validator or KEY_VALIDATORS.get(name)
    if validator and not validator.match(value):
        entry.status = KeyStatus.INVALID
        entry.error_message = (
            f"{name} format does not match expected pattern "
            f"(got {len(value)} chars, redacted: {entry.redacted_value()})"
        )
        return entry

    # Valid
    entry.status = KeyStatus.ACTIVE
    entry.error_message = None
    return entry


def validate_all(entries: Dict[str, KeyEntry]) -> Dict[str, KeyEntry]:
    """Validate all discovered keys, plus check for missing expected keys."""
    validated: Dict[str, KeyEntry] = {}

    # Validate canonical names first so a migrated alias can never clobber a
    # canonical key that is itself ACTIVE — when both are set, the canonical
    # value wins and the alias is ignored (it may hold a stale rotation).
    ordered = sorted(
        entries.items(), key=lambda kv: kv[0] in DEPRECATED_ALIASES
    )
    for original_name, entry in ordered:
        result = validate_key(entry)
        existing = validated.get(result.name)
        if existing is not None and existing.status == KeyStatus.ACTIVE:
            log.warning(
                "Ignoring '%s' — canonical '%s' is already set from %s",
                original_name, result.name, existing.source_file or "source",
            )
            continue
        validated[result.name] = result

    # Check for expected keys that weren't discovered
    for expected in ProviderCatalog.all_expected_keys():
        if expected not in validated:
            validated[expected] = KeyEntry(
                name=expected,
                status=KeyStatus.MISSING,
                error_message=f"{expected} not found in source file",
            )

    return validated


# ---------------------------------------------------------------------------
# Delivery: merge into local.env (the funnel's sanctioned entry point)
# ---------------------------------------------------------------------------

def merge_into_local_env(
    entries: Dict[str, KeyEntry],
    local_env: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, bool]:
    """Merge ACTIVE keys into local.env, preserving all other lines.

    local.env is what `make -C pmoves secrets-funnel` hydrates env.shared
    from (tools/secrets_local_hydrate.py). We only ever add or update the
    provider keys handled by this tool; unknown lines pass through verbatim.

    Returns key_name -> written (bool). Skipped (non-ACTIVE) keys are False.
    """
    target = local_env or local_env_path()
    results: Dict[str, bool] = {}

    active = {k: e for k, e in entries.items() if e.status == KeyStatus.ACTIVE}
    for name in entries:
        results[name] = name in active
    if not active:
        log.warning("No ACTIVE keys to merge into %s", target)
        return results

    if dry_run:
        for name in sorted(active):
            log.info("[DRY-RUN] Would merge %s into %s", name, target)
        return results

    existing_lines: list[str] = []
    if target.exists():
        existing_lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    remaining = dict(active)
    out_lines: list[str] = []
    for raw in existing_lines:
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key = line.partition("=")[0].strip()
            if key in remaining:
                out_lines.append(f"{key}={remaining.pop(key).value}")
                continue
            # A deprecated alias line is superseded by its canonical entry
            if key in DEPRECATED_ALIASES and DEPRECATED_ALIASES[key][0] in active:
                log.info("Dropping superseded alias line '%s' from local.env", key)
                continue
        out_lines.append(raw)

    for name in sorted(remaining):
        out_lines.append(f"{name}={remaining[name].value}")

    target.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)  # 0600

    for name in sorted(active):
        log.info("Merged %s into %s", name, target)
    log.info(
        "Next step: run `make -C pmoves secrets-funnel` to hydrate env.shared, "
        "export the CHIT bundle, and regenerate tier env files."
    )
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(entries: Dict[str, KeyEntry]) -> None:
    """Print a formatted validation report (no key values exposed)."""
    print("\n" + "=" * 70)
    print("  PMOVES Provider Key Validation Report")
    print("=" * 70)

    by_status: dict[KeyStatus, list[KeyEntry]] = {s: [] for s in KeyStatus}
    for entry in entries.values():
        by_status[entry.status].append(entry)

    # Active keys
    active = by_status[KeyStatus.ACTIVE]
    if active:
        print(f"\n  ACTIVE KEYS ({len(active)}):")
        for e in sorted(active, key=lambda x: x.name):
            provider, suits, _ = ProviderCatalog.get_provider_info(e.name)
            print(f"    {e.name:<30} {provider:<20} [{len(suits)} model suits]")

    # Issues
    issues = [
        e for s, es in by_status.items()
        for e in es
        if s != KeyStatus.ACTIVE
    ]
    if issues:
        print(f"\n  ISSUES ({len(issues)}):")
        for e in sorted(issues, key=lambda x: x.name):
            marker = "WARN" if e.status in (KeyStatus.DEPRECATED_ALIAS, KeyStatus.EMPTY) else "ERR "
            print(f"    [{marker}] {e.name:<30} {e.status.value:<20} {e.error_message or ''}")

    # Summary
    total = len(entries)
    ok = len(active)
    print(f"\n  SUMMARY: {ok}/{total} keys active, {total - ok} issues")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Verification (reads the real, user-scoped CGP bundle)
# ---------------------------------------------------------------------------

def verify_bundle(
    expected_keys: list[str],
    bundle_path: Optional[Path] = None,
) -> Dict[str, bool]:
    """Verify the exported CHIT bundle carries the expected keys with
    non-sentinel values.

    The bundle is the user-scoped CGP written by `make chit-export`
    (mk/codex.mk CHIT_EXPORT_PATH) and must be decoded with the pmoves.chit
    codec -- it is a structured CGP payload, not flat KEY=value JSON.

    Returns key_name -> present-and-set (bool).
    """
    from pmoves.chit import decode_secret_map, load_cgp

    path = bundle_path or default_bundle_path()
    results: Dict[str, bool] = {key: False for key in expected_keys}

    if not path.exists():
        log.error(
            "No CHIT bundle at %s -- run `make -C pmoves chit-export` "
            "(or the full `make -C pmoves secrets-funnel`) first.", path,
        )
        return results

    try:
        secret_map = decode_secret_map(load_cgp(str(path)))
    except Exception:
        log.exception("Failed to decode CHIT bundle at %s", path)
        return results

    for key in expected_keys:
        value = (secret_map.get(key) or "").strip()
        results[key] = bool(value) and value.lower() not in SENTINEL_VALUES

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PMOVES Secrets Funnel -- Provider Key Validation + Delivery",
    )
    parser.add_argument(
        "--import-file",
        type=Path,
        default=None,
        help=(
            "Filled receipt template (dotenv format) to validate and merge "
            "into local.env. Shred the file after a successful merge."
        ),
    )
    parser.add_argument(
        "--local-env",
        type=Path,
        default=None,
        help="Override the local.env path (default: project-local, else host config dir)",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Override the CHIT bundle path for --verify (default: host config dir)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what --import-file would merge, without writing",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the exported CHIT bundle has the expected keys set",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Show validation report for the current local.env, no writes",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output report as JSON (no key values exposed)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    # --verify mode: read the real bundle
    if args.verify:
        expected = ProviderCatalog.all_expected_keys()
        results = verify_bundle(expected, bundle_path=args.bundle)
        ok = sum(1 for v in results.values() if v)
        print(f"CHIT bundle verification: {ok}/{len(expected)} keys set")
        for key, present in sorted(results.items()):
            status = "OK" if present else "MISSING"
            print(f"  [{status}] {key}")
        return 0 if all(results.values()) else 1

    # Discover + validate
    source = args.import_file or args.local_env or local_env_path()
    entries = discover_keys(source)
    log.info("Discovered %d potential keys in %s", len(entries), source)
    validated = validate_all(entries)
    print_report(validated)

    results: Dict[str, bool] = {}
    if args.import_file and not args.validate_only:
        results = merge_into_local_env(
            validated,
            local_env=args.local_env,
            dry_run=args.dry_run,
        )
        merged = sum(1 for v in results.values() if v)
        log.info("Merge complete: %d/%d keys delivered to local.env", merged, len(results))

    if args.json_output:
        import json as _json
        output = {
            "validation": {
                k: {
                    "status": v.status.value,
                    "provider": ProviderCatalog.get_provider_info(k)[0],
                    "error": v.error_message,
                    "redacted": v.redacted_value(),
                }
                for k, v in sorted(validated.items())
            },
            "merge": results,
            "summary": {
                "total": len(validated),
                "active": sum(1 for v in validated.values() if v.status == KeyStatus.ACTIVE),
                "merged": sum(1 for v in results.values() if v),
            },
        }
        print(_json.dumps(output, indent=2))

    if args.validate_only or not args.import_file:
        return 0
    # Exit nonzero only if an ACTIVE key failed to merge
    failed_active = [
        k for k, v in validated.items()
        if v.status == KeyStatus.ACTIVE and not results.get(k, False)
    ]
    return 1 if failed_active else 0


if __name__ == "__main__":
    sys.exit(main())
