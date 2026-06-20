"""Generate env files from the CHIT secrets manifest."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

import yaml

from pmoves.chit.codec import decode_secret_map, load_cgp

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent


@dataclass
class Target:
    file: str
    key: str


@dataclass
class Entry:
    id: str
    label: str
    required: bool
    targets: Sequence[Target]


def load_manifest(path: Path) -> tuple[Path, Sequence[Entry]]:
    manifest_data = yaml.safe_load(path.read_text())
    if not isinstance(manifest_data, Mapping):
        raise ValueError("Manifest must be a mapping")
    if manifest_data.get("version") != 1:
        raise ValueError("Unsupported manifest version")

    default_targets: Sequence[Target] = []
    defaults = manifest_data.get("defaults", {})
    if isinstance(defaults, Mapping):
        target_data = defaults.get("targets", [])
        if isinstance(target_data, list):
            default_targets = [_parse_target(item) for item in target_data]

    cgp_file = manifest_data.get("cgp_file")
    if not isinstance(cgp_file, str):
        raise ValueError("Manifest missing 'cgp_file'")
    cgp_path = (REPO_ROOT / cgp_file).resolve()

    entries_raw = manifest_data.get("entries")
    if not isinstance(entries_raw, list):
        raise ValueError("Manifest 'entries' must be a list")

    entries: List[Entry] = []
    for item in entries_raw:
        if not isinstance(item, Mapping):
            continue
        entry_id = item.get("id")
        source = item.get("source", {})
        if not isinstance(entry_id, str):
            raise ValueError("Entry missing id")
        if not isinstance(source, Mapping):
            raise ValueError(f"Entry {entry_id} missing source mapping")
        if source.get("type") != "cgp":
            raise ValueError(f"Entry {entry_id} uses unsupported source")
        label = source.get("label")
        if not isinstance(label, str):
            raise ValueError(f"Entry {entry_id} missing source label")

        targets_data = item.get("targets")
        if isinstance(targets_data, list) and targets_data:
            targets = [_parse_target(t) for t in targets_data]
        else:
            targets = list(default_targets)
        if not targets:
            raise ValueError(f"Entry {entry_id} has no targets")

        required = bool(item.get("required", True))
        entries.append(Entry(id=entry_id, label=label, required=required, targets=targets))

    return cgp_path, entries


def _parse_target(data: Mapping) -> Target:
    if not isinstance(data, Mapping):
        raise ValueError("Target must be a mapping")
    file_name = data.get("file")
    key = data.get("key")
    if not isinstance(file_name, str) or not file_name:
        raise ValueError("Target missing file")
    if key is None:
        key = ""
    if not isinstance(key, str) or not key:
        raise ValueError("Target missing key")
    return Target(file=file_name, key=key)


def build_outputs(
    secrets: Mapping[str, str],
    entries: Sequence[Entry],
    *,
    strict: bool = True,
) -> tuple[Dict[str, Dict[str, str]], List[str]]:
    outputs: Dict[str, Dict[str, str]] = defaultdict(dict)
    missing: List[str] = []
    for entry in entries:
        if entry.label not in secrets:
            if entry.required:
                missing.append(entry.label)
            continue
        value = secrets[entry.label]
        for target in entry.targets:
            outputs[target.file][target.key] = value
    if missing and strict:
        joined = ", ".join(sorted(missing))
        raise KeyError(f"Missing required secrets: {joined}")
    return outputs, missing


def _drop_multiline(relative: str, values: Mapping[str, str]) -> Dict[str, str]:
    """Refuse to emit newline-bearing values into a line-based env file.

    Docker Compose `env_file`/`--env-file` and `docker run --env-file` are strictly
    one ``VAR=VAL`` per line; multi-line values are unsupported even when quoted, so a
    value with embedded ``\\n``/``\\r`` (e.g. a PEM/OpenSSH private key) splatters across
    lines and every continuation re-parses as a bogus ``VAR`` — the loader fails with
    ``unexpected character ... in variable name``. Such secrets must be delivered via the
    ``*_FILE`` convention (services.common.env.get_secret reads ``KEY`` then ``KEY_FILE``)
    or Docker ``secrets:`` (mounted at ``/run/secrets/<name>``), never as an inline env var.
    Refs: https://docs.docker.com/reference/compose-file/services/#env_file ;
    https://docs.docker.com/compose/how-tos/use-secrets/
    """
    safe: Dict[str, str] = {}
    skipped: List[str] = []
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            skipped.append(key)
            continue
        safe[key] = value
    if skipped:
        print(
            f"WARNING: {relative}: skipped {len(skipped)} multi-line secret(s) "
            f"({', '.join(sorted(skipped))}) — multi-line values corrupt line-based "
            "env files. Deliver via the *_FILE convention (services.common.env.get_secret) "
            "or Docker secrets, not an inline env var.",
            file=sys.stderr,
        )
    return safe


def write_env_files(
    outputs: Mapping[str, Mapping[str, str]],
    *,
    merge: bool = False,
) -> None:
    header = "# Auto-generated by pmoves.tools.secrets_sync. Do not edit.\n"
    for relative, values in outputs.items():
        env_path = PROJECT_ROOT / relative
        env_path.parent.mkdir(parents=True, exist_ok=True)
        values = _drop_multiline(relative, values)

        if merge and env_path.exists():
            # Selective rotation: read existing, update only specified keys
            existing: Dict[str, str] = {}
            comments: List[str] = []
            for raw_line in env_path.read_text().splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    comments.append(raw_line)
                    continue
                if "=" in stripped:
                    k, v = stripped.split("=", 1)
                    # Defensive: ignore lines from an already-corrupt file (a prior
                    # multi-line value leaves continuation lines whose "key" is not a
                    # valid env identifier) so the corruption is not propagated.
                    if not k.isidentifier():
                        continue
                    existing[k] = v
            # Merge: new values override existing for specified keys
            existing.update(values)
            lines = comments + [""]
            for key in sorted(existing):
                lines.append(f"{key}={existing[key]}")
            env_path.write_text("\n".join(lines) + "\n")
        else:
            # Full regeneration (original behavior)
            lines_out = [header]
            for key in sorted(values):
                lines_out.append(f"{key}={values[key]}\n")
            env_path.write_text("".join(lines_out))


def report(outputs: Mapping[str, Mapping[str, str]]) -> str:
    rows = []
    for file_name, values in sorted(outputs.items()):
        rows.append(f"{file_name}: {len(values)} entries")
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed env files from CHIT secrets manifest.")
    parser.add_argument(
        "command",
        choices=("generate", "report"),
        help="generate env files or report planned outputs",
    )
    parser.add_argument(
        "--manifest",
        default="pmoves/chit/secrets_manifest.yaml",
        help="path to secrets manifest (default: pmoves/chit/secrets_manifest.yaml)",
    )
    parser.add_argument(
        "--cgp",
        default=None,
        help="override CGP file path from manifest (default: use manifest cgp_file)",
    )
    parser.add_argument(
        "--keys",
        nargs="*",
        default=None,
        help="Optional subset of secret labels to sync (selective rotation)",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        default=False,
        help="warn on missing required secrets instead of failing",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        default=False,
        help="merge into existing tier files instead of overwriting",
    )
    args = parser.parse_args(argv)

    manifest_path = (REPO_ROOT / args.manifest).resolve()
    cgp_path, entries = load_manifest(manifest_path)

    # Allow CLI override of CGP path
    if args.cgp:
        cgp_path = Path(args.cgp).expanduser().resolve()

    secrets = decode_secret_map(load_cgp(cgp_path))

    # Filter entries if --keys is specified (selective rotation)
    if args.keys:
        key_set = set(args.keys)
        entries = [e for e in entries if e.label in key_set]

    outputs, missing = build_outputs(secrets, entries, strict=False)
    if missing:
        joined = ", ".join(sorted(missing))
        if args.allow_missing:
            print(f"WARNING: Missing secrets (non-fatal): {joined}", file=sys.stderr)
        else:
            print(f"ERROR: Missing required secrets: {joined}", file=sys.stderr)
            return 1

    if args.command == "report":
        print(report(outputs))
        return 0

    write_env_files(outputs, merge=args.merge or bool(args.keys))
    print(report(outputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
