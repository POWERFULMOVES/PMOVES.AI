#!/usr/bin/env python3
"""Audit PMOVES tooling overlays against submodule scripts and workflows."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "pmoves/configs/tooling_script_audit_manifest.json"
DEFAULT_OUTPUT = REPO_ROOT / "pmoves/docs/AGENTS/TOOLING_SCRIPT_AUDIT.md"
DEFAULT_ENV_EXAMPLE = REPO_ROOT / "pmoves/env.shared.example"

TARGET_RE = re.compile(r"^([A-Za-z0-9_./-]+)\s*:(?![=])")
TOKEN_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class Finding:
    level: str
    code: str
    message: str
    path: str | None = None


@dataclass
class ScriptRecord:
    module: str
    path: Path
    rel_path: str
    keywords: set[str]
    tokens: set[str]


@dataclass
class OverlapRow:
    keyword: str
    score: float
    pmoves_path: str
    submodule: str
    submodule_path: str
    shared_tokens: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit PMOVES scripts/tools for overlap with submodule tooling and "
            "validate canonical can-opener workflows."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Policy manifest path (default: {DEFAULT_MANIFEST.relative_to(REPO_ROOT).as_posix()})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Markdown report path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT).as_posix()})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures.",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_manifest(path: Path) -> dict:
    raw = json.loads(read_text(path))
    if not isinstance(raw, dict):
        raise SystemExit(f"Manifest must be a JSON object: {path}")
    return raw


def parse_gitmodules(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []

    modules: list[tuple[str, str]] = []
    name = ""
    module_path = ""
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line:
            continue
        section = re.match(r'\[submodule "(.+)"\]', line)
        if section:
            if name and module_path:
                modules.append((name, module_path))
            name = section.group(1)
            module_path = ""
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key == "path":
            module_path = value
    if name and module_path:
        modules.append((name, module_path))
    return modules


def normalize_tokens(path: Path) -> set[str]:
    parts = [path.stem.lower(), *[part.lower() for part in path.parts[-3:]]]
    raw = "_".join(parts)
    tokens = {token for token in TOKEN_RE.split(raw) if len(token) > 1}
    return tokens


def keyword_hits(path: Path, keywords: Iterable[str]) -> set[str]:
    lower = path.as_posix().lower()
    return {kw for kw in keywords if kw in lower}


def parse_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _ = line.split("=", 1)
        keys.add(key.strip())
    return keys


def parse_make_targets(makefiles: Iterable[Path]) -> set[str]:
    targets: set[str] = set()
    for path in makefiles:
        if not path.exists():
            continue
        for raw in read_text(path).splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("."):
                continue
            match = TARGET_RE.match(line)
            if not match:
                continue
            target = match.group(1)
            if target in {"ifeq", "ifneq", "ifdef", "ifndef", "else", "endif"}:
                continue
            targets.add(target)
    return targets


def collect_root_records(
    *,
    scan_dirs: list[str],
    allowed_exts: set[str],
    keywords: list[str],
) -> tuple[list[ScriptRecord], list[ScriptRecord]]:
    all_records: list[ScriptRecord] = []
    keyword_records: list[ScriptRecord] = []
    for raw_dir in scan_dirs:
        root = REPO_ROOT / raw_dir
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed_exts:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            matched = keyword_hits(Path(rel), keywords)
            record = ScriptRecord(
                module="pmoves",
                path=path,
                rel_path=rel,
                keywords=matched,
                tokens=normalize_tokens(path.relative_to(REPO_ROOT)),
            )
            all_records.append(record)
            if matched:
                keyword_records.append(record)
    return all_records, keyword_records


def should_scan_submodule_path(
    rel_path: str,
    *,
    hints: tuple[str, ...],
    skip_tokens: tuple[str, ...],
    keywords: list[str],
) -> bool:
    lower = rel_path.lower()
    wrapped = f"/{lower.strip('/')}/"
    if any(token in wrapped for token in skip_tokens):
        return False
    if any(hint in lower for hint in hints):
        return True
    filename = Path(rel_path).name.lower()
    if any(kw in filename for kw in keywords):
        return len(Path(rel_path).parts) <= 3
    return False


def collect_submodule_records(
    *,
    modules: list[tuple[str, str]],
    allowed_exts: set[str],
    hints: tuple[str, ...],
    skip_tokens: tuple[str, ...],
    keywords: list[str],
    findings: list[Finding],
) -> list[ScriptRecord]:
    records: list[ScriptRecord] = []
    for _, module_path in modules:
        root = REPO_ROOT / module_path
        if not root.exists():
            findings.append(
                Finding(
                    "WARN",
                    "MISSING_SUBMODULE_PATH",
                    "Submodule path is not present locally (run submodule sync/init if needed).",
                    module_path,
                )
            )
            continue
        scanned = 0
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed_exts:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            rel_from_module = path.relative_to(root).as_posix()
            if not should_scan_submodule_path(
                rel_from_module,
                hints=hints,
                skip_tokens=skip_tokens,
                keywords=keywords,
            ):
                continue
            matched = keyword_hits(Path(rel_from_module), keywords)
            if not matched:
                continue
            records.append(
                ScriptRecord(
                    module=module_path,
                    path=path,
                    rel_path=rel,
                    keywords=matched,
                    tokens=normalize_tokens(path.relative_to(REPO_ROOT)),
                )
            )
            scanned += 1
            if scanned >= 600:
                findings.append(
                    Finding(
                        "WARN",
                        "SUBMODULE_SCAN_CAPPED",
                        "Scan capped at 600 matched files for this submodule.",
                        module_path,
                    )
                )
                break
    return records


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    shared = a & b
    union = a | b
    if not union:
        return 0.0
    return len(shared) / len(union)


def build_overlap_rows(
    *,
    root_keyword_records: list[ScriptRecord],
    submodule_records: list[ScriptRecord],
    keywords: list[str],
    max_rows_per_keyword: int,
) -> list[OverlapRow]:
    rows: list[OverlapRow] = []
    for keyword in keywords:
        root_hits = [item for item in root_keyword_records if keyword in item.keywords]
        sub_hits = [item for item in submodule_records if keyword in item.keywords]
        if not root_hits or not sub_hits:
            continue

        candidates: list[OverlapRow] = []
        for root_item in root_hits:
            for sub_item in sub_hits:
                shared = sorted(root_item.tokens & sub_item.tokens)
                score = jaccard(root_item.tokens, sub_item.tokens)
                if not shared and score < 0.20:
                    continue
                candidates.append(
                    OverlapRow(
                        keyword=keyword,
                        score=score,
                        pmoves_path=root_item.rel_path,
                        submodule=sub_item.module,
                        submodule_path=sub_item.rel_path,
                        shared_tokens=shared[:5],
                    )
                )

        deduped: dict[tuple[str, str], OverlapRow] = {}
        for row in sorted(candidates, key=lambda item: item.score, reverse=True):
            key = (row.pmoves_path, row.submodule_path)
            if key in deduped:
                continue
            deduped[key] = row
            if len(deduped) >= max_rows_per_keyword:
                break
        rows.extend(deduped.values())
    return rows


def check_duplicate_stems(
    *,
    root_records: list[ScriptRecord],
    allowlist: set[str],
) -> list[Finding]:
    grouped: dict[str, list[ScriptRecord]] = {}
    for record in root_records:
        stem = TOKEN_RE.sub("_", record.path.stem.lower()).strip("_")
        grouped.setdefault(stem, []).append(record)

    findings: list[Finding] = []
    for stem, records in sorted(grouped.items()):
        if stem in allowlist:
            continue
        if len(records) <= 1:
            continue
        if stem == "init" and all(record.path.name == "__init__.py" for record in records):
            continue
        suffixes = {record.path.suffix.lower() for record in records}
        if len(records) == 2 and suffixes == {".sh", ".ps1"}:
            continue
        paths = ", ".join(record.rel_path for record in records)
        findings.append(
            Finding(
                "WARN",
                "DUPLICATE_SCRIPT_STEM",
                f"Potential duplicate/ad-hoc tooling stem '{stem}' found in: {paths}",
            )
        )
    return findings


def check_cross_platform_pairs(
    *,
    pairs: list[dict],
) -> list[Finding]:
    findings: list[Finding] = []
    for pair in pairs:
        name = str(pair.get("name", "unnamed"))
        linux_path = str(pair.get("linux", "")).strip()
        windows_path = str(pair.get("windows", "")).strip()
        if not linux_path or not windows_path:
            findings.append(
                Finding(
                    "ERROR",
                    "PAIR_SPEC_INVALID",
                    f"Cross-platform pair '{name}' is missing linux/windows fields in manifest.",
                )
            )
            continue
        linux_exists = (REPO_ROOT / linux_path).exists()
        windows_exists = (REPO_ROOT / windows_path).exists()
        if not linux_exists or not windows_exists:
            missing = []
            if not linux_exists:
                missing.append(linux_path)
            if not windows_exists:
                missing.append(windows_path)
            findings.append(
                Finding(
                    "ERROR",
                    "PAIR_MISSING_FILE",
                    f"Cross-platform pair '{name}' is missing: {', '.join(missing)}",
                )
            )
    return findings


def check_canonical_make_targets(required: list[str], available: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for target in required:
        if target not in available:
            findings.append(
                Finding(
                    "ERROR",
                    "MISSING_CAN_OPENER",
                    "Canonical can-opener make target is missing.",
                    target,
                )
            )
    return findings


def check_canonical_files(required: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for rel_path in required:
        if not (REPO_ROOT / rel_path).exists():
            findings.append(
                Finding(
                    "ERROR",
                    "MISSING_CAN_OPENER_FILE",
                    "Canonical workflow file is missing.",
                    rel_path,
                )
            )
    return findings


def check_seeded_defaults(required: list[str], env_keys: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for key in required:
        if key not in env_keys:
            findings.append(
                Finding(
                    "ERROR",
                    "MISSING_SEEDED_DEFAULT",
                    "Seeded branded default key is missing from pmoves/env.shared.example.",
                    key,
                )
            )
    return findings


def check_orphan_pmoves_dirs(
    *,
    modules: list[tuple[str, str]],
    known_non_submodule_dirs: set[str],
) -> list[Finding]:
    module_top_dirs = {Path(module_path).parts[0] for _, module_path in modules if Path(module_path).parts}
    findings: list[Finding] = []
    for path in REPO_ROOT.iterdir():
        if not path.is_dir():
            continue
        name = path.name
        lower = name.lower()
        if not (lower.startswith("pmoves") or lower.startswith("pmoves-")):
            continue
        if name in module_top_dirs or name in known_non_submodule_dirs:
            continue
        findings.append(
            Finding(
                "WARN",
                "ORPHAN_PMOVES_DIR",
                "Directory looks like a PMOVES module but is not mapped in .gitmodules.",
                name,
            )
        )
    return findings


def check_workflow_routes(
    *,
    workflow_routes: dict,
    available_targets: set[str],
    overlap_rows: list[OverlapRow],
) -> list[Finding]:
    keywords_with_overlap = {row.keyword for row in overlap_rows}
    findings: list[Finding] = []
    for keyword in sorted(keywords_with_overlap):
        routes = workflow_routes.get(keyword, [])
        if not routes:
            findings.append(
                Finding(
                    "WARN",
                    "MISSING_WORKFLOW_ROUTE",
                    f"No canonical workflow route defined for keyword '{keyword}'.",
                )
            )
            continue
        for target in routes:
            if target not in available_targets:
                findings.append(
                    Finding(
                        "ERROR",
                        "WORKFLOW_ROUTE_TARGET_MISSING",
                        f"Workflow route target '{target}' for keyword '{keyword}' is missing.",
                    )
                )
    return findings


def render_markdown(
    *,
    root_records: list[ScriptRecord],
    root_keyword_records: list[ScriptRecord],
    submodule_records: list[ScriptRecord],
    overlap_rows: list[OverlapRow],
    findings: list[Finding],
    workflow_routes: dict,
) -> str:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    error_count = sum(1 for finding in findings if finding.level == "ERROR")
    warn_count = sum(1 for finding in findings if finding.level == "WARN")
    keywords_touched = sorted({row.keyword for row in overlap_rows})

    lines: list[str] = []
    lines.append("# PMOVES Tooling Overlay Audit")
    lines.append(f"_Generated: {today}_")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- PMOVES scripts/tools scanned: **{len(root_records)}**")
    lines.append(f"- PMOVES auth/user/login-focused entries: **{len(root_keyword_records)}**")
    lines.append(f"- Submodule keyword-matched scripts/tools: **{len(submodule_records)}**")
    lines.append(f"- Potential overlap rows: **{len(overlap_rows)}**")
    lines.append(f"- Keywords with overlap: **{', '.join(keywords_touched) if keywords_touched else 'none'}**")
    lines.append(f"- Findings: **{error_count} error(s)**, **{warn_count} warning(s)**")
    lines.append("")
    lines.append("## Canonical Workflow Routes")
    lines.append("| Keyword | PMOVES Can-Openers |")
    lines.append("| --- | --- |")
    for keyword, targets in sorted(workflow_routes.items()):
        route = ", ".join(f"`{item}`" for item in targets) if targets else "-"
        lines.append(f"| `{keyword}` | {route} |")
    lines.append("")

    lines.append("## Overlap Candidates")
    if overlap_rows:
        lines.append("| Keyword | Score | PMOVES Script/Tool | Submodule | Submodule Script/Tool | Shared Tokens |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in sorted(overlap_rows, key=lambda item: (item.keyword, -item.score, item.pmoves_path)):
            shared = ", ".join(row.shared_tokens) if row.shared_tokens else "-"
            lines.append(
                f"| `{row.keyword}` | {row.score:.2f} | "
                f"`{row.pmoves_path}` | `{row.submodule}` | `{row.submodule_path}` | {shared} |"
            )
    else:
        lines.append("- No overlap candidates were detected for configured keywords.")
    lines.append("")

    lines.append("## Findings")
    if findings:
        for finding in findings:
            if finding.path:
                lines.append(
                    f"- [{finding.level}] `{finding.code}` `{finding.path}`: {finding.message}"
                )
            else:
                lines.append(f"- [{finding.level}] `{finding.code}`: {finding.message}")
    else:
        lines.append("- No findings.")
    lines.append("")

    lines.append("## Operator Guidance")
    lines.append(
        "1. Prefer PMOVES can-openers for auth/user/login flows before adding new submodule-specific wrappers."
    )
    lines.append(
        "2. Keep seeded defaults in `pmoves/env.shared.example` so new users can onboard without manual workaround edits."
    )
    lines.append(
        "3. Preserve submodule scripts as troubleshooting fallback, but route primary workflows through PMOVES targets."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)

    findings: list[Finding] = []

    keywords = [str(item).lower() for item in manifest.get("keywords", [])]
    allowed_exts = {str(item).lower() for item in manifest.get("allowed_extensions", [])}
    scan_dirs = [str(item) for item in manifest.get("root_scan_dirs", [])]
    hint_tuple = tuple(str(item).lower() for item in manifest.get("submodule_scan_dir_hints", []))
    skip_tokens = tuple(str(item).lower() for item in manifest.get("submodule_skip_path_tokens", []))

    modules = parse_gitmodules(REPO_ROOT / ".gitmodules")
    root_records, root_keyword_records = collect_root_records(
        scan_dirs=scan_dirs,
        allowed_exts=allowed_exts,
        keywords=keywords,
    )
    submodule_records = collect_submodule_records(
        modules=modules,
        allowed_exts=allowed_exts,
        hints=hint_tuple,
        skip_tokens=skip_tokens,
        keywords=keywords,
        findings=findings,
    )

    max_rows = int(manifest.get("max_overlap_rows_per_keyword", 20))
    overlap_rows = build_overlap_rows(
        root_keyword_records=root_keyword_records,
        submodule_records=submodule_records,
        keywords=keywords,
        max_rows_per_keyword=max_rows,
    )

    makefiles = [REPO_ROOT / "pmoves/Makefile", *(REPO_ROOT / "pmoves/mk").glob("*.mk")]
    make_targets = parse_make_targets(makefiles)
    env_keys = parse_env_keys(DEFAULT_ENV_EXAMPLE)

    findings.extend(check_cross_platform_pairs(pairs=list(manifest.get("cross_platform_pairs", []))))
    findings.extend(
        check_canonical_make_targets(
            required=list(manifest.get("canonical_make_targets", [])),
            available=make_targets,
        )
    )
    findings.extend(check_canonical_files(required=list(manifest.get("canonical_files", []))))
    findings.extend(
        check_seeded_defaults(
            required=list(manifest.get("seeded_default_env_keys", [])),
            env_keys=env_keys,
        )
    )
    findings.extend(
        check_duplicate_stems(
            root_records=root_records,
            allowlist={str(item) for item in manifest.get("duplicate_stem_allowlist", [])},
        )
    )
    findings.extend(
        check_orphan_pmoves_dirs(
            modules=modules,
            known_non_submodule_dirs={str(item) for item in manifest.get("known_non_submodule_dirs", [])},
        )
    )
    findings.extend(
        check_workflow_routes(
            workflow_routes=dict(manifest.get("workflow_routes", {})),
            available_targets=make_targets,
            overlap_rows=overlap_rows,
        )
    )

    report = render_markdown(
        root_records=root_records,
        root_keyword_records=root_keyword_records,
        submodule_records=submodule_records,
        overlap_rows=overlap_rows,
        findings=findings,
        workflow_routes=dict(manifest.get("workflow_routes", {})),
    )
    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report + "\n", encoding="utf-8")

    error_count = sum(1 for finding in findings if finding.level == "ERROR")
    warn_count = sum(1 for finding in findings if finding.level == "WARN")
    print(f"Wrote {output_path}")
    print(f"Summary: errors={error_count} warnings={warn_count} overlap_rows={len(overlap_rows)}")

    if error_count > 0:
        return 1
    if args.strict and warn_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
