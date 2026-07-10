#!/usr/bin/env python3
"""
Provider Key Inventory -- read-only validation and CGP vault verification

Scans the configured env files for provider API keys, validates their formats,
and reports status. Separately, verifies that the CGP vault exported by the
canonical secrets funnel holds a non-empty value for every expected key.

This tool is READ-ONLY. It does not write env files and it does not inject
secrets. Injection is owned by the canonical funnel:

    make -C pmoves secrets-funnel

which is defined in pmoves/mk/codex.mk and included by pmoves/Makefile. That
funnel runs secrets-local-hydrate -> secrets-runtime-hydrate ->
credential_urlencoder -> secrets-funnel-sync -> secrets-audit -> tooling-audit,
and it is the only supported path to CHIT storage.

NEVER logs actual key values. All output uses redaction patterns.

Usage:
    # Validation report (default)
    python provider_key_inventory.py

    # Machine-readable report; no key values exposed
    python provider_key_inventory.py --json-output

    # Verify the CGP vault holds every expected key
    python provider_key_inventory.py --verify

Exit codes:
    0  all discovered keys valid / vault complete
    1  one or more keys MISSING or INVALID / vault incomplete

Security:
    - Key values are NEVER printed to stdout/stderr
    - Redaction pattern: sk-xx...xx (first 5 + last 4 chars shown)
    - Validation failures are logged with key name only
    - Key values are NEVER passed as CLI arguments
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# stdlib imports (PEP 8 ordering: stdlib, third-party, local)
# ---------------------------------------------------------------------------
import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
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
    "verify_chit_storage",
    "resolve_cgp_path",
    "chit_injection_guidance",
    "main",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PMOVES_ROOT = Path(__file__).resolve().parents[1]

# All env files to search for keys (in priority order).
# pmoves/secrets/local.env is the path secrets-local-hydrate reads and the one
# KEY_RECEIPT_FORM.md tells operators to create; it must be scanned first or the
# documented inspect-then-inject sequence reports freshly supplied keys missing.
KEY_SOURCE_FILES = [
    "pmoves/secrets/local.env",
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
    # stderr, not stdout: --json-output must stay machine-parseable.
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("[%(name)s] %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger("provider_key_inventory")
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)


log = _RedactingLoggerAdapter(logging.getLogger("provider_key_inventory"), {})


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
# CHIT injection -- intentionally NOT implemented here
# ---------------------------------------------------------------------------

CANONICAL_FUNNEL_CMD = "make -C pmoves secrets-funnel"


def chit_injection_guidance() -> str:
    """Return the canonical way to inject provider keys into CHIT storage.

    This module is read-only by design. Injection belongs to the canonical
    secrets funnel defined in pmoves/mk/codex.mk (included by pmoves/Makefile),
    which runs: secrets-local-hydrate -> secrets-runtime-hydrate ->
    credential_urlencoder -> secrets-funnel-sync -> secrets-audit -> tooling-audit.

    An earlier revision of this file shelled out to pmoves/tools/chit_cli.py,
    which has never existed in this repository. That path always failed.
    """
    return (
        "\nThis tool is read-only; it does not write secrets.\n"
        "To apply provider keys, run the canonical funnel:\n"
        f"\n    {CANONICAL_FUNNEL_CMD}\n"
    )


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

def resolve_cgp_path() -> Path:
    """Resolve the CGP vault the canonical funnel exports to.

    Mirrors CHIT_EXPORT_PATH in pmoves/mk/codex.mk: %APPDATA% on Windows,
    $XDG_CONFIG_HOME (else ~/.config) elsewhere. Falls back to the repo-local
    copy under pmoves/data/chit/ when the exported vault is absent.
    """
    override = os.environ.get("CHIT_EXPORT_PATH")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")

    exported = Path(base) / "pmoves" / "chit" / "env.cgp.json"
    if exported.exists():
        return exported
    return PMOVES_ROOT / "data" / "chit" / "env.cgp.json"


def verify_chit_storage(expected_keys: list[str]) -> dict[str, bool]:
    """Verify the CGP vault holds a non-empty value for each expected key.

    The CGP schema is {"points": [{"label": ..., "value": ...}]}. Keys are
    never top-level members of the document, so a membership test against the
    parsed dict always reports every key missing.
    """
    cgp_path = resolve_cgp_path()
    present: dict[str, str] = {}

    if not cgp_path.exists():
        log.error("CGP vault not found: %s", cgp_path)
    else:
        data: Any = None
        try:
            data = json.loads(cgp_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.error("CGP vault is corrupted: %s", cgp_path)

        # A corrupted vault may still be valid JSON of the wrong shape
        # (a list, a scalar, or {"points": null}). Degrade, never raise.
        if not isinstance(data, dict):
            if data is not None:
                log.error("CGP vault is not a JSON object: %s", cgp_path)
            data = {}

        points = data.get("points")
        if not isinstance(points, list):
            if points is not None:
                log.error("CGP vault 'points' is not a list: %s", cgp_path)
            points = []

        for point in points:
            if not isinstance(point, dict):
                continue
            label = point.get("label")
            if label:
                value = point.get("value")
                present[label] = value if isinstance(value, str) else ""

    return {key: bool(present.get(key, "").strip()) for key in expected_keys}



# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "PMOVES Provider Key Inventory -- read-only validation and vault verification. "
            "This tool never writes secrets."
        ),
        epilog=f"Injection is owned by the canonical funnel: {CANONICAL_FUNNEL_CMD}",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="PMOVES repository root directory (default: cwd)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the CGP vault holds a non-empty value for every expected key",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Deprecated alias for the default behaviour (kept for compatibility)",
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

    if args.verify:
        expected = ProviderCatalog.all_expected_keys()
        results = verify_chit_storage(expected)
        ok = sum(1 for v in results.values() if v)
        print(f"CGP vault verification: {ok}/{len(expected)} keys present ({resolve_cgp_path()})")
        for key, present in sorted(results.items()):
            print(f"  [{'OK' if present else 'MISSING'}] {key}")
        return 0 if all(results.values()) else 1

    log.info("Discovering keys from env files ...")
    entries = discover_keys_from_env(args.root_dir)
    log.info("Discovered %d potential keys", len(entries))

    validated = validate_all(entries)

    unhealthy = [
        e for e in validated.values()
        if e.status in (KeyStatus.MISSING, KeyStatus.INVALID)
    ]

    if args.json_output:
        output = {
            "cgp_vault": str(resolve_cgp_path()),
            "validation": {
                k: {
                    "status": v.status.value,
                    "provider": ProviderCatalog.get_provider_info(k)[0],
                    "error": v.error_message,
                    "redacted": v.redacted_value(),
                }
                for k, v in sorted(validated.items())
            },
            "summary": {
                "total": len(validated),
                "active": sum(1 for v in validated.values() if v.status == KeyStatus.ACTIVE),
                "unhealthy": len(unhealthy),
            },
            "inject_with": CANONICAL_FUNNEL_CMD,
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(validated)
        print(chit_injection_guidance())

    return 1 if unhealthy else 0


if __name__ == "__main__":
    sys.exit(main())
