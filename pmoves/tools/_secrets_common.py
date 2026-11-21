"""Shared utilities for the secrets pipeline.

Single source-of-truth for placeholder detection, config path resolution,
and env-file parsing — used by brand_defaults, secrets_local_hydrate,
runtime_secrets_hydrate, auth_bootstrap_check, and local_cert_runners.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def force_utf8_stdio() -> None:
    """Make stdout/stderr UTF-8 so status glyphs don't crash a cp1252 Windows console.

    Windows Python defaults stdout to the locale encoding (cp1252), which raises
    ``UnicodeEncodeError`` on ``✔``/``ℹ``/``→`` etc. The funnel sets no
    ``PYTHONUTF8``/``PYTHONIOENCODING``, so tools that print glyphs must self-defend.
    A no-op when the stream can't be reconfigured (e.g. under pytest capture).
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Placeholder Detection
# ---------------------------------------------------------------------------

PLACEHOLDER_VALUES: frozenset[str] = frozenset({
    "",
    "changeme",
    "change_me",
    "base64:change_me",
    "generate_from_wger_ui",
    "surreal_user_here",
    "surreal_pass_here",
    "root",
    "pmoves4482",
    "minioadmin",
    "none",
    "null",
    "your_key_here",
    "placeholder",
    "example",
    "master_key",
    "localhack",
    "example.com",
})


def normalize_env_value(value: str) -> str:
    """Strip whitespace and unquote matching outer single/double quotes.

    Also unescapes \\" → " so repeated _set_kv calls are idempotent
    (Codex P2: quote escaping must not accumulate on re-runs).
    """
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    # Unescape any backslash-escaped quotes from prior _set_kv runs
    value = value.replace('\\"', '"').replace("\\'", "'")
    return value


def is_placeholder(value: str | None) -> bool:
    """Return True if value is missing, empty, or a known placeholder.

    Consolidated from four implementations:
    - brand_defaults._is_blank_or_placeholder
    - secrets_local_hydrate._is_empty_or_placeholder
    - runtime_secrets_hydrate._looks_placeholder
    - auth_bootstrap_check._looks_placeholder
    """
    if value is None:
        return True
    normalized = normalize_env_value(value)
    lowered = normalized.lower()
    if not lowered or lowered in PLACEHOLDER_VALUES:
        return True
    # Pattern: your_* prefix (any position), placeholder_* prefix
    if "your_" in lowered:
        return True
    if lowered.startswith("placeholder_"):
        return True
    # Pattern: <name>_here template text (CLICKHOUSE_PASSWORD_HERE). The exact
    # list only knew surreal_*_here, so other templates rode the CI bundle into
    # env.shared. Suffix + identifier-only: real secrets that contain "here"
    # elsewhere, or base64 with "_here" in it, are not templates.
    if lowered.endswith("_here") and re.fullmatch(r"[a-z0-9_]+", lowered):
        return True
    # Example domain checks (URLs and emails)
    if lowered.endswith("@example.com") or lowered.endswith(".example.com"):
        return True
    try:
        candidate = normalized if "://" in normalized else f"https://{normalized}"
        host = (urllib.parse.urlparse(candidate).hostname or "").lower()
        if host in {"example.com", "www.example.com"}:
            return True
    except (ValueError, UnicodeError):
        pass
    return False


# Whole-value unexpanded variable references. A bare `$VAR` is matched by this
# regex; a braced `${...}` expansion is matched by _is_braced_expansion, a
# brace-balanced scan, because a regex like `\$\{NAME(:-[^}]*)?\}` stops at the
# FIRST `}` and so misses nested defaults -- env.shared.example ships
# SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET:-${JWT_SECRET}}.
_BARE_REF_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
_PARAM_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# POSIX/compose parameter-expansion operators that may follow the name.
_PARAM_OPERATORS = (":-", ":=", ":+", ":?", "-", "=", "+", "?")


def _is_braced_expansion(value: str) -> bool:
    """True if *value* is exactly ONE ``${NAME}`` / ``${NAME<op>word}`` expansion.

    The braces must balance and the ``}`` matching the opening ``${`` must be the
    LAST character, so ``${A:-${B}}`` and ``${A:+${B}}`` are refs while
    ``${A}${B}`` and ``${A}-suffix`` are not (the opening brace closes early).
    The *word* after the operator is not interpreted -- whatever it holds, the
    value is still a pointer, not a secret.
    """
    if not value.startswith("${"):
        return False
    depth = 0
    for i, ch in enumerate(value):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                if i != len(value) - 1:
                    return False
                break
    else:
        return False  # unbalanced: never closed
    body = value[2:-1]
    name = _PARAM_NAME_RE.match(body)
    if name is None:
        return False
    rest = body[name.end():]
    return rest == "" or rest.startswith(_PARAM_OPERATORS)


def is_unexpanded_ref(value: str | None) -> bool:
    """Return True if the WHOLE value is an unexpanded ``${VAR}``/``$VAR`` reference.

    Semantics: whole-value only. ``$VAR``, ``${VAR}`` and one braced expansion
    with any operator and any (nested) word -- ``${A:-${B}}``, ``${A:+${B}}``,
    ``${A-x}`` -- are refs. A value that merely CONTAINS ``${`` or ``$NAME``
    (``prefix${A}``, ``sk-live-$OTHER``, ``${A}${B}``) is NOT: a real secret may
    legitimately contain ``$`` and ``{``, and refusing it would drop a value.

    Deliberately not folded into ``is_placeholder``. env.shared legitimately
    carries refs for non-secret interpolation keys, and ``is_placeholder`` also
    drives brand_defaults' config defaults and local.env hydration -- folding refs
    in there would overwrite a deliberate ``KEY=${OTHER}`` with a default. Only
    the secrets funnel (chit-export, secrets_sync, self-generated fill) treats a
    ref as a non-value, because a secret is a value, and a ref is a pointer to one.

    Measured on Z890, 2026-09-09: env.shared held SUPABASE_JWT_SECRET=``${JWT_SECRET}``
    (13 chars) where a fresh 58-char value belonged; chit-export carried it into
    the CGP, secrets_sync accepted it as non-empty, and the merge write-back spread
    it across every tier file.
    """
    if value is None:
        return False
    value = normalize_env_value(value)
    return bool(_BARE_REF_RE.fullmatch(value)) or _is_braced_expansion(value)


# ---------------------------------------------------------------------------
# Config Path Resolution
# ---------------------------------------------------------------------------

def host_config_dir() -> Path:
    """Return the platform-appropriate PMOVES config directory.

    Mirrors _config_paths.sh:pmoves_host_config_dir() logic exactly:
    checks APPDATA first (covers Windows + WSL with APPDATA set),
    then XDG_CONFIG_HOME, then platform-specific fallback.
    """
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "pmoves"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        return Path(xdg) / "pmoves"
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "pmoves"
    return Path.home() / ".config" / "pmoves"


def local_env_path() -> Path:
    """Resolve the local.env path, preferring project-local over per-user.

    Search order:
      1. pmoves/secrets/local.env (project-local, written by CI runner)
      2. $host_config_dir/secrets/local.env (per-user)
    """
    project_path = PROJECT_ROOT / "secrets" / "local.env"
    if project_path.exists():
        return project_path
    return host_config_dir() / "secrets" / "local.env"


# ---------------------------------------------------------------------------
# Env File Parsing
# ---------------------------------------------------------------------------

def validate_secret_value(key: str, value: str) -> tuple[bool, str | None]:
    """Validate a secret value for corruption or format issues.

    Returns:
        (is_valid, error_message) - If invalid, error_message explains why

    Checks for:
    - Actual newlines (literal \\n is allowed for JWTs/multiline configs)
    - Suspicious patterns (base64 fragments concatenated to API keys)

    There is deliberately NO rule against '+' with '=' padding. An earlier rule
    rejected any unquoted value containing '+' and ending in '=', claiming it
    "will break Docker Compose parsing". Measured 2026-11-20 (B850): a throwaway
    compose file with ``PW=Ab+cd/ef12345678=`` in both ``env_file`` and
    ``--env-file`` rendered the value unchanged through ``env_file`` AND
    ``${PW}`` interpolation (``docker compose config``). The rule only dropped
    legitimate base64 passwords (WGER_ADMIN_PASSWORD on B850).
    """
    if not value:
        return True, None

    # Check for actual newlines (literal \n is allowed for JWTs/multiline configs)
    if "\n" in value or "\r" in value:
        return False, "contains actual newline characters - secret values must be single-line"

    # Check for suspicious base64 concatenation patterns
    # Pattern: API key followed by base64-like string (alnum+/= with padding)
    if len(value) > 100:  # Normal API keys are < 100 chars
        # Look for base64 padding (= or ==) not at the start
        if value.find("=") > 50:
            # Check if there's a transition from non-base64 to base64
            # Common API keys: alnum with specific prefixes (AIza, sk-, etc.)
            # Pattern: prefix like "AIza" or "sk-" followed by base64
            if re.search(r'[A-Za-z0-9_-]{20,}[=]{1,2}[A-Za-z0-9+/=]{10,}', value):
                return False, "appears to be multiple values concatenated (API key + base64 fragment)"

    return True, None


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse KEY=VALUE lines from a dotenv file, skipping comments and blanks.

    Values that fail ``validate_secret_value`` are dropped (a key-name-only
    WARNING goes to stderr). A caller that must know WHICH keys were dropped
    should call ``parse_env_file_with_report`` instead.
    """
    values, _skipped = parse_env_file_with_report(path)
    return values


def parse_env_file_with_report(path: Path) -> Tuple[Dict[str, str], List[str]]:
    """Like ``parse_env_file``, but also return the keys it dropped.

    Returns ``(values, skipped_keys)``. ``skipped_keys`` lists, in file order,
    the KEY NAMES whose value failed ``validate_secret_value``; values are never
    reported. Lines whose left side is not a valid key are not reported: that
    branch exists to discard base64 fragments, so the "key" there may be part
    of a secret.
    """
    values: Dict[str, str] = {}
    skipped: List[str] = []
    if not path.exists():
        return values, skipped
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]

        # Skip lines without proper KEY=VALUE format
        # Must have '=' with non-empty key and value on both sides
        if "=" not in line:
            continue

        # Split on first '=' only
        parts = line.split("=", 1)
        if len(parts) != 2:
            continue

        key, value = parts
        key = key.strip()

        # Validate key format (uppercase alphanumeric with underscores)
        if not key or not key.isupper() or not key.replace("_", "").isalnum():
            # Skip lines that don't look like KEY=VALUE format
            # This catches base64 fragments with '=' padding like "abcd1234=="
            continue

        # Validate the value format
        is_valid, error = validate_secret_value(key, value)
        if not is_valid:
            # Log only key name (CodeQL safe: no value taint, no error message)
            print(f"WARNING: Skipping malformed secret '{key}' (validation failed)", file=sys.stderr)
            skipped.append(key)
            continue

        # Strip/normalize value before storage (regression prevention from PR #1356)
        value = normalize_env_value(value)
        values[key] = value
    return values, skipped
