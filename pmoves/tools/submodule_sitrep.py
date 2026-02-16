#!/usr/bin/env python3
"""Generate a production-focused submodule alignment SITREP."""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"


@dataclass
class SubmoduleStatus:
    prefix: str
    commit: str
    path: str
    detail: str


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_gitmodules() -> list[dict[str, str]]:
    cfg = configparser.ConfigParser()
    cfg.read(GITMODULES, encoding="utf-8")
    rows: list[dict[str, str]] = []
    for section in cfg.sections():
        rows.append(
            {
                "section": section,
                "path": cfg.get(section, "path", fallback=""),
                "url": cfg.get(section, "url", fallback=""),
                "branch": cfg.get(section, "branch", fallback=""),
            }
        )
    return rows


def parse_submodule_status(output: str) -> list[SubmoduleStatus]:
    rows: list[SubmoduleStatus] = []
    for raw in output.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        prefix = line[0]
        payload = line[1:].strip()
        parts = payload.split(maxsplit=2)
        if len(parts) < 2:
            continue
        commit, path = parts[0], parts[1]
        detail = parts[2] if len(parts) > 2 else ""
        rows.append(SubmoduleStatus(prefix=prefix, commit=commit, path=path, detail=detail))
    return rows


def find_duplicate_urls(modules: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    by_url: dict[str, list[dict[str, str]]] = defaultdict(list)
    for module in modules:
        by_url[module["url"]].append(module)
    return {url: rows for url, rows in by_url.items() if url and len(rows) > 1}


def discover_files(patterns: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(REPO_ROOT.glob(pattern))
    unique = sorted({path.resolve() for path in files if path.is_file()})
    return unique


def scan_patterns(
    files: Iterable[Path], terms: Iterable[str], *, ignore: Iterable[str] | None = None
) -> dict[str, list[str]]:
    ignored = set(ignore or [])
    term_hits: dict[str, list[str]] = {term: [] for term in terms}
    for file_path in files:
        rel = file_path.relative_to(REPO_ROOT).as_posix()
        if rel in ignored:
            continue
        if fnmatch.fnmatch(rel, "*/.git/*"):
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for term in terms:
            if term in text:
                term_hits[term].append(rel)
    return {term: sorted(set(paths)) for term, paths in term_hits.items() if paths}


def collect_dirty_submodules(modules: list[dict[str, str]]) -> dict[str, int]:
    """Return submodule paths that have local changes with entry counts."""
    dirty: dict[str, int] = {}
    for module in modules:
        path = module.get("path", "").strip()
        if not path:
            continue
        submodule_root = REPO_ROOT / path
        if not submodule_root.exists():
            continue
        proc = subprocess.run(
            ["git", "-C", str(submodule_root), "status", "--porcelain"],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            continue
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if lines:
            dirty[path] = len(lines)
    return dict(sorted(dirty.items()))


def markdown_list(items: Iterable[str]) -> str:
    rows = list(items)
    if not rows:
        return "- _none_"
    return "\n".join(f"- `{item}`" for item in rows)


def format_report(
    modules: list[dict[str, str]],
    status_rows: list[SubmoduleStatus],
    recursive_exit: int,
    recursive_stderr: str,
    duplicate_urls: dict[str, list[dict[str, str]]],
    legacy_hits: dict[str, list[str]],
    alias_hits: dict[str, list[str]],
    docs_legacy_hits: dict[str, list[str]],
    dirty_submodules: dict[str, int],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    uninitialized = sorted(row.path for row in status_rows if row.prefix == "-")
    drifted = sorted(row.path for row in status_rows if row.prefix == "+")
    conflicts = sorted(row.path for row in status_rows if row.prefix.upper() == "U")

    recursive_error = recursive_stderr.strip() if recursive_stderr.strip() else "_none_"

    dup_sections: list[str] = []
    for url, rows in sorted(duplicate_urls.items()):
        dup_sections.append(f"- `{url}`")
        for row in sorted(rows, key=lambda r: r["path"]):
            dup_sections.append(f"  - `{row['path']}` (branch `{row['branch'] or 'n/a'}`)")
    duplicate_block = "\n".join(dup_sections) if dup_sections else "- _none_"

    legacy_block = []
    for term, files in sorted(legacy_hits.items()):
        legacy_block.append(f"- `{term}`")
        for file in files:
            legacy_block.append(f"  - `{file}`")
    legacy_text = "\n".join(legacy_block) if legacy_block else "- _none_"

    alias_block = []
    for term, files in sorted(alias_hits.items()):
        alias_block.append(f"- `{term}`")
        for file in files:
            alias_block.append(f"  - `{file}`")
    alias_text = "\n".join(alias_block) if alias_block else "- _none_"

    docs_block = []
    for term, files in sorted(docs_legacy_hits.items()):
        docs_block.append(f"- `{term}`")
        for file in files:
            docs_block.append(f"  - `{file}`")
    docs_text = "\n".join(docs_block) if docs_block else "- _none_"

    if dirty_submodules:
        dirty_rows = "\n".join(
            f"- `{path}` ({count} changed entries)"
            for path, count in dirty_submodules.items()
        )
    else:
        dirty_rows = "- _none_"

    return f"""# Submodule Alignment SITREP
_Generated: {now}_

## Summary
- Declared submodules in `.gitmodules`: **{len(modules)}**
- Uninitialized submodules (`git submodule status` prefix `-`): **{len(uninitialized)}**
- Drifted submodules (`+`): **{len(drifted)}**
- Conflict submodules (`U`): **{len(conflicts)}**
- Recursive status exit code: **{recursive_exit}**

## Critical Blockers
- Recursive traversal currently fails: **{recursive_exit != 0}**
- Recursive error:
  - `{recursive_error}`

## Duplicate URL Groups (Canonical-vs-Alias Paths)
{duplicate_block}

## Initialization State
### Uninitialized
{markdown_list(uninitialized)}

### Drifted
{markdown_list(drifted)}

### Conflicts
{markdown_list(conflicts)}

## Dirty Worktrees (Local Changes)
{dirty_rows}

## Legacy Name Hits (Action Required)
{legacy_text}

## Alias/Compatibility Path Hits (Review Required)
{alias_text}

## Documentation Legacy Hits (Archive/Update)
{docs_text}

## Production Decision Guidance
1. Keep compatibility path mappings active in `.gitmodules` until all legacy gitlinks are removed from index and no runtime file depends on alias paths.
2. Keep recursive submodule checks enabled and treat any new unmapped nested gitlink as a release blocker.
3. Split cleanup into targeted PR waves:
   - Wave A: metadata integrity + deterministic submodule checks.
   - Wave B: canonical path migration (alias removal with scripted updates).
   - Wave C: docs/context regeneration and archived legacy references.
4. For production branch protection, gate on non-recursive integrity plus recursive metadata integrity; allow optional uninitialized submodules only where explicitly documented.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "pmoves/docs/SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md"),
        help="Path to output markdown report.",
    )
    args = parser.parse_args()

    modules = parse_gitmodules()
    status = run_git(["submodule", "status"])
    status_rows = parse_submodule_status(status.stdout)

    recursive = run_git(["submodule", "status", "--recursive"])
    duplicate_urls = find_duplicate_urls(modules)

    scan_file_patterns = [
        "pmoves/scripts/**/*.sh",
        "pmoves/scripts/**/*.ps1",
        "pmoves/scripts/**/*.py",
        "pmoves/tools/**/*.sh",
        "pmoves/tools/**/*.ps1",
        "pmoves/tools/**/*.py",
        "pmoves/docker-compose*.yml",
        "pmoves/compose/*.yml",
        "pmoves/Makefile",
        "pmoves/mk/*.mk",
        "scripts/**/*.sh",
        "scripts/**/*.ps1",
        "scripts/**/*.py",
    ]
    files = discover_files(scan_file_patterns)
    ignore_paths = {"pmoves/tools/submodule_sitrep.py"}
    output_path = Path(args.output).expanduser().resolve()
    try:
        output_rel = output_path.relative_to(REPO_ROOT).as_posix()
        ignore_paths.add(output_rel)
    except ValueError:
        pass

    legacy_terms = [
        "PMOVES-Firefly-iii",
        "PMOVES-E2B-Danger-Room-Deskdesktop",
        "pmoves/pmoves/vendor/e2b",
    ]
    alias_terms = [
        "pmoves/vendor/",
        "research/A2UI",
        "pmoves-surf",
    ]
    legacy_hits = scan_patterns(files, legacy_terms, ignore=ignore_paths)
    alias_hits = scan_patterns(files, alias_terms, ignore=ignore_paths)

    docs_files = discover_files(
        [
            "pmoves/docs/**/*.md",
            "docs/**/*.md",
            ".claude/**/*.md",
        ]
    )
    docs_legacy_hits = scan_patterns(docs_files, legacy_terms, ignore=ignore_paths)
    dirty_submodules = collect_dirty_submodules(modules)

    report = format_report(
        modules=modules,
        status_rows=status_rows,
        recursive_exit=recursive.returncode,
        recursive_stderr=recursive.stderr,
        duplicate_urls=duplicate_urls,
        legacy_hits=legacy_hits,
        alias_hits=alias_hits,
        docs_legacy_hits=docs_legacy_hits,
        dirty_submodules=dirty_submodules,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
