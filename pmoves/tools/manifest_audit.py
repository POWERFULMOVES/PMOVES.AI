#!/usr/bin/env python3
"""Audit provisioning manifests for unsupported hardware targets."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("PyYAML is required to run manifest_audit (pip install pyyaml)") from exc

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = REPO_ROOT / "CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/inventory/nodes.yaml"
DEFAULT_SUPABASE_EXPORT = REPO_ROOT / "supabase/deployment_records.json"

SUPPORTED_ARCHES = {"x86_64", "aarch64"}
ARCH_ALIASES = {"amd64": "x86_64", "arm64": "aarch64"}


@dataclass
class NodeRecord:
    source: str
    name: str
    arch: str | None
    role: str | None = None
    status: str | None = None
    replacement_options: Sequence[str] | None = None

    @property
    def normalized_arch(self) -> str | None:
        if self.arch is None:
            return None
        value = self.arch.strip().lower()
        if not value:
            return None
        return ARCH_ALIASES.get(value, value)


def _load_inventory(path: Path) -> list[NodeRecord]:
    if not path.exists():
        return []

    raw = yaml.safe_load(path.read_text())
    if raw is None:
        return []

    if isinstance(raw, Mapping):
        candidates: Iterable[Mapping[str, object]] = raw.get("nodes", [])  # type: ignore[index]
    elif isinstance(raw, list):
        candidates = raw  # type: ignore[assignment]
    else:
        raise ValueError(f"Unsupported inventory format in {path}")

    records: list[NodeRecord] = []
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        records.append(
            NodeRecord(
                source="inventory",
                name=str(item.get("name", "<unnamed>")),
                arch=(str(item["arch"]) if item.get("arch") is not None else None),
                role=(str(item["role"]) if item.get("role") is not None else None),
                status=(str(item["status"]) if item.get("status") is not None else None),
                replacement_options=tuple(str(v) for v in item.get("replacement_options", []) if v),
            )
        )
    return records


def _load_supabase(path: Path) -> list[NodeRecord]:
    if not path.exists():
        return []

    data = json.loads(path.read_text())
    if isinstance(data, Mapping):
        items = data.get("nodes") or data.get("records") or []
    else:
        items = data

    records: list[NodeRecord] = []
    if not isinstance(items, Iterable):
        return records

    for item in items:
        if not isinstance(item, Mapping):
            continue
        records.append(
            NodeRecord(
                source="supabase",
                name=str(item.get("name", "<unnamed>")),
                arch=(str(item["arch"]) if item.get("arch") is not None else None),
                role=(str(item["role"]) if item.get("role") is not None else None),
                status=(str(item.get("status")) if item.get("status") is not None else None),
                replacement_options=tuple(str(v) for v in item.get("replacement_options", []) if v),
            )
        )
    return records


def _summarize(records: Sequence[NodeRecord]) -> dict[str, int]:
    summary: dict[str, int] = {"total": len(records), "supported": 0, "unsupported": 0, "unknown": 0}
    for record in records:
        arch = record.normalized_arch
        if arch is None:
            summary["unknown"] += 1
        elif arch in SUPPORTED_ARCHES:
            summary["supported"] += 1
        else:
            summary["unsupported"] += 1
    return summary


def audit(records: Sequence[NodeRecord]) -> list[str]:
    issues: list[str] = []
    for record in records:
        arch = record.normalized_arch
        if arch is None:
            issues.append(
                f"{record.source}:{record.name}: missing architecture metadata; unable to verify support"
            )
            continue
        if arch not in SUPPORTED_ARCHES:
            replacements = ""
            if record.replacement_options:
                replacements = f" | replacements: {', '.join(record.replacement_options)}"
            role = f" role={record.role}" if record.role else ""
            status = f" status={record.status}" if record.status else ""
            issues.append(
                f"{record.source}:{record.name}: arch={record.arch}{role}{status}{replacements}"
            )
    return issues


def format_summary(label: str, summary: Mapping[str, int]) -> str:
    return (
        f"{label}: total={summary['total']} supported={summary['supported']} "
        f"unsupported={summary['unsupported']} unknown={summary['unknown']}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit provisioning manifests for unsupported hardware.")
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help="Path to provisioning inventory YAML (default: inventory/nodes.yaml)",
    )
    parser.add_argument(
        "--supabase-export",
        type=Path,
        default=DEFAULT_SUPABASE_EXPORT,
        help="Optional Supabase deployment export (JSON).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero even when only unknown architectures are encountered.",
    )
    args = parser.parse_args(argv)

    inventory_records = _load_inventory(args.inventory)
    supabase_records = _load_supabase(args.supabase_export)
    all_records = [*inventory_records, *supabase_records]

    if not all_records:
        print("No inventory or deployment records found; nothing to audit.")
        return 0

    if inventory_records:
        print(format_summary("inventory", _summarize(inventory_records)))
    else:
        print("inventory: no records found")

    if supabase_records:
        print(format_summary("supabase", _summarize(supabase_records)))

    issues = audit(all_records)

    if issues:
        print("\nUnsupported hardware targets detected:")
        for entry in issues:
            print(f"  - {entry}")
        return 1

    unknown_only = any(record.normalized_arch is None for record in all_records)
    if unknown_only:
        message = "No unsupported hardware found, but some records lacked architecture metadata."
        print(message)
        return 1 if args.strict else 0

    print("No unsupported hardware targets found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
