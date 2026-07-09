#!/usr/bin/env python3
"""
Secrets Funnel Populate -- Provider Key Injection Pipeline

Reads provider API keys from local.env, validates formats against
provider_catalog.yaml patterns, and injects into CHIT-encrypted storage.

NEVER logs actual key values. All output uses redaction patterns.

Usage:
    # Dry run (validate + show what would be injected, no changes)
    python secrets_funnel_populate.py --dry-run

    # Validate keys and inject into CHIT
    python secrets_funnel_populate.py

    # Verify CHIT storage has all expected keys
    python secrets_funnel_populate.py --verify

    # Show only validation report (no injection)
    python secrets_funnel_populate.py --validate-only

Pipeline:
    local.env -> validation -> CHIT encryption -> env.cgp.json
    ^                                        |
    |                                        v
    +------- make secrets-funnel <------------+

Security:
    - Key values are NEVER printed to stdout/stderr
    - Redaction pattern: sk-xx...xx (first 5 + last 4 chars shown)
    - Validation failures are logged with key name only
    - CHIT_PASSPHRASE is read from environment (not args)
    - Key values are NEVER passed as CLI arguments (always via secure channel)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# stdlib imports (PEP 8 ordering: stdlib, third-party, local)
# ---------------------------------------------------------------------------
import argparse
import getpass
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------
__all__ = [
    "KeyEntry",
    "KeyStatus",
    "ProviderCatalog",
    "discover_keys_from_env",
    "validate_all",
    "inject_into_chit",
    "main",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PMOVES_ROOT = Path(__file__).resolve().parents[1]

# All env files to search for keys (in priority order)
KEY_SOURCE_FILES = [
    "local.env",
    "pmoves/.env.local",
    "pmoves/env.shared",
    "pmoves/env.tier-llm",
    "pmoves/env.tier-agent",
    "pmoves/env.tier-supabase",
    ".env",
]

# Sentinel values that indicate "not set"
SENTINEL_VALUES = frozenset({
    "unset-pending-key",
    "local-disabled",
    "placeholder",
    "",
    "null",
    "none",
    "todo",
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
    # MCP Server Token
    "MCP_SERVER_TOKEN": re.compile(r"^.{20,}$"),
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class KeyStatus(str, Enum):
    ACTIVE = "active"
    MISSING = "missing"
    EMPTY = "empty"
    INVALID = "invalid"
    DEPRECATED_ALIAS = "deprecated_alias"
    EXPIRED = "expired"
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
        import re as _re

        msg = _re.sub(self._SENSITIVE_RE, r"\1=***REDACTED***", str(msg))
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
    """Configure module logging with redacting handler."""
    handler = logging.StreamHandler(sys.stdout)
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
        "MCP_SERVER_TOKEN": (
            "MCP Server (A2A)",
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
# Env file discovery
# ---------------------------------------------------------------------------

def discover_keys_from_env(
    root_dir: Path,
    source_files: Optional[list[str]] = None,
) -> dict[str, KeyEntry]:
    """Scan all configured env files for provider keys.

    Returns a dict of key_name -> KeyEntry. Values are redacted in logs.
    """
    files = source_files or KEY_SOURCE_FILES
    entries: dict[str, KeyEntry] = {}

    for rel_path in files:
        env_file = root_dir / rel_path
        if not env_file.exists():
            log.debug("Env file not found: %s", env_file)
            continue

        log.info("Scanning %s for keys ...", rel_path)
        parsed = _parse_env_file(env_file)

        for key_name, value in parsed.items():
            # Skip non-provider keys
            if not _is_provider_key(key_name):
                continue

            # Skip if we already have this key from a higher-priority file
            if key_name in entries and entries[key_name].is_set():
                continue

            entry = KeyEntry(
                name=key_name,
                value=value,
                source_file=rel_path,
                validator=KEY_VALIDATORS.get(key_name),
            )
            entries[key_name] = entry

    return entries


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env-style file, returning key-value pairs.

    Handles:
    - Standard KEY=value
    - KEY="quoted value"
    - KEY='single quoted'
    - Comments (# or ;)
    - Empty lines
    - Multi-line values (basic)
    """
    result: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and comments
        if not line or line.startswith("#") or line.startswith(";"):
            i += 1
            continue

        # Handle multi-line values (basic: lines ending with \)
        full_line = line
        while full_line.endswith("\\") and i + 1 < len(lines):
            i += 1
            full_line = full_line[:-1] + lines[i].strip()

        # Parse KEY=value
        if "=" in full_line:
            key, _, value = full_line.partition("=")
            key = key.strip()
            value = value.strip()

            # Remove surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            result[key] = value

        i += 1

    return result


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
    - Provider-specific rules
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


def validate_all(entries: dict[str, KeyEntry]) -> dict[str, KeyEntry]:
    """Validate all discovered keys, plus check for missing expected keys."""
    validated: dict[str, KeyEntry] = {}

    # Validate discovered keys
    for name, entry in entries.items():
        validated[name] = validate_key(entry)

    # Check for expected keys that weren't discovered
    for expected in ProviderCatalog.all_expected_keys():
        if expected not in validated:
            validated[expected] = KeyEntry(
                name=expected,
                status=KeyStatus.MISSING,
                error_message=f"{expected} not found in any env file",
            )

    return validated


# ---------------------------------------------------------------------------
# CHIT injection
# ---------------------------------------------------------------------------

def inject_into_chit(
    entries: dict[str, KeyEntry],
    dry_run: bool = False,
) -> dict[str, bool]:
    """Inject validated keys into CHIT-encrypted storage.

    Returns a dict of key_name -> success (bool).
    """
    results: dict[str, bool] = {}
    passphrase = _get_chit_passphrase()

    if not passphrase:
        log.error(
            "CHIT_PASSPHRASE not set. Cannot inject keys. "
            "Set it as an environment variable or use voice activation."
        )
        return {name: False for name in entries}

    for name, entry in entries.items():
        if entry.status != KeyStatus.ACTIVE:
            log.debug("Skipping %s (status: %s)", name, entry.status.value)
            results[name] = False
            continue

        if dry_run:
            log.info("[DRY-RUN] Would inject %s into CHIT", name)
            results[name] = True
            continue

        success = _inject_single_key(name, entry.value, passphrase)
        results[name] = success

    return results


def _get_chit_passphrase() -> Optional[str]:
    """Get CHIT passphrase from environment or interactive prompt."""
    passphrase = os.environ.get("CHIT_PASSPHRASE")
    if passphrase:
        return passphrase

    # Try voice-activated passphrase file (if exists)
    voice_file = Path.home() / ".pmoves" / "chit_passphrase"
    if voice_file.exists():
        return voice_file.read_text().strip()

    # Interactive fallback
    if sys.stdin.isatty():
        try:
            return getpass.getpass("CHIT passphrase: ")
        except (EOFError, KeyboardInterrupt):
            return None

    return None


def _inject_single_key(name: str, value: str, passphrase: str) -> bool:
    """Inject a single key into CHIT-encrypted storage."""
    fd: Optional[int] = None
    tmp_path: Optional[str] = None

    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".env", prefix="chit_key_")
        os.chmod(tmp_path, 0o600)

        with os.fdopen(fd, "w") as f:
            f.write(f"{name}={value}\n")
        fd = None

        chit_cli = PMOVES_ROOT / "tools" / "chit_cli.py"
        if not chit_cli.exists():
            log.error(
                "CHIT CLI not found at %s. Cannot inject %s. "
                "Install CHIT tooling or set CHIT_PASSPHRASE for direct encryption.",
                chit_cli, name,
            )
            return False

        result = subprocess.run(
            [
                sys.executable,
                str(chit_cli),
                "--action", "set",
                "--key", name,
                "--from-file", tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            log.info("Injected %s into CHIT storage", name)
            return True
        else:
            log.error("CHIT CLI failed for %s: %s", name, result.stderr[:200])
            return False

    except subprocess.TimeoutExpired:
        log.error("CHIT CLI timeout for %s", name)
        return False
    except Exception:
        log.exception("Failed to inject %s", name)
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                size = os.path.getsize(tmp_path)
                with open(tmp_path, "wb") as f:
                    f.write(b"\x00" * size)
                os.unlink(tmp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(entries: dict[str, KeyEntry]) -> None:
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
# Verification
# ---------------------------------------------------------------------------

def verify_chit_storage(expected_keys: list[str]) -> dict[str, bool]:
    """Verify that CHIT storage contains all expected keys.

    Returns key_name -> present (bool).
    """
    env_cgp_path = PMOVES_ROOT / "env.cgp.json"
    results: dict[str, bool] = {}

    data: dict[str, Any] = {}
    if env_cgp_path.exists():
        try:
            data = json.loads(env_cgp_path.read_text())
        except json.JSONDecodeError:
            log.error("env.cgp.json is corrupted")

    for key in expected_keys:
        results[key] = key in data

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PMOVES Secrets Funnel -- Provider Key Injection Pipeline",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="PMOVES repository root directory (default: cwd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate keys but do not inject into CHIT",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify CHIT storage has all expected keys",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Show validation report without injection or verification",
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

    _setup_logging(args.verbose)  # Don't assign to unused variable

    # --verify mode
    if args.verify:
        expected = ProviderCatalog.all_expected_keys()
        results = verify_chit_storage(expected)
        ok = sum(1 for v in results.values() if v)
        print(f"CHIT verification: {ok}/{len(expected)} keys present")
        for key, present in sorted(results.items()):
            status = "OK" if present else "MISSING"
            print(f"  [{status}] {key}")
        return 0 if all(results.values()) else 1

    # Discover keys from env files
    log.info("Discovering keys from env files ...")
    entries = discover_keys_from_env(args.root_dir)
    log.info("Discovered %d potential keys", len(entries))

    # Validate
    validated = validate_all(entries)

    # --validate-only mode
    if args.validate_only:
        print_report(validated)
        return 0

    # Print report
    print_report(validated)

    # Check if we have critical issues
    critical_issues = [
        e for e in validated.values()
        if e.status in (KeyStatus.MISSING, KeyStatus.INVALID)
    ]
    if critical_issues:
        log.warning(
            "Found %d critical issues. Fix before injecting.",
            len(critical_issues),
        )
        # Continue anyway -- non-critical keys can still be injected

    # Inject into CHIT
    active_entries = {
        k: v for k, v in validated.items()
        if v.status == KeyStatus.ACTIVE
    }

    if not active_entries:
        log.error("No active keys to inject. Populate local.env first.")
        return 1

    log.info("Injecting %d active keys into CHIT ...", len(active_entries))
    results = inject_into_chit(active_entries, dry_run=args.dry_run)

    ok = sum(1 for v in results.values() if v)
    log.info(
        "Injection complete: %d/%d succeeded",
        ok, len(results),
    )

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
            "injection": results,
            "summary": {
                "total": len(validated),
                "active": len(active_entries),
                "injected": ok,
                "failed": len(results) - ok,
            },
        }
        print(_json.dumps(output, indent=2))

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
