"""PMOVES Claude Code backend selector.

The operator's `~/.claude/settings.json` was hijacked by the Mavis SDK on/around
2026-09-10 to inject `ANTHROPIC_MODEL=MiniMax-M3[1m]` plus matching Sonnet/Opus/Haiku
defaults and a `modelPicker.replaceBuiltInOptions: true` listing only MiniMax models.
The `claude-pmoves` launcher's Mavis-SDK env strip keeps `ANTHROPIC_BASE_URL` /
`ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` (claude's NEEDS list), so the hijack
persists through to the launched `claude` process.

This module provides two surfaces:

1. Transient (per-launch). `apply_backend(backend, env)` strips the Mavis-SDK set from
   the in-memory env and emits a WARN. Invoked by `claude-pmoves.{sh,ps1}` via the
   `--backend={anthropic|minimax|auto}` flag or `PMOVES_CLAUDE_BACKEND` env var.

2. Persistent. `read_settings` / `write_settings_atomic` / `list_backups` / `backup_name`
   manage `~/.claude/settings.json` with backup-first semantics. The CLI subcommands
   `show`, `set`, `backup`, `restore`, `list-backups` are wrapped by
   `pmoves-mini claude-backend` (see `pmoves/tools/mini_cli.py`).

Templates live at `pmoves/configs/claude_settings/{anthropic,minimax}.json`.

Heuristic for `auto` mode (keyed on `ANTHROPIC_BASE_URL` only):
  - empty  -> not hijacked (preserve)
  - host == "api.anthropic.com" -> not hijacked (preserve)
  - anything else -> hijacked (strip + WARN)

Mirrors the operator-visible behaviour in
`pmoves/docs/AGENTS/claude_backend_switch_LEARNINGS.md`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

BACKENDS = ("auto", "anthropic", "minimax")
ANTHROPIC_API_HOST = "api.anthropic.com"

# The Mavis SDK set to strip when `auto` detects hijack or `anthropic` is forced.
# Includes the three vars the Mavis-SDK env-strip already preserves for claude
# (ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY) — this module
# is the OVERRIDE layer, called AFTER the strip, so we strip unconditionally when
# the backend says so.
STRIPPABLE_VARS: Tuple[str, ...] = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
    "CLAUDECODE",
)

# Prefix used to preserve stripped values for inspection (mirrors the
# PMOVES_MAVIS_SDK_<NAME> pattern from the Mavis-SDK env-strip lane, PR #3149).
STRIPPED_PREFIX = "PMOVES_CLAUDE_BACKEND_STRIPPED_"

# Substring of the per-launch WARN; pinned by TwinParityTests so the bash + ps1
# twins reference the same phrase.
WARN_PHRASE = "stripped Mavis SDK hijack"

# JSONL audit-log default fields (same shape as PMOVES_MAVIS_SDK_*) — see
# `pmoves/tools/mavis_sdk_audit.py` for the canonical schema.
AUDIT_FIELDS: Tuple[str, ...] = (
    "ts",
    "host",
    "pid",
    "cli",
    "stripped_count",
    "stripped_names",
    "all_consumed",
    "backend",
)


def parse_backend_argv(argv: Sequence[str]) -> Optional[str]:
    """Pull `--backend=<value>` (or `--backend <value>`) out of argv.

    Returns the canonical lowercase backend, or None if the flag is absent.
    Raises ValueError if the value is not in BACKENDS.
    """
    out: Optional[str] = None
    rest: List[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--backend":
            if i + 1 >= len(argv):
                raise ValueError("--backend requires a value")
            out = argv[i + 1]
            i += 2
            continue
        m = re.match(r"^--backend=(.+)$", a)
        if m:
            out = m.group(1)
            i += 1
            continue
        rest.append(a)
        i += 1
    if out is None:
        return None
    canonical = out.strip().lower()
    if canonical not in BACKENDS:
        raise ValueError(
            f"invalid --backend={out!r}; expected one of {', '.join(BACKENDS)}"
        )
    return canonical


def _host_of(url: str) -> str:
    """Return the hostname of a URL, or empty string if unparseable."""
    if not url:
        return ""
    # Tolerate both http:// and bare hostnames. urllib would be the obvious
    # choice but pulling it in for a single hostname extraction is overkill,
    # and a regex keeps the failure mode obvious (return "").
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://([^/:?#]+)", url)
    if m:
        return m.group(1).lower()
    # No scheme — assume the whole string up to "/" or ":" is a host.
    m = re.match(r"^([^/:?#]+)", url)
    return m.group(1).lower() if m else ""


def is_hijacked(env: Mapping[str, str]) -> bool:
    """True iff ANTHROPIC_BASE_URL is set AND its host is not api.anthropic.com."""
    base_url = env.get("ANTHROPIC_BASE_URL", "")
    if not base_url:
        return False
    host = _host_of(base_url)
    if host == ANTHROPIC_API_HOST:
        return False
    return True


def apply_backend(
    backend: str,
    env: Dict[str, str],
    *,
    label: str = "claude-pmoves",
) -> Tuple[List[str], Optional[str]]:
    """Mutate `env` per the backend selection. Return (stripped_names, warn_text).

    - `minimax`: no-op. Returns ([], None).
    - `auto`: strip iff hijacked (ANTHROPIC_BASE_URL host != api.anthropic.com and
      non-empty). Else no-op.
    - `anthropic`: strip unconditionally. WARN is emitted only when something was
      actually stripped.

    Originals are preserved under STRIPPED_PREFIX + NAME (process env only, never
    written to disk). The returned warn_text is None unless vars were actually
    stripped.
    """
    if backend not in BACKENDS:
        raise ValueError(
            f"apply_backend: backend must be one of {', '.join(BACKENDS)}; got {backend!r}"
        )

    if backend == "minimax":
        return [], None

    if backend == "auto" and not is_hijacked(env):
        return [], None

    stripped: List[str] = []
    for var in STRIPPABLE_VARS:
        original = env.pop(var, None)
        if original is None:
            continue
        env[STRIPPED_PREFIX + var] = original
        stripped.append(var)

    if not stripped:
        return [], None

    warn_text = (
        f"[{label}] backend={backend}: {WARN_PHRASE} ({len(stripped)} vars): "
        + ", ".join(stripped)
        + ". "
        + "Use --backend=minimax to preserve, or "
        + "'pmoves-mini claude-backend set anthropic' to make this the default."
    )
    return stripped, warn_text


def _utc_iso_basic() -> str:
    """Return a filesystem-safe UTC timestamp: 2026-09-25T13-21-34Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def backup_name(now: Optional[datetime] = None) -> str:
    """Return the canonical backup suffix used for settings.json snapshots."""
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H-%M-%SZ")


def read_settings(path: Path) -> Dict[str, Any]:
    """Parse a Claude-Code settings.json. Returns {} if file is missing or empty."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        # A partial write or malformed file. Returning {} would silently drop the
        # operator's plugins — raise instead. The caller (`show`) catches this and
        # prints a recoverable error.
        raise
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object at the top level; got {type(data).__name__}")
    return data


def write_settings_atomic(
    path: Path,
    data: Dict[str, Any],
    *,
    backup: bool = True,
) -> Optional[Path]:
    """Write `data` to `path` atomically. If `backup`, snapshot the existing file
    to `<path>.bak.<UTC-ISO>` first. Returns the backup path, or None if no
    backup was created (no existing file, or backup=False).

    Backup collisions are de-duplicated by appending `.1`, `.2`, ... — two `set`
    calls within the same UTC second each get their own snapshot. Without this,
    a same-second pair overwrites the older backup, defeating the audit trail
    that "every `set` is recoverable" relies on.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Optional[Path] = None
    if backup and path.exists():
        candidate = path.with_name(f"{path.name}.bak.{backup_name()}")
        suffix = 1
        while candidate.exists():
            candidate = path.with_name(f"{path.name}.bak.{backup_name()}.{suffix}")
            suffix += 1
        backup_path = candidate
        backup_path.write_bytes(path.read_bytes())
    tmp = path.with_name(path.name + ".new")
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return backup_path


def list_backups(settings_dir: Path) -> List[Path]:
    """Return settings.json.bak.<ISO> files in `settings_dir`, newest-first."""
    if not settings_dir.exists():
        return []
    pat = re.compile(r"^settings\.json\.bak\.([0-9TZ\-]+)$")
    found: List[Tuple[str, Path]] = []
    for entry in settings_dir.iterdir():
        if not entry.is_file():
            continue
        m = pat.match(entry.name)
        if not m:
            continue
        found.append((m.group(1), entry))
    found.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in found]


def restore_from_backup(backup_path: Path, target_path: Path) -> Path:
    """Atomically replace `target_path` with the contents of `backup_path`.
    Returns the path written."""
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_name(target_path.name + ".new")
    tmp.write_bytes(backup_path.read_bytes())
    os.replace(tmp, target_path)
    return target_path


def _home_settings_path() -> Path:
    """Return the operator's Claude Code settings.json path."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "settings.json"
    # macOS / Linux: ~/.config/claude/settings.json (matches Claude Code 2.x).
    return Path.home() / ".config" / "claude" / "settings.json"


def _templates_dir() -> Path:
    """Locate pmoves/configs/claude_settings/ relative to this module."""
    return Path(__file__).resolve().parents[1] / "configs" / "claude_settings"


def _audit_log_path(root: Optional[Path] = None) -> Path:
    """Mirror mavis_sdk_env.{sh,ps1}: $(pwd)/pmoves/data/chit/mavis_sdk_env.log
    by default, with PMOVES_MAVIS_SDK_LOG_PATH / PMOVES_MAVIS_SDK_LOG_DIR override.
    """
    override_path = os.environ.get("PMOVES_MAVIS_SDK_LOG_PATH")
    if override_path:
        return Path(override_path)
    override_dir = os.environ.get("PMOVES_MAVIS_SDK_LOG_DIR")
    base = Path(override_dir) if override_dir else (root or Path.cwd()) / "pmoves" / "data" / "chit"
    return base / "mavis_sdk_env.log"


def _audit_append(
    *,
    stripped_names: Sequence[str],
    backend: str,
    cli_name: str = "claude",
    log_path: Optional[Path] = None,
) -> None:
    """Best-effort append one JSONL line to the audit log. Mirrors the
    PMOVES_MAVIS_SDK_* audit semantics (best-effort, never a launch blocker)."""
    import socket

    path = log_path or _audit_log_path()
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "cli": cli_name,
        "stripped_count": len(stripped_names),
        "stripped_names": list(stripped_names),
        "all_consumed": False,
        "backend": backend,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # best-effort — never block the launch
        pass


def _render_show(settings: Dict[str, Any]) -> str:
    """Format the `claude-backend show` output. Pinned by tests via substring."""
    env = settings.get("env", {}) or {}
    anthropic_keys = sorted(k for k in env.keys() if k.startswith("ANTHROPIC_"))
    claude_code_keys = sorted(k for k in env.keys() if k.startswith("CLAUDE_CODE_"))
    model_picker = settings.get("modelPicker", {}) or {}
    options = model_picker.get("options", [])
    replace = model_picker.get("replaceBuiltInOptions", False)

    lines: List[str] = []
    if "model" in settings:
        lines.append(f"default model: {settings['model']}")
    if options:
        labels = ", ".join(opt.get("label") or opt.get("model", "?") for opt in options)
        lines.append(f"modelPicker: {labels}" + (" (replaceBuiltInOptions=true)" if replace else ""))
    elif replace:
        lines.append("modelPicker: (replaceBuiltInOptions=true, options=[])")
    else:
        lines.append("modelPicker: (anthropic defaults)")
    if anthropic_keys:
        lines.append("ANTHROPIC_* env overrides:")
        for k in anthropic_keys:
            v = env[k]
            if "TOKEN" in k.upper() or "KEY" in k.upper():
                v = "<redacted>"
            lines.append(f"  {k}={v}")
    else:
        lines.append("ANTHROPIC_* env overrides: (none)")
    if claude_code_keys:
        lines.append("CLAUDE_CODE_* env overrides:")
        for k in claude_code_keys:
            lines.append(f"  {k}={env[k]}")
    else:
        lines.append("CLAUDE_CODE_* env overrides: (none)")
    return "\n".join(lines)


def _print_backups(settings_dir: Path) -> None:
    backups = list_backups(settings_dir)
    if not backups:
        print("(no backups)")
        return
    print(f"backups ({len(backups)}, newest first):")
    for b in backups:
        print(f"  {b.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude_backend",
        description=(
            "PMOVES Claude Code backend selector — switches between Anthropic-direct "
            "and MiniMax-routed Claude Code via ~/.claude/settings.json."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_apply = sub.add_parser("apply", help="Apply a backend to the current process env (stdin-style).")
    p_apply.add_argument("--backend", required=True, choices=BACKENDS)
    p_apply.add_argument("--label", default="claude-pmoves")

    p_parse = sub.add_parser("parse", help="Parse a --backend= flag value out of argv.")
    p_parse.add_argument("rest", nargs=argparse.REMAINDER)

    p_show = sub.add_parser("show", help="Print current ~/.claude/settings.json state.")

    p_set = sub.add_parser("set", help="Write a template to ~/.claude/settings.json.")
    p_set.add_argument("backend", choices=("anthropic", "minimax"))

    sub.add_parser("backup", help="Snapshot ~/.claude/settings.json to a timestamped backup.")

    p_restore = sub.add_parser("restore", help="Restore ~/.claude/settings.json from a backup file.")
    p_restore.add_argument("backup_file")

    sub.add_parser("list-backups", help="List existing settings.json backup files.")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)
    settings_path = _home_settings_path()

    if args.command == "apply":
        env = dict(os.environ)
        stripped, warn = apply_backend(args.backend, env, label=args.label)
        if stripped:
            _audit_append(stripped_names=stripped, backend=args.backend, log_path=_audit_log_path())
        # Emit shell-evaluable stdout (so bash/ps1 can `eval` the result).
        # PowerShell twin does the same with PowerShell syntax via label.
        # Emit `unset NAME` for every var apply_backend stripped — the caller's
        # env had those vars set BEFORE apply_backend ran, and the function
        # removes them from its in-memory `env` dict. Without this loop the
        # bash/ps1 launcher's `eval` would never see the unset.
        for var in stripped:
            print(f"unset {var}")
        for k, v in env.items():
            if k.startswith(STRIPPED_PREFIX) or k == "PMOVES_CLAUDE_BACKEND":
                esc = v.replace("'", "'\\''")
                print(f"export {k}='{esc}'")
        if warn:
            print(warn, file=sys.stderr)
        return 0

    if args.command == "parse":
        try:
            val = parse_backend_argv(list(args.rest))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        if val is None:
            print("(no --backend flag)")
        else:
            print(val)
        return 0

    if args.command == "show":
        if not settings_path.exists():
            print("(no settings.json at", str(settings_path), ")")
            return 0
        try:
            data = read_settings(settings_path)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"error: cannot parse {settings_path}: {e}", file=sys.stderr)
            return 1
        print(_render_show(data))
        print()
        _print_backups(settings_path.parent)
        return 0

    if args.command == "set":
        template = _templates_dir() / f"{args.backend}.json"
        if not template.exists():
            print(f"error: no template at {template}", file=sys.stderr)
            return 1
        data = read_settings(template)
        backup = write_settings_atomic(settings_path, data, backup=True)
        if backup:
            print(f"claude-backend now {args.backend} (backup at {backup.name})")
        else:
            print(f"claude-backend now {args.backend} (no prior settings.json to back up)")
        return 0

    if args.command == "backup":
        if not settings_path.exists():
            print(f"error: {settings_path} does not exist; nothing to back up", file=sys.stderr)
            return 1
        backup = write_settings_atomic(settings_path, read_settings(settings_path), backup=True)
        if backup is None:
            print("error: backup failed", file=sys.stderr)
            return 1
        print(str(backup))
        return 0

    if args.command == "restore":
        backup = Path(args.backup_file)
        if not backup.name.startswith("settings.json.bak."):
            print(
                f"warning: {backup} does not match the settings.json.bak.<ISO> naming; restoring anyway",
                file=sys.stderr,
            )
        written = restore_from_backup(backup, settings_path)
        print(f"restored from {backup} -> {written}")
        return 0

    if args.command == "list-backups":
        _print_backups(settings_path.parent)
        return 0

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
