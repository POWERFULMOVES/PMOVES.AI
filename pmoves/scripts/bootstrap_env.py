"""Interactive environment bootstrapper for PMOVES services.

This utility reads a declarative registry of required configuration values,
prompts the operator for any missing secrets or endpoints, and writes the
appropriate `.env` overlays.  It also supports non-interactive validation so
`make preflight` can fail fast when required inputs are absent.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import secrets
import string
import sys
from dataclasses import dataclass, field
from getpass import getpass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "pmoves" / "bootstrap" / "registry.json"
ENV_SHARED_PATH = REPO_ROOT / "pmoves" / "env.shared"
CLEARED_KEYS_PATH = REPO_ROOT / "pmoves" / "configs" / "secrets_cleared.yaml"
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Used only when neither the command line nor the registry declares an axis.
DEFAULT_GEN_TYPE = "random_urlsafe"
DEFAULT_GEN_LENGTH = 48


def read_cleared_keys(path: Optional[Path] = None) -> List[str]:
    """Keys deliberately held empty, in declaration order.

    Line-parsed rather than YAML-parsed, matching pytest_ratchet.py and
    hardening_ratchet.py: this runs inside a *bootstrap* script, which must not
    acquire a pyyaml dependency to do its job. The file's leading comment block
    is load-bearing documentation and a JSON file could not carry it.
    """
    target = path or CLEARED_KEYS_PATH
    if not target.is_file():
        return []
    keys: List[str] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- "):
            key = line[2:].strip().strip("\"'")
            if key and key not in keys:
                keys.append(key)
    return keys


def _write_cleared_keys(keys: List[str], path: Optional[Path] = None) -> None:
    """Rewrite the tombstone list, preserving the explanatory header verbatim."""
    target = path or CLEARED_KEYS_PATH
    header: List[str] = []
    if target.is_file():
        for line in target.read_text(encoding="utf-8").splitlines():
            if line.startswith("cleared_keys:"):
                break
            header.append(line)
    body = ["cleared_keys: []"] if not keys else ["cleared_keys:"] + [
        f'  - "{k}"' for k in sorted(keys)
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(header + body) + "\n", encoding="utf-8")


def mark_key_cleared(key: str, path: Optional[Path] = None) -> None:
    """Record *key* as deliberately empty so hydrate() cannot re-populate it."""
    keys = read_cleared_keys(path)
    if key not in keys:
        keys.append(key)
        _write_cleared_keys(keys, path)


def unmark_key_cleared(key: str, path: Optional[Path] = None) -> None:
    """Drop *key* from the tombstone — it now carries a real value again."""
    keys = read_cleared_keys(path)
    if key in keys:
        _write_cleared_keys([k for k in keys if k != key], path)


def _warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"[info] {msg}")


def _error(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)


def load_registry(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Bootstrap registry not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Unable to parse bootstrap registry ({path}): {exc}") from exc
    if data.get("version") != 1:
        raise ValueError("Unsupported bootstrap registry version (expected 1)")
    return data


def generate_value(spec: Optional[Dict]) -> Optional[str]:
    if not spec or "type" not in spec:
        return None
    gen_type = spec["type"]
    if gen_type == "random_hex":
        length = int(spec.get("length", 32))
        if length % 2 != 0:
            length += 1
        return secrets.token_hex(length // 2)
    return _generate_token_or_passphrase(spec, gen_type)


def _generate_token_or_passphrase(spec: Dict, gen_type: str) -> Optional[str]:
    if gen_type == "random_urlsafe":
        length = int(spec.get("length", 32))
        token = secrets.token_urlsafe(length)
        return token[:length]
    if gen_type == "passphrase":
        words = int(spec.get("words", 4))
        alphabet = string.ascii_lowercase
        return "-".join(
            "".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(words)
        )
    _warn(f"Unknown generator type '{gen_type}'")
    return None


def value_matches_spec(value: Optional[str], spec: Optional[Dict]) -> bool:
    """Return True if `value` looks like a valid output of `spec`.

    Used to detect corrupted previously-generated values (non-hex chars in a
    random_hex slot, wrong length, etc.). When False, the bootstrap path
    treats the slot as empty and regenerates — so a single `make env-setup
    ARGS=--accept-defaults` self-heals VAULT_ENC_KEY / PG_META_CRYPTO_KEY /
    LOGFLARE_*_TOKEN drift without operator intervention.
    """
    if not value or not spec or "type" not in spec:
        return True  # nothing to check against
    gen_type = spec["type"]
    if gen_type == "random_hex":
        length = int(spec.get("length", 32))
        if len(value) != length:
            return False
        return all(c in string.hexdigits for c in value)
    # Intentionally lax for random_urlsafe: some legacy values were generated
    # via `openssl rand -base64 | tr -d '='` which includes `+` and `/` (not
    # strictly url-safe). Regenerating those would rotate working n8n / wger /
    # jellyfin passwords for no security benefit. Only hex values get the
    # strict character-set check because their downstream consumers (Fernet /
    # vault keys) actually require hex.
    return True


def _registry_generator(key: str, registry_path: Optional[str] = None) -> Optional[dict]:
    """The `generate` spec the bootstrap registry declares for *key*, if any.

    Returns e.g. {"type": "random_hex", "length": 32}. None when the key is not
    in the registry or declares no generator — callers then fall back to the
    historical default.

    Read failures are swallowed deliberately: a rotation must not be blocked by
    an unreadable registry, it should just lose the type hint and say so by
    printing nothing.
    """
    try:
        import json as _json

        path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
        data = _json.loads(path.read_text(encoding="utf-8"))
        for service in data.get("services") or []:
            for var in service.get("variables") or []:
                if var.get("key") == key:
                    gen = var.get("generate")
                    return gen if isinstance(gen, dict) else None
    except Exception:
        return None
    return None


def _resolve_generator_axes(
    key: str,
    registry_path: Optional[str],
    gen_type: Optional[str],
    length: Optional[int],
) -> Tuple[str, int, str, str]:
    """Resolve (gen_type, length) for a rotation, one axis at a time.

    Returns (gen_type, length, type_source, length_source), where each *source*
    is the provenance string the log line reports for that axis.

    THE TWO AXES ARE INDEPENDENT. Naming one on the command line must not
    discard the registry's declaration of the other. The previous version put
    the whole registry lookup under ``if gen_type is None``, so
    ``--rotate VAULT_ENC_KEY --gen-type random_hex`` skipped the lookup entirely
    and fell through to the built-in 48 -- while the registry declares 32 and
    the yt OAuth flow does bytes.fromhex() on the result. That turned the flag
    an operator would reach for to *avoid* the corruption into a second way to
    reproduce it, and did so silently: the provenance line lived inside the
    same skipped branch, so nothing was printed at all.

    `passphrase` sizes itself from ``words`` and ignores ``length``, so
    inheriting a declared length across an explicit type change is inert
    rather than wrong.
    """
    type_source = "--gen-type" if gen_type is not None else ""
    length_source = "--length" if length is not None else ""

    if gen_type is None or length is None:
        declared = _registry_generator(key, registry_path) or {}
        if gen_type is None and declared.get("type"):
            gen_type = declared["type"]
            type_source = "bootstrap registry"
        if length is None and declared.get("length"):
            length = int(declared["length"])
            length_source = "bootstrap registry"

    if gen_type is None:
        gen_type, type_source = DEFAULT_GEN_TYPE, "built-in default"
    if length is None:
        length, length_source = DEFAULT_GEN_LENGTH, "built-in default"

    return gen_type, length, type_source, length_source


def rotate_secret(
    key: str,
    *,
    value: Optional[str] = None,
    length: int = 48,
    gen_type: str = "random_urlsafe",
    env_path: Optional[Path] = None,
    allow_empty: bool = False,
) -> str:
    """Surgically rotate a single secret in env.shared (the secrets-funnel source).

    Replaces the ``KEY=...`` line in place — preserving every other line, comment,
    and ordering exactly — or appends ``KEY=value`` if the key is absent. When
    *value* is None a fresh value is generated from (gen_type, length). The new
    value must be single-line: multi-line values corrupt line-based env files
    (see ``secrets_sync._drop_multiline``); PEM/SSH keys belong in the ``*_FILE``
    convention, not here.

    env.shared is the canonical funnel source — after rotating, run
    ``make -C pmoves chit-export`` (encode env.shared -> CGP bundle) then
    ``make -C pmoves secrets-funnel`` to propagate to the tier env files.

    *allow_empty* permits writing ``KEY=`` (the empty value). It is off by
    default and must be asked for explicitly, because an empty value is
    indistinguishable from an unset shell variable at the call site — without
    this gate, ``--value "$SOME_UNSET_VAR"`` would silently blank a live
    credential. Empty is a legitimate *configured state* for some keys, not an
    absence: Supabase ships ``SUPABASE_SECRET_KEY`` and
    ``SUPABASE_PUBLISHABLE_KEY`` empty on purpose and its Kong entrypoint
    strips blank key entries, so a populated one is what breaks the deployment
    (see #2593/#2595 — a duplicate key crash-looped Kong 3,924 times). Before
    this parameter existed the pipeline could not express that state at all.

    Returns the new value; callers MUST NOT log it.
    """
    target = env_path or ENV_SHARED_PATH
    if not _ENV_KEY_RE.match(key or ""):
        raise ValueError(
            f"invalid env key (must match [A-Za-z_][A-Za-z0-9_]*): {key!r}"
        )
    if value is None and not allow_empty:
        value = generate_value({"type": gen_type, "length": length})
    if value is None:
        value = ""
    if not value and not allow_empty:
        raise ValueError(
            f"no value to rotate {key!r}: pass --value, or use a generatable "
            f"--gen-type. To deliberately blank it, use --clear {key}."
        )
    if "\n" in value or "\r" in value:
        raise ValueError(
            f"refusing to write a multi-line value for {key!r} — multi-line values "
            "corrupt line-based env files; use the *_FILE convention for PEM/SSH keys"
        )
    if not target.exists():
        raise FileNotFoundError(f"env file not found: {target}")

    original = target.read_text(encoding="utf-8")
    new_line = f"{key}={value}"
    out: List[str] = []
    replaced = False
    for raw in original.splitlines():
        stripped = raw.lstrip()
        is_target = (
            "=" in stripped
            and not stripped.startswith("#")
            and stripped.split("=", 1)[0].strip() == key
        )
        if is_target:
            # Replace the first occurrence; DROP any later duplicates so a stale
            # later value can't win in last-wins env parsers (chit_encode_secrets).
            if not replaced:
                out.append(new_line)
                replaced = True
            continue
        out.append(raw)
    if not replaced:
        out.append(new_line)
    text = "\n".join(out)
    if original.endswith("\n") or not original:
        text += "\n"
    target.write_text(text, encoding="utf-8")
    return value


def normalize_bool(value: str) -> str:
    truthy = {"true", "t", "yes", "y", "1"}
    falsy = {"false", "f", "no", "n", "0"}
    lower = value.lower()
    if lower in truthy:
        return "true"
    if lower in falsy:
        return "false"
    raise ValueError("Enter true/false or y/n")


def validate_value(value: str, meta: Dict) -> Tuple[bool, Optional[str]]:
    if value == "" and not meta.get("required", False):
        return True, None
    val_type = meta.get("type", "string")
    if val_type in {"string", "url_optional"}:
        if val_type == "url_optional" and value:
            val_type = "url"
        else:
            return True, None
    if val_type == "url":
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            return True, None
        return False, "Provide a full URL (e.g. http://localhost:65421/rest/v1)."
    if val_type == "int":
        try:
            int(value)
            return True, None
        except ValueError:
            return False, "Enter a valid integer."
    if val_type == "bool":
        try:
            normalize_bool(value)
            return True, None
        except ValueError as exc:
            return False, str(exc)
    return True, None


def normalize_value(value: str, meta: Dict) -> str:
    val_type = meta.get("type", "string")
    if val_type == "bool":
        return normalize_bool(value)
    if val_type == "int":
        return str(int(value))
    return value


@dataclass
class EnvFile:
    path: Path
    original_values: Dict[str, str] = field(default_factory=dict)
    original_order: List[str] = field(default_factory=list)
    original_text: str = ""
    comments: List[str] = field(default_factory=list)
    managed_values: Dict[str, str] = field(default_factory=dict)
    managed_order: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path.exists():
            self.original_text = self.path.read_text(encoding="utf-8")
            self._parse_existing(self.original_text)

    def _parse_existing(self, text: str) -> None:
        for raw_line in text.splitlines():
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# Managed by pmoves/scripts/bootstrap_env.py"):
                continue
            if stripped.startswith("# Generated at "):
                continue
            if stripped.startswith("# Preserved entries (not managed by bootstrap)"):
                continue
            if stripped.startswith("#"):
                self.comments.append(line)
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key not in self.original_values:
                    self.original_order.append(key)
                self.original_values[key] = value
            else:
                self.comments.append(line)

    def _build_preserve_allowlist(self) -> set:
        """Build allowlist of keys that may be preserved from the existing file.

        Keys from env.shared.example and bootstrap/registry.json are allowed.
        This prevents leaked host environment variables (Windows PATH, CUDA_PATH,
        VSCODE_*, etc.) from surviving rewrites.
        """
        allowed: set = set()
        pmoves_dir = self.path.parent

        # Keys from template (env.shared.example)
        template = pmoves_dir / (self.path.name + ".example")
        if template.exists():
            for line in template.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    allowed.add(s.split("=", 1)[0].strip())

        # Keys from bootstrap registry
        registry_path = pmoves_dir / "bootstrap" / "registry.json"
        if registry_path.exists():
            try:
                data = json.loads(registry_path.read_text(encoding="utf-8"))
                for svc in data.get("services", []):
                    for var in svc.get("variables", []):
                        if k := var.get("key"):
                            allowed.add(k)
            except (json.JSONDecodeError, KeyError):
                pass

        # Also allow all currently managed keys (from this run)
        allowed.update(self.managed_order)

        return allowed

    def get(self, key: str) -> Optional[str]:
        raw: Optional[str] = None
        if key in self.managed_values:
            raw = self.managed_values[key]
        elif key in self.original_values:
            raw = self.original_values[key]
        if raw is None:
            return None
        return self._resolve_placeholder(raw)

    def _resolve_placeholder(self, value: str, depth: int = 0) -> Optional[str]:
        """Resolve ${VAR} placeholders from values already present in this file.

        This avoids treating unresolved aliases as real values during bootstrap.
        """
        if depth > 4:
            return None
        match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value.strip())
        if not match:
            return value
        ref_key = match.group(1)
        ref_val = self.managed_values.get(ref_key)
        if ref_val in (None, ""):
            ref_val = self.original_values.get(ref_key)
        if ref_val in (None, ""):
            return None
        return self._resolve_placeholder(ref_val, depth + 1)

    def set(self, key: str, value: str) -> None:
        if key not in self.managed_order:
            self.managed_order.append(key)
        self.managed_values[key] = value

    @staticmethod
    def _strip_timestamp(text: str) -> str:
        """Return *text* with the ``# Generated at ...`` line removed for comparison."""
        return "\n".join(
            ln for ln in text.splitlines() if not ln.startswith("# Generated at ")
        )

    def write(self) -> bool:
        if not self.managed_order:
            # No managed keys for this file – leave the original content untouched.
            return False

        lines: List[str] = []
        lines.append("# Managed by pmoves/scripts/bootstrap_env.py")
        lines.append("")  # placeholder — filled with timestamp only on real change
        lines.append("")
        for key in self.managed_order:
            value = self.managed_values.get(key, "")
            lines.append(f"{key}={value}")

        preserved: List[str] = []
        allowlist = self._build_preserve_allowlist()
        for key in self.original_order:
            if key not in self.managed_order:
                # Only preserve keys that appear in the canonical allowlist.
                # This prevents leaked host environment variables (e.g., Windows
                # PATH, CUDA_PATH, VSCODE_*) from persisting across rewrites.
                if allowlist and key not in allowlist:
                    continue
                preserved.append(f"{key}={self.original_values[key]}")

        if preserved or self.comments:
            lines.append("")
            lines.append("# Preserved entries (not managed by bootstrap):")
            lines.extend(preserved)
            lines.extend(self.comments)

        new_body = "\n".join(lines).rstrip() + "\n"
        if self._strip_timestamp(new_body) == self._strip_timestamp(self.original_text):
            return False  # No value change — skip rewrite to avoid timestamp churn

        # Values actually changed — inject fresh timestamp and write.
        lines[1] = f"# Generated at {_dt.datetime.now(_dt.timezone.utc).isoformat()}Z"
        final_text = "\n".join(lines).rstrip() + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            fh.write(final_text)
        self.original_text = final_text
        return True


def select_services(registry: Dict, selected_ids: Optional[Iterable[str]]) -> List[Dict]:
    services = registry.get("services", [])
    if not selected_ids:
        return services
    wanted = set(selected_ids)
    matched = [svc for svc in services if svc.get("id") in wanted]
    missing = wanted - {svc.get("id") for svc in matched}
    if missing:
        raise ValueError(f"Unknown service id(s): {', '.join(sorted(missing))}")
    return matched


def run_check(registry: Dict, services: List[Dict]) -> int:
    missing: List[Tuple[str, str, str]] = []
    for svc in services:
        for var in svc.get("variables", []):
            file_path = REPO_ROOT / var["file"]
            env = EnvFile(file_path)
            existing = env.get(var["key"])
            if existing is not None and existing != "":
                continue
            if not var.get("required", False):
                continue
            missing.append((svc.get("name", svc["id"]), var["file"], var["key"]))
    if missing:
        _error("Missing required configuration values:")
        for svc_name, file_rel, key in missing:
            _error(f"  - [{svc_name}] {key} (file: {file_rel})")
        return 1
    _info("All required variables are populated.")
    return 0


def prompt_for_value(
    svc_name: str,
    var: Dict,
    default_value: Optional[str],
    pre_generated: Optional[str],
) -> str:
    prompt_text = var.get("prompt", var["key"])
    help_text = var.get("help")
    required = var.get("required", False)
    sensitive = var.get("sensitive", False)

    if help_text:
        print(f"\n[{svc_name}] {prompt_text}")
        print(f"  {help_text}")
    else:
        print(f"\n[{svc_name}] {prompt_text}")

    display_default: Optional[str] = default_value
    if sensitive and display_default:
        display_default = "***"
    if pre_generated and not default_value:
        display_default = "(auto-generated)"
    elif default_value is None:
        display_default = None

    suffix = ""
    if display_default not in (None, ""):
        suffix = f" [{display_default}]"

    while True:
        raw = getpass(f"  value{suffix}: ") if sensitive else input(f"  value{suffix}: ")
        if not raw:
            if default_value not in (None, ""):
                raw = default_value
            elif pre_generated:
                raw = pre_generated
            elif required:
                print("  → This value is required. Please enter a value.")
                continue
            else:
                raw = ""
        ok, message = validate_value(raw, var)
        if not ok:
            print(f"  → {message}")
            continue
        return normalize_value(raw, var)


def bootstrap(registry: Dict, services: List[Dict], accept_defaults: bool) -> int:
    env_files: Dict[str, EnvFile] = {}
    updated_files: List[Path] = []

    def get_env(path_str: str) -> EnvFile:
        if path_str not in env_files:
            env_files[path_str] = EnvFile(REPO_ROOT / path_str)
        return env_files[path_str]

    def resolve_inherit(meta: Dict) -> Optional[str]:
        inherit = meta.get("inherit")
        if not inherit:
            return None
        if isinstance(inherit, dict):
            file_path = inherit.get("file")
            key = inherit.get("key")
            if file_path and key:
                value = get_env(file_path).get(key)
                if value not in (None, ""):
                    return value
        elif isinstance(inherit, str):
            value = os.environ.get(inherit)
            if value not in (None, ""):
                return value
        return None

    incomplete_defaults: List[Tuple[str, str]] = []

    for svc in services:
        svc_name = svc.get("name", svc["id"])
        for var in svc.get("variables", []):
            env = get_env(var["file"])
            key = var["key"]
            existing = env.get(key)
            # Detect corrupted previously-generated values (e.g. non-hex chars in
            # a random_hex slot). When the existing value fails the generator's
            # format check, treat the slot as empty so the regen path fires.
            gen_spec = var.get("generate")
            if existing and gen_spec and not value_matches_spec(existing, gen_spec):
                _warn(f"{key} in {var['file']} fails {gen_spec.get('type')} format check — regenerating")
                existing = None
                env.set(key, "")
            inherited = None if existing not in (None, "") else resolve_inherit(var)
            default = existing
            if default in (None, "") and inherited not in (None, ""):
                default = inherited
            if default in (None, ""):
                default = var.get("default")
            generated = None
            if (existing in (None, "")) and gen_spec:
                generated = generate_value(gen_spec)
                if default in (None, "") and generated:
                    default = generated

            if accept_defaults:
                if default not in (None, ""):
                    value = normalize_value(str(default), var)
                elif generated:
                    value = normalize_value(str(generated), var)
                elif not var.get("required", False):
                    value = ""
                else:
                    incomplete_defaults.append((svc_name, key))
                    continue
            else:
                value = prompt_for_value(svc_name, var, default, generated)

            env.set(key, value)

    if accept_defaults and incomplete_defaults:
        _error("Could not satisfy required values in non-interactive mode:")
        for svc_name, key in incomplete_defaults:
            _error(f"  - [{svc_name}] {key}")
        _error("Re-run without --accept-defaults or pre-populate the values.")
        return 2

    for file_key, env in env_files.items():
        changed = env.write()
        if changed:
            updated_files.append(env.path.relative_to(REPO_ROOT))

    if updated_files:
        _info("Updated configuration files:")
        for path in updated_files:
            _info(f"  - {path}")
    else:
        _info("No changes were necessary.")
    return 0


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap PMOVES environment configuration."
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help=f"Path to registry JSON (default: {DEFAULT_REGISTRY_PATH})",
    )
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Limit to specific service id(s). Can be supplied multiple times.",
    )
    parser.add_argument(
        "--accept-defaults",
        action="store_true",
        help="Use defaults and generated values without prompting.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; exit non-zero if required values are missing.",
    )
    parser.add_argument(
        "--rotate",
        metavar="KEY",
        help="Rotate a single secret in env.shared (surgical in-place replace). "
        "Then run: make -C pmoves chit-export && make -C pmoves secrets-funnel.",
    )
    parser.add_argument(
        "--clear",
        metavar="KEY",
        help="Set a single key in env.shared to the EMPTY value (surgical in-place). "
        "Empty is a real configured state for some keys — Supabase ships "
        "SUPABASE_SECRET_KEY / SUPABASE_PUBLISHABLE_KEY empty and its Kong "
        "entrypoint strips blank entries — and --rotate cannot express it. "
        "Separate flag rather than --value '' so blanking a credential is always "
        "deliberate, never the result of an unset shell variable. "
        "Then run: make -C pmoves chit-export && make -C pmoves secrets-funnel.",
    )
    parser.add_argument(
        "--value",
        help="Explicit new value for --rotate (e.g. an externally-minted API key). "
        "If omitted, a value is generated from --gen-type/--length. "
        "Prefer --value-env for values with shell-active characters.",
    )
    parser.add_argument(
        "--value-env",
        metavar="VARNAME",
        help="Read the --rotate value from this environment variable (shell-safe: "
        "the secret never passes through argv/make expansion). Overrides --value.",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=None,
        help=(
            "Length of the generated --rotate value. "
            "Default: the length the registry declares for this key, else 48."
        ),
    )
    parser.add_argument(
        "--gen-type",
        default=None,
        help=(
            "Generator type for --rotate (random_urlsafe | random_hex | passphrase). "
            "Default: the type the registry declares for this key, else random_urlsafe."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    if args.clear and args.rotate:
        _error("--clear and --rotate are mutually exclusive: pick one key operation")
        return 2

    if args.clear:
        try:
            rotate_secret(args.clear, value="", allow_empty=True)
        except (ValueError, FileNotFoundError) as exc:
            _error(str(exc))
            return 2
        # Tombstone BEFORE reporting success. secrets-funnel runs
        # secrets-local-hydrate as its second step, and hydrate() treats the
        # empty string as a placeholder (it is the first entry in
        # PLACEHOLDER_VALUES), so without this record the very next funnel run
        # overlays the stale local.env value back on top and silently undoes
        # the clear.
        mark_key_cleared(args.clear)
        _info(
            f"Cleared {args.clear} in env.shared (now empty) and recorded it in "
            f"{CLEARED_KEYS_PATH.name} so secrets-local-hydrate cannot restore it. "
            "Next: make -C pmoves chit-export && make -C pmoves secrets-funnel, "
            "then restart the affected consumers."
        )
        return 0

    if args.rotate:
        rotate_value = args.value
        if args.value_env:
            rotate_value = os.environ.get(args.value_env)
            if rotate_value is None:
                _error(f"--value-env {args.value_env}: environment variable not set")
                return 2
        # HONOUR THE REGISTRY'S DECLARED GENERATOR.
        #
        # This defaulted to random_urlsafe regardless of what the key IS, and
        # `make secrets-rotate` never passed --gen-type. So rotating a key the
        # registry declares as {"type": "random_hex", "length": 32} produced a
        # 48-char urlsafe value instead.
        #
        # That is not hypothetical: it is how VAULT_ENC_KEY got corrupted on the
        # 4090 (measured 2026-09-01 -- len 48, urlsafe charset, not hex). The
        # yt OAuth flow does bytes.fromhex() on it, raised ValueError, swallowed
        # it, and reported "Encryption is unavailable" with the key set. A
        # completed browser consent was discarded as a result.
        #
        # Rotating to repair it would have regenerated urlsafe again and
        # reproduced the same defect, which is the trap this closes.
        # BOTH AXES COME FROM THE REGISTRY, OR NEITHER DOES.
        #
        # The first version of this block resolved `type` from the registry but
        # left `--length` defaulting to 48, so `gen_length` was never None and
        # the length branch below could not fire. The registry's declared length
        # was read, printed, and discarded.
        #
        # Measured 2026-09-02: rotating SECRET_KEY_BASE (registry: 96) emitted a
        # 48-char value, and supabase-realtime stayed in its crash loop
        # ("cookie store expects conn.secret_key_base to be at least 64 bytes").
        # The same hole meant VAULT_ENC_KEY would rotate to 48 hex chars where
        # Supabase documents "exactly 32 characters" -- a value Supavisor
        # rejects.
        #
        # `--gen-type` and `--length` therefore BOTH default to None: None means
        # "not specified, ask the registry", and an explicit flag always wins.
        gen_type, gen_length, type_source, length_source = _resolve_generator_axes(
            args.rotate, args.registry, args.gen_type, args.length
        )
        # Attribute each axis to where it actually came from, and print it
        # unconditionally. Claiming "from bootstrap registry" over a value the
        # registry did not supply -- or printing nothing at all because an
        # explicit flag was given -- is the step-report defect this file
        # exists to avoid.
        if rotate_value is None:
            print(
                f"generator for {args.rotate}: "
                f"{gen_type} (from {type_source}), "
                f"length {gen_length} (from {length_source})"
            )
        try:
            rotate_secret(
                args.rotate,
                value=rotate_value,
                length=gen_length,
                gen_type=gen_type,
            )
        except (ValueError, FileNotFoundError) as exc:
            _error(str(exc))
            return 2
        # A key that now carries a real value is no longer deliberately empty.
        # Leaving the tombstone would permanently block hydrate() from ever
        # overlaying this key again — a clear followed by a rotate must not
        # leave a latent trap behind.
        unmark_key_cleared(args.rotate)
        source = (
            "supplied value"
            if (args.value or args.value_env)
            else f"generated {gen_type}, length {gen_length}"
        )
        _info(
            f"Rotated {args.rotate} in env.shared ({source}). "
            "Next: make -C pmoves chit-export && make -C pmoves secrets-funnel, "
            "then restart the affected consumers."
        )
        return 0

    registry = load_registry(args.registry)
    try:
        services = select_services(registry, args.services)
    except ValueError as exc:
        _error(str(exc))
        return 2

    if args.check:
        return run_check(registry, services)

    try:
        return bootstrap(registry, services, accept_defaults=args.accept_defaults)
    except KeyboardInterrupt:
        _warn("Aborted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
