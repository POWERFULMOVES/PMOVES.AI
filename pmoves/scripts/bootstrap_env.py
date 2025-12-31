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

    def get(self, key: str) -> Optional[str]:
        if key in self.managed_values:
            return self.managed_values[key]
        if key in self.original_values:
            return self.original_values[key]
        return None

    def set(self, key: str, value: str) -> None:
        if key not in self.managed_order:
            self.managed_order.append(key)
        self.managed_values[key] = value

    def write(self) -> bool:
        if not self.managed_order:
            # No managed keys for this file – leave the original content untouched.
            return False

        lines: List[str] = []
        lines.append("# Managed by pmoves/scripts/bootstrap_env.py")
        lines.append(f"# Generated at {_dt.datetime.now(timezone.utc).isoformat()}Z")
        lines.append("")
        for key in self.managed_order:
            value = self.managed_values.get(key, "")
            lines.append(f"{key}={value}")

        preserved: List[str] = []
        for key in self.original_order:
            if key not in self.managed_order:
                preserved.append(f"{key}={self.original_values[key]}")

        if preserved or self.comments:
            lines.append("")
            lines.append("# Preserved entries (not managed by bootstrap):")
            lines.extend(preserved)
            lines.extend(self.comments)

        new_text = "\n".join(lines).rstrip() + "\n"
        if new_text != self.original_text:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as fh:
                fh.write(new_text)
            self.original_text = new_text
            return True
        return False


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
            inherited = None if existing not in (None, "") else resolve_inherit(var)
            default = existing
            if default in (None, "") and inherited not in (None, ""):
                default = inherited
            if default in (None, ""):
                default = var.get("default")
            generated = None
            if (existing in (None, "")) and var.get("generate"):
                generated = generate_value(var.get("generate"))
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
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
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
