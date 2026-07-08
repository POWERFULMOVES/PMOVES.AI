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
    "AGNOTE4482_CRITICAL_KEYS",
    "CHIT_ENV_CGP",
    "CHIT_PASSPHRASE_ENV_VARS",
    "DEPRECATED_ALIASES",
    "KEY_SOURCE_FILES",
    "KEY_VALIDATORS",
    "KeyEntry",
    "KeyStatus",
    "RedactingLogger",
    "find_key_sources",
    "get_chit_passphrase",
    "inject_into_chit",
    "parse_env_file",
    "print_report",
    "redact_env_line",
    "validate_all_keys",
    "validate_key",
    "verify_chit_storage",
]


# ============================================================================
# CONFIGURATION
# ============================================================================

# Keys that are the priority fill from AGNOTE4482
AGNOTE4482_CRITICAL_KEYS = [
    "Z_AI_API_KEY",
    "MOONSHOT_API_KEY",
    "ALIBABA_PRO_CODING_PLAN",
    "KILOCODE_API_KEY",
    "OLLAMA_API_KEY",
    "HF_TOKEN",
    "MINIMAX_API_KEY",
    "OPENROUTER_API_KEY",
]

# Key format validators (key_name -> regex pattern)
# These are validation patterns from provider_catalog.yaml
KEY_VALIDATORS: dict[str, str] = {
    "Z_AI_API_KEY": r"^.{8,}$",  # Z.AI: any string, min 8 chars
    "MOONSHOT_API_KEY": r"^sk-[a-zA-Z0-9]{20,}$",  # Moonshot: sk- prefix
    "ALIBABA_PRO_CODING_PLAN": r"^sk-[a-f0-9]{32}$",  # DashScope: sk- + 32 hex
    "KILOCODE_API_KEY": r"^.{8,}$",  # KiloCode: any string, min 8 chars
    "OLLAMA_API_KEY": r"^.{8,}$",  # Ollama Pro: any string, min 8 chars
    "HF_TOKEN": r"^hf_[A-Za-z0-9]{30,40}$",  # HF: hf_ + 30-40 alphanum
    "MINIMAX_API_KEY": r"^.{8,}$",  # MiniMax: any string, min 8 chars
    "MINIMAX_TOKEN_PLAN_API_KEY": r"^.{8,}$",  # MiniMax Token Plan: any string, min 8 chars
    "OPENROUTER_API_KEY": r"^sk-or-[a-zA-Z0-9-]{20,}$",  # OpenRouter: sk-or- prefix
    "OPENAI_API_KEY": r"^sk-(?:proj-)?[a-zA-Z0-9]{20,}$",  # OpenAI: sk- or sk-proj-
    "ANTHROPIC_API_KEY": r"^sk-ant-[a-zA-Z0-9-]{10,}$",  # Anthropic: sk-ant- prefix
    "GEMINI_API_KEY": r"^.{8,}$",  # Gemini: any string, min 8 chars
    "GROQ_API_KEY": r"^gsk_[A-Za-z0-9]{28,36}$",  # Groq: gsk_ + 28-36 alphanum
    "MISTRAL_API_KEY": r"^.{8,}$",  # Mistral: any string, min 8 chars
    "DEEPSEEK_API_KEY": r"^sk-[a-zA-Z0-9]{20,}$",  # DeepSeek: sk- prefix
    "XAI_API_KEY": r"^.{8,}$",  # xAI: any string, min 8 chars
    "ELEVENLABS_API_KEY": r"^.{8,}$",  # ElevenLabs: any string, min 8 chars
    "COHERE_API_KEY": r"^.{8,}$",  # Cohere: any string, min 8 chars
    "FIREWORKS_AI_API_KEY": r"^.{8,}$",  # Fireworks: any string, min 8 chars
    "PERPLEXITYAI_API_KEY": r"^pplx-[a-zA-Z0-9]{20,}$",  # Perplexity: pplx- prefix
    "TOGETHER_AI_API_KEY": r"^.{8,}$",  # Together: any string, min 8 chars
    "VENICE_API_KEY": r"^.{8,}$",  # Venice: any string, min 8 chars
    "CLOUDFLARE_API_TOKEN": r"^.{8,}$",  # Cloudflare: any string, min 8 chars
    "MCP_SERVER_TOKEN": r"^.{16,}$",  # MCP: min 16 chars for security
    "MCP_CLIENT_SECRET": r"^.{16,}$",  # MCP: min 16 chars for security
}

# Deprecated aliases and their canonical names + sunset dates
DEPRECATED_ALIASES: dict[str, tuple[str, str]] = {
    "KIMI_API_KEY": ("MOONSHOT_API_KEY", "2026-10-01"),
    "ALIBABA_API_KEY": ("ALIBABA_PRO_CODING_PLAN", "2026-10-01"),
    "DASHSCOPE_API_KEY": ("ALIBABA_PRO_CODING_PLAN", "2026-10-01"),
    "ZAI_API_KEY": ("Z_AI_API_KEY", "2026-10-01"),
    "HUGGINGFACE_TOKEN": ("HF_TOKEN", "2026-10-01"),
}

# Files to search for key sources
KEY_SOURCE_FILES = [
    "local.env",
    "pmoves/.env.local",
    "pmoves/env.shared",
    "pmoves/env.tier-llm",
    "pmoves/env.tier-agent",
    "pmoves/env.tier-supabase",
    ".env",
]

# CHIT target paths
CHIT_ENV_CGP = "pmoves/data/chit/env.cgp.json"
CHIT_PASSPHRASE_ENV_VARS = ["CHIT_PASSPHRASE", "CHIT_PROD_PASSPHRASE"]


# ============================================================================
# DATA CLASSES
# ============================================================================

class KeyStatus(Enum):
    MISSING = "missing"           # Key not found in any source
    EMPTY = "empty"               # Key found but value is empty
    PENDING_FILL = "pending-fill"  # Value is the sentinel "unset-pending-key"
    VALID = "valid"               # Key found, non-empty, format valid
    INVALID_FORMAT = "invalid-format"  # Key found but format check failed
    DEPRECATED_ALIAS = "deprecated-alias"  # Key uses deprecated alias name


@dataclass
class KeyEntry:
    """Represents a single key entry with its status and metadata."""
    name: str
    value: str = ""
    status: KeyStatus = KeyStatus.MISSING
    source_file: str = ""
    validation_pattern: str = ".*"
    canonical_name: str = ""       # Set if this is a deprecated alias
    sunset_date: str = ""          # Set if deprecated
    error_message: str = ""

    @property
    def is_populated(self) -> bool:
        """True if the key has a real value (not empty, not sentinel)."""
        if not self.value or self.value.strip() == "":
            return False
        if self.value.strip().lower() in ("unset-pending-key", "local-disabled", "placeholder"):
            return False
        return True

    @property
    def redacted_value(self) -> str:
        """Return redacted value for logging (never expose full key)."""
        if not self.is_populated:
            return "(empty)"
        v = self.value.strip()
        if len(v) <= 12:
            return "***"  # Too short to show anything
        return f"{v[:5]}...{v[-4:]}"


def redact_env_line(line: str) -> str:
    """Redact a KEY=VALUE line, keeping only the key name."""
    if "=" not in line:
        return line
    key, _, _ = line.partition("=")
    return f"{key}=***REDACTED***"


# ============================================================================
# LOGGING
# ============================================================================

class RedactingLogger:
    """Logger that automatically redacts key values from output."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._redaction_patterns: list[str] = []
        self._redaction_regex: re.Pattern[str] | None = None

    def _build_redaction_regex(self) -> re.Pattern[str] | None:
        """Build a regex with word boundaries for all registered secrets."""
        if not self._redaction_patterns:
            return None
        # Escape each pattern and join with word boundaries
        escaped = [re.escape(p) for p in self._redaction_patterns if len(p) > 4]
        if not escaped:
            return None
        # Use word boundaries to avoid false positive partial matches
        pattern = r"(?:^|\b|\W)(" + "|".join(escaped) + r")(?:\b|\W|$)"
        try:
            return re.compile(pattern)
        except re.error:
            # Fallback: if the combined pattern is too large, use simple replacement
            return None

    def _redact(self, message: str) -> str:
        """Redact any known key values from the message using regex word boundaries."""
        if self._redaction_regex is None:
            self._redaction_regex = self._build_redaction_regex()
        if self._redaction_regex:
            message = self._redaction_regex.sub("***REDACTED***", message)
        return message

    def register_value(self, value: str) -> None:
        """Register a secret value for redaction."""
        if value and len(value) > 4:
            self._redaction_patterns.append(value)
            # Invalidate cached regex so it's rebuilt on next _redact call
            self._redaction_regex = None

    def info(self, message: str) -> None:
        print(f"[INFO]  {self._redact(message)}", file=sys.stdout)

    def warn(self, message: str) -> None:
        print(f"[WARN]  {self._redact(message)}", file=sys.stderr)

    def error(self, message: str) -> None:
        print(f"[ERROR] {self._redact(message)}", file=sys.stderr)

    def debug(self, message: str) -> None:
        if self.verbose:
            print(f"[DEBUG] {self._redact(message)}", file=sys.stdout)

    def success(self, message: str) -> None:
        print(f"[OK]    {self._redact(message)}", file=sys.stdout)


# ============================================================================
# KEY DISCOVERY
# ============================================================================

def find_key_sources(logger: RedactingLogger) -> dict[str, str]:
    """Find local.env or equivalent key source files."""
    found: dict[str, str] = {}
    for filename in KEY_SOURCE_FILES:
        path = Path(filename)
        if path.exists():
            logger.info(f"Found key source: {path.resolve()}")
            found[str(path)] = filename
    return found


def _is_multiline_value(lines: list[str], start_idx: int) -> tuple[bool, int, str]:
    """Check if a value starts a multi-line quoted string.

    Returns (is_multiline, end_idx, full_line) where end_idx is the line
    index where the multi-line value ends (inclusive).
    """
    line = lines[start_idx]
    key, sep, value = line.partition("=")
    if sep != "=":
        return False, start_idx, line

    key = key.strip()
    value = value.strip()

    # Check for opening quote without closing quote on same line
    if (value.startswith('"') and not value.endswith('"')) or \
       (value.startswith("'") and not value.endswith("'")):
        quote_char = value[0]
        parts = [value[1:]]  # Strip opening quote
        idx = start_idx + 1
        while idx < len(lines):
            next_line = lines[idx].rstrip("\n\r")
            if next_line.endswith(quote_char):
                parts.append(next_line[:-1])  # Strip closing quote
                return True, idx, key + "=" + "\n".join(parts)
            parts.append(next_line)
            idx += 1
        # Unterminated quote -- return what we have
        return True, idx - 1, key + "=" + "\n".join(parts)

    return False, start_idx, line


def parse_env_file(filepath: str, logger: RedactingLogger) -> dict[str, str]:
    """Parse an env file and return key-value pairs. Supports multi-line values.

    Values are registered for redaction.
    """
    env_vars: dict[str, str] = {}
    path = Path(filepath)
    if not path.exists():
        return env_vars

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line or line.startswith("#"):
            idx += 1
            continue
        if "=" not in line:
            idx += 1
            continue

        # Check for multi-line values
        is_multi, end_idx, raw_line = _is_multiline_value(lines, idx)
        if is_multi:
            idx = end_idx + 1
        else:
            idx += 1
            raw_line = line

        key, _, value = raw_line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env_vars[key] = value
        if any(k in key for k in ["_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"]):
            logger.register_value(value)

    logger.info(f"Parsed {len(env_vars)} vars from {filepath}")
    return env_vars


# ============================================================================
# KEY VALIDATION
# ============================================================================

def validate_key(name: str, value: str, logger: RedactingLogger) -> KeyEntry:
    """Validate a single key and return a KeyEntry with status."""
    entry = KeyEntry(name=name, value=value)

    # Check if this is a deprecated alias
    if name in DEPRECATED_ALIASES:
        canonical, sunset = DEPRECATED_ALIASES[name]
        entry.canonical_name = canonical
        entry.sunset_date = sunset
        entry.error_message = f"'{name}' deprecated, use '{canonical}' (sunset: {sunset})"

        if value and value.strip():
            # Auto-migrate -- create canonical entry with same value
            logger.info(f"Migrating '{name}' -> '{canonical}' (sunset: {sunset})")
            entry.name = canonical
            entry.canonical_name = name  # Track the original alias name
            entry.sunset_date = sunset
            # The value is preserved; fall through to normal validation below
        else:
            # Empty deprecated alias -- mark as needing fill
            entry.status = KeyStatus.EMPTY
            logger.warn(
                f"Key '{name}' is deprecated alias for '{canonical}' (sunset: {sunset}) "
                f"but has no value. Use '{canonical}' instead."
            )
            return entry

    # Check for empty value
    if not value or value.strip() == "":
        entry.status = KeyStatus.EMPTY
        entry.error_message = "Key is empty or not set"
        return entry

    # Check for sentinel values (case-insensitive)
    sentinel_lower = value.strip().lower()
    if sentinel_lower in ("unset-pending-key", "local-disabled", "placeholder"):
        entry.status = KeyStatus.PENDING_FILL
        entry.error_message = f"Key has sentinel value '{value.strip()}'"
        return entry

    # Validate format
    pattern = KEY_VALIDATORS.get(entry.name, ".*")
    entry.validation_pattern = pattern
    if pattern and not re.match(pattern, value.strip()):
        entry.status = KeyStatus.INVALID_FORMAT
        entry.error_message = f"Value does not match expected pattern: {pattern}"
        logger.warn(
            f"Key '{entry.name}' format validation failed (pattern: {pattern}). "
            f"Value redacted: {entry.redacted_value}"
        )
        return entry

    # Key is valid
    entry.status = KeyStatus.VALID
    entry.error_message = ""
    return entry


def validate_all_keys(
    env_vars: dict[str, str],
    keys_to_check: list[str],
    logger: RedactingLogger,
) -> list[KeyEntry]:
    """Validate all keys and return a list of KeyEntry results."""
    results: list[KeyEntry] = []

    for key_name in keys_to_check:
        value = env_vars.get(key_name, "")
        entry = validate_key(key_name, value, logger)
        entry.source_file = "local.env" if key_name in env_vars else ""
        results.append(entry)

    return results


# ============================================================================
# CHIT INTEGRATION
# ============================================================================

def get_chit_passphrase(logger: RedactingLogger) -> Optional[str]:
    """Get CHIT passphrase from environment, with interactive fallback."""
    for var_name in CHIT_PASSPHRASE_ENV_VARS:
        passphrase = os.environ.get(var_name)
        if passphrase:
            logger.debug(f"Found CHIT passphrase in {var_name}")
            return passphrase

    # Fallback: prompt interactively
    try:
        passphrase = getpass.getpass("CHIT passphrase: ")
        if passphrase:
            return passphrase
    except (EOFError, KeyboardInterrupt):
        pass

    logger.error(
        "No CHIT passphrase found. Set CHIT_PASSPHRASE or CHIT_PROD_PASSPHRASE "
        "environment variable, or run interactively."
    )
    return None


def inject_into_chit(
    entries: list[KeyEntry],
    passphrase: str,
    dry_run: bool,
    logger: RedactingLogger,
) -> bool:
    """Inject validated keys into CHIT-encrypted storage."""

    # Filter to only valid, populated entries
    valid_entries = [e for e in entries if e.status == KeyStatus.VALID and e.is_populated]

    if not valid_entries:
        logger.warn("No valid, populated keys to inject into CHIT")
        return False

    logger.info(f"Preparing to inject {len(valid_entries)} keys into CHIT")

    for entry in valid_entries:
        logger.info(
            f"  CHIT target: {entry.name} = {entry.redacted_value}"
        )

    if dry_run:
        logger.info("[DRY RUN] Would inject keys into CHIT. No changes made.")
        return True

    # Check if CHIT tooling is available
    chit_cli = Path("pmoves/tools/chit_cli.py")
    if not chit_cli.exists():
        logger.error(
            "CHIT CLI not found at %s. Cannot proceed with key injection. "
            "Install CHIT tooling or ensure chit_cli.py is available.",
            chit_cli,
        )
        return False

    return _inject_via_chit_cli(valid_entries, passphrase, logger)


def _inject_via_chit_cli(
    entries: list[KeyEntry],
    passphrase: str,
    logger: RedactingLogger,
) -> bool:
    """Inject keys using the CHIT CLI tool.

    Key values are NEVER passed as CLI arguments.
    Values are written to a temporary file with 0o600 permissions
    and passed via --from-file or env var.
    """
    for entry in entries:
        temp_path = None
        try:
            # Write key=value to a temp file with 0o600 permissions
            fd, temp_path = tempfile.mkstemp(suffix=".env", prefix="chit_key_")
            try:
                os.write(fd, f"{entry.name}={entry.value}\n".encode("utf-8"))
            finally:
                os.close(fd)

            # Restrict permissions: owner read/write only
            os.chmod(temp_path, 0o600)

            env = os.environ.copy()
            env["CHIT_PASSPHRASE"] = passphrase

            # Pass the key value via --from-file instead of --value
            # to prevent exposure in process listings (ps aux)
            result = subprocess.run(
                [
                    sys.executable,
                    "pmoves/tools/chit_cli.py",
                    "--action", "set",
                    "--key", entry.name,
                    "--from-file", temp_path,
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )

            if result.returncode == 0:
                logger.success(f"CHIT set: {entry.name}")
            else:
                logger.error(f"CHIT set failed for {entry.name}: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error(f"CHIT CLI timeout for {entry.name}")
        except Exception as e:
            logger.error(f"CHIT CLI error for {entry.name}: {e}")
        finally:
            # Securely clean up the temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    # Overwrite with zeros before unlinking (defense in depth)
                    try:
                        file_size = os.path.getsize(temp_path)
                        with open(temp_path, "wb") as f:
                            f.write(b"\x00" * file_size)
                    except OSError:
                        pass
                    os.unlink(temp_path)
                except OSError:
                    pass

    return True


# ============================================================================
# VERIFICATION
# ============================================================================

def verify_chit_storage(
    expected_keys: list[str],
    logger: RedactingLogger,
) -> list[KeyEntry]:
    """Verify that CHIT storage contains all expected keys."""
    chit_path = Path(CHIT_ENV_CGP)
    results: list[KeyEntry] = []

    if not chit_path.exists():
        logger.error(f"CHIT storage not found at {chit_path}")
        for key in expected_keys:
            results.append(KeyEntry(name=key, status=KeyStatus.MISSING))
        return results

    try:
        with open(chit_path, "r", encoding="utf-8") as f:
            cgp_data = json.load(f)

        entry_ids = {
            e.get("id", "").upper(): e
            for e in cgp_data.get("entries", [])
            if isinstance(e, dict)
        }

        for key in expected_keys:
            entry_id = key.lower()
            if entry_id in entry_ids:
                cgp_entry = entry_ids[entry_id]
                results.append(
                    KeyEntry(
                        name=key,
                        status=KeyStatus.VALID,
                        source_file=str(chit_path),
                    )
                )
                logger.success(f"CHIT verify: {key} found in CGP")
            else:
                results.append(
                    KeyEntry(name=key, status=KeyStatus.MISSING)
                )
                logger.warn(f"CHIT verify: {key} NOT found in CGP")

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read CHIT storage: {e}")
        for key in expected_keys:
            results.append(KeyEntry(name=key, status=KeyStatus.MISSING))

    return results


# ============================================================================
# REPORTING
# ============================================================================

def print_report(
    entries: list[KeyEntry],
    logger: RedactingLogger,
    title: str = "Key Validation Report",
) -> None:
    """Print a formatted report of key validation results."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print(f"  Generated: {datetime.now(tz=timezone.utc).isoformat()}")
    print("=" * 70)

    # Group by status
    by_status: dict[KeyStatus, list[KeyEntry]] = {s: [] for s in KeyStatus}
    for e in entries:
        by_status[e.status].append(e)

    # Critical keys section
    print("\n  --- AGNOTE4482 Critical Keys ---")
    for key_name in AGNOTE4482_CRITICAL_KEYS:
        entry = next((e for e in entries if e.name == key_name), None)
        if entry:
            icon = "  " if entry.status == KeyStatus.VALID else "!!"
            print(
                f"  [{icon}] {entry.name:30s} {entry.status.value:20s} "
                f"{entry.redacted_value}"
            )
        else:
            print(f"  [??] {key_name:30s} missing-from-results")

    # Summary
    print("\n  --- Summary ---")
    total = len(entries)
    valid = len(by_status[KeyStatus.VALID])
    missing = len(by_status[KeyStatus.MISSING]) + len(by_status[KeyStatus.EMPTY])
    invalid = len(by_status[KeyStatus.INVALID_FORMAT])
    deprecated = len(by_status[KeyStatus.DEPRECATED_ALIAS])
    pending = len(by_status[KeyStatus.PENDING_FILL])

    print(f"  Total keys checked:  {total}")
    print(f"  Valid:               {valid}")
    print(f"  Missing/Empty:       {missing}")
    print(f"  Invalid format:      {invalid}")
    print(f"  Deprecated aliases:  {deprecated}")
    print(f"  Pending fill:        {pending}")

    if valid == total:
        print(f"\n  [PASS] All {total} keys are valid and populated.")
    elif valid > 0:
        print(f"\n  [WARN] {valid}/{total} keys valid. {missing} need attention.")
    else:
        print(f"\n  [FAIL] No valid keys found. {missing} keys need to be filled.")

    # Detail on issues
    if invalid > 0:
        print("\n  --- Format Validation Failures ---")
        for e in by_status[KeyStatus.INVALID_FORMAT]:
            print(f"    ! {e.name}: {e.error_message}")

    if deprecated > 0:
        print("\n  --- Deprecated Aliases ---")
        for e in by_status[KeyStatus.DEPRECATED_ALIAS]:
            print(f"    ! {e.name}: {e.error_message}")

    print("\n" + "=" * 70)


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Secrets Funnel Populate -- Provider Key Injection Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run              # Validate without injecting
  %(prog)s --validate-only        # Only show validation report
  %(prog)s --verify               # Verify CHIT storage
  %(prog)s -v                     # Verbose mode (with injection)
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no CHIT injection")
    parser.add_argument("--validate-only", action="store_true", help="Show validation report and exit")
    parser.add_argument("--verify", action="store_true", help="Verify CHIT storage contents")
    parser.add_argument("--keys", nargs="+", default=None, help="Specific keys to check (default: all)")
    parser.add_argument("--source", default=None, help="Override key source file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()
    logger = RedactingLogger(verbose=args.verbose)

    # Determine which keys to check
    keys_to_check = args.keys or list(KEY_VALIDATORS.keys())

    logger.info("Secrets Funnel Populate starting")
    logger.info(f"Keys to check: {len(keys_to_check)}")

    # --- VERIFY MODE ---
    if args.verify:
        logger.info("Running in VERIFY mode")
        results = verify_chit_storage(keys_to_check, logger)
        print_report(results, logger, title="CHIT Storage Verification Report")
        valid_count = sum(1 for r in results if r.status == KeyStatus.VALID)
        return 0 if valid_count == len(results) else 1

    # --- DISCOVER KEY SOURCES ---
    if args.source:
        source_files = {args.source: args.source}
    else:
        source_files = find_key_sources(logger)

    if not source_files:
        logger.error(
            "No key source files found. Expected one of: "
            + ", ".join(KEY_SOURCE_FILES)
        )
        logger.error("Create local.env with key values, or specify --source")
        return 1

    # Parse all source files (later files override earlier ones)
    all_env_vars: dict[str, str] = {}
    for filepath in source_files:
        env_vars = parse_env_file(filepath, logger)
        all_env_vars.update(env_vars)

    logger.info(f"Total unique vars loaded: {len(all_env_vars)}")

    # --- VALIDATE KEYS ---
    results = validate_all_keys(all_env_vars, keys_to_check, logger)

    # Print validation report
    print_report(results, logger)

    if args.validate_only:
        valid_count = sum(1 for r in results if r.status == KeyStatus.VALID)
        return 0 if valid_count > 0 else 1

    # --- INJECT INTO CHIT ---
    passphrase = get_chit_passphrase(logger)
    if not passphrase:
        logger.error("Cannot proceed without CHIT passphrase")
        logger.info("Set CHIT_PASSPHRASE environment variable and retry")
        return 1

    success = inject_into_chit(results, passphrase, dry_run=args.dry_run, logger=logger)

    if args.dry_run:
        logger.info("Dry run complete. No changes made.")
        logger.info("To inject for real, run without --dry-run")
    elif success:
        logger.success("Secrets funnel population complete")
        logger.info("Next: Run 'make -C pmoves secrets-verify' to confirm")
    else:
        logger.error("Secrets funnel population failed")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
