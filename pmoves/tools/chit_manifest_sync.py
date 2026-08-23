#!/usr/bin/env python3
"""Sync the v1 CHIT secrets manifest from the richer v2 manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest_v2.yaml"
DEFAULT_DEST = REPO_ROOT / "pmoves" / "chit" / "secrets_manifest.yaml"
DEFAULT_CGP_FILE = "pmoves/data/chit/env.cgp.json"

# Keep canonical labels stable even when env bundles use upstream naming.
CANONICAL_SOURCE_ALIASES: Dict[str, Tuple[str, ...]] = {
    "SUPABASE_SERVICE_KEY": ("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY"),
    "SUPABASE_REALTIME_KEY": ("SUPABASE_ANON_KEY", "ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    "SUPABASE_REALTIME_SECRET": ("SUPABASE_JWT_SECRET", "JWT_SECRET"),
    "SERVICE_PASSWORD_POSTGRES": ("POSTGRES_PASSWORD", "SUPABASE_DB_PASSWORD"),
    "SERVICE_PASSWORD_ADMIN": ("POSTGRES_PASSWORD", "SUPABASE_DB_PASSWORD"),
    "SERVICE_USER_ADMIN": ("POSTGRES_USER", "SUPABASE_DB_USER"),
    "GITHUB_PAT": ("GH_PAT_PUBLISH",),
    "TENSORZERO_GATEWAY_URL": ("TENSORZERO_BASE_URL",),
    "TENSORZERO_PG_DB": ("TENSORZERO_CLICKHOUSE_DB",),
    "TENSORZERO_PG_USER": ("TENSORZERO_CLICKHOUSE_USER",),
}

# Some v2 labels are optional for local/single-node onboarding and should not warn by default.
REQUIRED_OVERRIDES: Dict[str, bool] = {
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": False,
    "TENSORZERO_GATEWAY_URL": False,
    "TENSORZERO_PG_DB": False,
    "TENSORZERO_PG_USER": False,
    "GITHUB_PAT": False,
}


def _normalize_labels(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _resolve_path(path_value: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    cwd_candidate = path_value.resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    repo_candidate = (REPO_ROOT / path_value).resolve()
    return repo_candidate


def _load_yaml(path: Path) -> Mapping[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path} must contain a mapping root")
    return raw


def _build_entry_index(entries: Iterable[Any]) -> Dict[str, Mapping[str, Any]]:
    out: Dict[str, Mapping[str, Any]] = {}
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        entry_id = item.get("id")
        if isinstance(entry_id, str):
            out[entry_id] = item
    return out


def _extract_aliases(source: Mapping[str, Any] | None) -> List[str]:
    if not isinstance(source, Mapping):
        return []
    aliases_raw = source.get("aliases", [])
    if not isinstance(aliases_raw, list):
        return []
    values = [item for item in aliases_raw if isinstance(item, str)]
    return _normalize_labels(values)


def _extract_file_targets(targets: Iterable[Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for target in targets:
        if not isinstance(target, Mapping):
            continue
        file_name = target.get("file")
        key = target.get("key")
        if isinstance(file_name, str) and file_name and isinstance(key, str) and key:
            out.append({"file": file_name, "key": key})
    return out


def _build_v1_entry(
    source_entry: Mapping[str, Any],
    existing_entry: Mapping[str, Any] | None = None,
) -> Dict[str, Any] | None:
    entry_id = source_entry.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("v2 entry missing id")

    source = source_entry.get("source")
    if not isinstance(source, Mapping):
        raise ValueError(f"v2 entry {entry_id} has invalid source")
    if source.get("type") != "cgp":
        # v1 sync target is intentionally CHIT (cgp) only.
        return None

    label = source.get("label")
    if not isinstance(label, str) or not label:
        raise ValueError(f"v2 entry {entry_id} missing source.label")

    existing_aliases = _extract_aliases(
        existing_entry.get("source") if isinstance(existing_entry, Mapping) else None
    )
    source_aliases = _extract_aliases(source)
    canonical_aliases = list(CANONICAL_SOURCE_ALIASES.get(label, ()))
    aliases = _normalize_labels([*existing_aliases, *source_aliases, *canonical_aliases])

    targets_raw = source_entry.get("targets", [])
    if not isinstance(targets_raw, list):
        raise ValueError(f"v2 entry {entry_id} targets must be a list")
    targets = _extract_file_targets(targets_raw)
    if not targets:
        raise ValueError(f"v2 entry {entry_id} has no file/key targets for v1 manifest")

    source_out: Dict[str, Any] = {"type": "cgp", "label": label}
    if aliases:
        source_out["aliases"] = aliases

    v1: Dict[str, Any] = {
        "id": entry_id,
        "source": source_out,
        "targets": targets,
        "required": REQUIRED_OVERRIDES.get(label, bool(source_entry.get("required", True))),
    }
    # Constraints must survive the derivation, not just the v2 file.
    #
    # `secrets-funnel-sync` derives the v1 manifest from v2 and then hands the
    # DERIVED file to secrets_sync.py (codex.mk:114-115). So anything this
    # function does not copy is invisible to load_manifest() on the canonical
    # path -- a constraint declared in v2 would be enforced by nothing, while
    # both files looked correct. min_length was added to v2 for SECRET_KEY_BASE
    # and would have been dropped exactly here.
    min_length = source_entry.get("min_length")
    if isinstance(min_length, int) and not isinstance(min_length, bool) and min_length > 0:
        v1["min_length"] = min_length
    return v1


def build_v1_manifest(
    source_manifest: Mapping[str, Any],
    existing_manifest: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    entries_raw = source_manifest.get("entries")
    if not isinstance(entries_raw, list):
        raise ValueError("v2 manifest entries must be a list")

    existing_entries = _build_entry_index(
        existing_manifest.get("entries", []) if isinstance(existing_manifest, Mapping) else []
    )
    out_entries: List[Dict[str, Any]] = []
    skipped_non_cgp = 0
    for entry in entries_raw:
        if not isinstance(entry, Mapping):
            continue
        entry_id = entry.get("id")
        existing_entry = existing_entries.get(entry_id) if isinstance(entry_id, str) else None
        next_entry = _build_v1_entry(entry, existing_entry)
        if next_entry is None:
            skipped_non_cgp += 1
            continue
        out_entries.append(next_entry)

    cgp_file = source_manifest.get("cgp_file")
    if not isinstance(cgp_file, str) or not cgp_file.strip():
        cgp_file = (
            existing_manifest.get("cgp_file")
            if isinstance(existing_manifest, Mapping)
            else DEFAULT_CGP_FILE
        )
    if not isinstance(cgp_file, str) or not cgp_file.strip():
        cgp_file = DEFAULT_CGP_FILE

    out: Dict[str, Any] = {"version": 1, "cgp_file": cgp_file, "entries": out_entries}

    if isinstance(existing_manifest, Mapping):
        defaults = existing_manifest.get("defaults")
        if isinstance(defaults, Mapping):
            out["defaults"] = defaults

    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Path to v2 manifest.")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Path to v1 manifest.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; fail with exit 1 if the destination is out of sync.",
    )
    args = parser.parse_args(argv)

    source_path = _resolve_path(args.source.expanduser())
    dest_path = _resolve_path(args.dest.expanduser())
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    source_manifest = _load_yaml(source_path)
    existing_manifest: Mapping[str, Any] | None = None
    if dest_path.exists():
        existing_manifest = _load_yaml(dest_path)

    next_manifest = build_v1_manifest(source_manifest, existing_manifest)
    next_text = yaml.safe_dump(next_manifest, sort_keys=False)
    current_text = dest_path.read_text(encoding="utf-8") if dest_path.exists() else ""

    if args.check:
        if current_text != next_text:
            print(f"OUT-OF-SYNC: {dest_path} differs from v2 source {source_path}")
            return 1
        print(f"OK: {dest_path} is in sync with {source_path}")
        return 0

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(next_text, encoding="utf-8")
    print(f"Synced {dest_path} from {source_path} ({len(next_manifest['entries'])} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
