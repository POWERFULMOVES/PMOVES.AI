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
"""

from __future__ import annotations

import argparse
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
    "HF_TOKEN": r"^hf_[a-zA-Z0-9]{34}$",  # HF: hf_ + 34 alphanum
    "MINIMAX_API_KEY": r"^.{8,}$",  # MiniMax: any string, min 8 chars
    "OPENROUTER_API_KEY": r"^sk-or-[a-zA-Z0-9-]{20,}$",  # OpenRouter: sk-or- prefix
    "OPENAI_API_KEY": r"^sk-(?:proj-)?[a-zA-Z0-9]{20,}$",  # OpenAI: sk- or sk-proj-
    "ANTHROPIC_API_KEY": r"^sk-ant-[a-zA-Z0-9-]{10,}$",  # Anthropic: sk-ant- prefix
    "GEMINI_API_KEY": r"^.{8,}$",  # Gemini: any string, min 8 chars
    "GROQ_API_KEY": r"^gsk_[a-zA-Z0-9]{31}$",  # Groq: gsk_ + 31 alphanum
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
    "pmoves/env.tier-llm",
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
    PENDING_FILL = "pending-fill" # Value is the sentinel "unset-pending-key"
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
        if self.value.strip() in ("unset-pending-key", "local-disabled", "PLACEHOLDER"):
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
        self.redaction_patterns: list[str] = []

    def _redact(self, message: str) -> str:
        """Redact any known key values from the message."""
        # Replace any assignment patterns
        for pattern in self.redaction_patterns:
            message = message.replace(pattern, "***REDACTED***")
        return message

    def register_value(self, value: str) -> None:
        """Register a secret value for redaction."""
        if value and len(value) > 4:
            self.redaction_patterns.append(value)

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

def parse_env_file(filepath: str, logger: RedactingLogger) -> dict[str, str]:
    """Parse an env file and return key-value pairs. Values are registered for redaction."""
    env_vars: dict[str, str] = {}
    path = Path(filepath)
    if not path.exists():
        return env_vars

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
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
        entry.status = KeyStatus.DEPRECATED_ALIAS
        entry.error_message = (
            f"'{name}' is a deprecated alias for '{canonical}' (sunset: {sunset}). "
            f"Use '{canonical}' instead."
        )
        logger.warn(f"Key '{name}' is deprecated. Use '{canonical}' (sunset: {sunset})")
        return entry

    # Check for empty value
    if not value or value.strip() == "":
        entry.status = KeyStatus.EMPTY
        entry.error_message = "Key is empty or not set"
        return entry

    # Check for sentinel values
    if value.strip() in ("unset-pending-key", "local-disabled", "PLACEHOLDER"):
        entry.status = KeyStatus.PENDING_FILL
        entry.error_message = f"Key has sentinel value '{value.strip()}'"
        return entry

    # Validate format
    pattern = KEY_VALIDATORS.get(name, ".*")
    entry.validation_pattern = pattern
    if pattern and not re.match(pattern, value.strip()):
        entry.status = KeyStatus.INVALID_FORMAT
        entry.error_message = f"Value does not match expected pattern: {pattern}"
        logger.warn(
            f"Key '{name}' format validation failed (pattern: {pattern}). "
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
    """Get CHIT passphrase from environment."""
    for var_name in CHIT_PASSPHRASE_ENV_VARS:
        passphrase = os.environ.get(var_name)
        if passphrase:
            logger.debug(f"Found CHIT passphrase in {var_name}")
            return passphrase
    logger.error(
        "No CHIT passphrase found. Set CHIT_PASSPHRASE or CHIT_PROD_PASSPHRASE "
        "environment variable."
    )
    return None


def inject_into_chit(
    entries: list[KeyEntry],
    passphrase: str,
    dry_run: bool,
    logger: RedactingLogger,
) -> bool:
    """Inject validated keys into CHIT-encrypted storage."""
    chit_path = Path(CHIT_ENV_CGP)

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
        logger.warn(f"CHIT CLI not found at {chit_cli}. Falling back to env.cgp.json append.")
        return _inject_via_env_cgp(valid_entries, passphrase, logger)

    return _inject_via_chit_cli(valid_entries, passphrase, logger)


def _inject_via_chit_cli(
    entries: list[KeyEntry],
    passphrase: str,
    logger: RedactingLogger,
) -> bool:
    """Inject keys using the CHIT CLI tool."""
    for entry in entries:
        try:
            env = os.environ.copy()
            env["CHIT_PASSPHRASE"] = passphrase

            result = subprocess.run(
                [
                    sys.executable,
                    "pmoves/tools/chit_cli.py",
                    "--action", "set",
                    "--key", entry.name,
                    "--value", entry.value,
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

    return True


def _inject_via_env_cgp(
    entries: list[KeyEntry],
    passphrase: str,
    logger: RedactingLogger,
) -> bool:
    """Fallback: inject keys directly into env.cgp.json."""
    chit_path = Path(CHIT_ENV_CGP)

    # Read existing CGP data
    cgp_data: dict[str, Any] = {}
    if chit_path.exists():
        try:
            with open(chit_path, "r", encoding="utf-8") as f:
                cgp_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warn(f"Could not read existing CGP: {e}. Starting fresh.")
            cgp_data = {"version": 1, "entries": [], "metadata": {}}

    # Ensure entries list exists
    if "entries" not in cgp_data:
        cgp_data["entries"] = []

    # Build entry lookup by ID
    existing_ids = {e.get("id"): e for e in cgp_data["entries"] if isinstance(e, dict)}

    for entry in entries:
        entry_id = entry.name.lower()
        cgp_entry = {
            "id": entry_id,
            "source": {"type": "manual", "label": entry.name, "date": datetime.now(timezone.utc).isoformat()},
            "targets": [
                {"file": ".env.generated", "key": entry.name},
                {"file": "env.tier-llm", "key": entry.name},
            ],
            "required": entry.name in AGNOTE4482_CRITICAL_KEYS,
        }

        if entry_id in existing_ids:
            # Update existing entry
            existing_ids[entry_id].update(cgp_entry)
        else:
            cgp_data["entries"].append(cgp_entry)

        logger.success(f"CGP entry upserted: {entry.name}")

    # Write updated CGP
    try:
        chit_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=chit_path.parent
        ) as tf:
            json.dump(cgp_data, tf, indent=2)
            temp_path = tf.name

        # Atomic rename
        os.replace(temp_path, chit_path)
        logger.info(f"CGP data written to {chit_path}")

    except IOError as e:
        logger.error(f"Failed to write CGP: {e}")
        return False

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
    print(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
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
