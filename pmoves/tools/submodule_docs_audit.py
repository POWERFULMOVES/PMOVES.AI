#!/usr/bin/env python3
"""Generate a submodule documentation coverage dossier for PMOVES."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"
DEFAULT_OUTPUT = REPO_ROOT / "pmoves" / "docs" / "SUBMODULE_DOCS_DOSSIER.md"
DOC_CANDIDATES = (
    "PMOVES.AI_INTEGRATION.md",
    "pmoves-integrations/README.md",
    "docs/README.md",
    "docs/index.md",
    "README.md",
)


@dataclass
class SubmoduleEntry:
    name: str
    path: str
    url: str
    initialized: bool
    docs: list[str]

    @property
    def has_docs(self) -> bool:
        return bool(self.docs)

    @property
    def has_pmoves_integration(self) -> bool:
        return "PMOVES.AI_INTEGRATION.md" in self.docs

    @property
    def requires_pmoves_integration(self) -> bool:
        # Nested vendor/research/integration mirrors inherit parent overlays.
        # Top-level submodules should carry an explicit PMOVES integration dossier.
        return "/" not in self.path.replace("\\", "/")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def read_gitmodules() -> dict[str, dict[str, str]]:
    proc = run_git("config", "-f", str(GITMODULES), "--get-regexp", r"^submodule\..*\.(path|url)$")
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "failed to parse .gitmodules")
    records: dict[str, dict[str, str]] = {}
    for raw in proc.stdout.splitlines():
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            continue
        key, value = parts
        match = key.removeprefix("submodule.")
        name, field = match.rsplit(".", maxsplit=1)
        records.setdefault(name, {})[field] = value.strip()
    return records


def is_initialized(path: Path) -> bool:
    if not path.exists():
        return False
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def collect_docs(path: Path) -> list[str]:
    docs: list[str] = []
    for candidate in DOC_CANDIDATES:
        if (path / candidate).exists():
            docs.append(candidate)
    return docs


def collect_entries() -> list[SubmoduleEntry]:
    config = read_gitmodules()
    rows: list[SubmoduleEntry] = []
    for name in sorted(config.keys(), key=lambda item: config[item].get("path", item).lower()):
        path = config[name].get("path", "")
        url = config[name].get("url", "")
        abs_path = REPO_ROOT / path
        rows.append(
            SubmoduleEntry(
                name=name,
                path=path,
                url=url,
                initialized=is_initialized(abs_path),
                docs=collect_docs(abs_path),
            )
        )
    return rows


def render_markdown(entries: list[SubmoduleEntry]) -> str:
    generated = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    total = len(entries)
    initialized = sum(1 for row in entries if row.initialized)
    with_docs = sum(1 for row in entries if row.has_docs)
    required_integration = [row for row in entries if row.requires_pmoves_integration]
    with_integration = sum(1 for row in required_integration if row.has_pmoves_integration)

    lines: list[str] = [
        "# Submodule Docs Dossier",
        f"_Generated: {generated}_",
        "",
        "## Summary",
        f"- Total submodules declared: **{total}**",
        f"- Initialized in workspace: **{initialized}/{total}**",
        f"- With at least one docs entry point: **{with_docs}/{total}**",
        f"- Top-level modules with `PMOVES.AI_INTEGRATION.md`: **{with_integration}/{len(required_integration)}**",
        "",
        "## Coverage Matrix",
        "| Submodule | Path | Initialized | PMOVES Integration Dossier | Local Docs Entry Points |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in entries:
        init = "yes" if row.initialized else "no"
        dossier = "yes" if row.has_pmoves_integration else "no"
        docs = ", ".join(f"`{row.path}/{doc}`" for doc in row.docs) if row.docs else "_missing_"
        lines.append(
            f"| `{row.name}` | `{row.path}` | {init} | {dossier} | {docs} |"
        )

    missing_docs = [row for row in entries if not row.has_docs]
    missing_dossier = [
        row
        for row in entries
        if row.requires_pmoves_integration and row.has_docs and not row.has_pmoves_integration
    ]
    not_initialized = [row for row in entries if not row.initialized]

    lines.extend(
        [
            "",
            "## Action Queue",
            f"- Missing local docs entry points: **{len(missing_docs)}**",
        ]
    )
    for row in missing_docs:
        lines.append(f"  - `{row.path}`")

    lines.append(f"- Missing `PMOVES.AI_INTEGRATION.md` dossier: **{len(missing_dossier)}**")
    for row in missing_dossier:
        lines.append(f"  - `{row.path}`")

    lines.append(f"- Not initialized in current workspace: **{len(not_initialized)}**")
    for row in not_initialized:
        lines.append(f"  - `{row.path}`")

    lines.extend(
        [
            "",
            "## Maintainer Notes",
            "- Keep this dossier in sync whenever submodules are added, renamed, or promoted.",
            "- Prefer adding `PMOVES.AI_INTEGRATION.md` in each submodule as the canonical PMOVES linkage doc.",
            "- Keep `README.md` focused on upstream module usage; keep PMOVES-specific overlays in the integration dossier.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output markdown path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if initialized submodules are missing docs, or top-level modules miss PMOVES integration dossier.",
    )
    args = parser.parse_args()

    entries = collect_entries()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(entries), encoding="utf-8")
    rel = args.output.relative_to(REPO_ROOT)
    print(f"Wrote {rel}")

    if args.strict:
        missing = [
            row
            for row in entries
            if row.initialized
            and (not row.has_docs or (row.requires_pmoves_integration and not row.has_pmoves_integration))
        ]
        if missing:
            print("FAIL: strict mode found initialized submodules missing docs coverage")
            for row in missing:
                reason = []
                if not row.has_docs:
                    reason.append("no docs entry point")
                if not row.has_pmoves_integration:
                    reason.append("missing PMOVES.AI_INTEGRATION.md")
                joined = ", ".join(reason)
                print(f"  - {row.path}: {joined}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
