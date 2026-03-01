#!/usr/bin/env python3
"""Check Claude command coverage in the Codex parity map."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


PARITY_CMD_RE = re.compile(r"`/([a-z0-9][a-z0-9-]*(?::[a-z0-9][a-z0-9-]*)?)`")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_token(command_file: Path, commands_root: Path) -> str:
    rel = command_file.relative_to(commands_root).with_suffix("")
    parts = list(rel.parts)
    if len(parts) == 1:
        return parts[0].lower()
    prefix = parts[0].lower()
    name = "-".join(p.lower() for p in parts[1:])
    return f"{prefix}:{name}"


def _scan_claude_commands(commands_root: Path) -> set[str]:
    tokens: set[str] = set()
    for file_path in sorted(commands_root.rglob("*.md")):
        tokens.add(_canonical_token(file_path, commands_root))
    return tokens


def _scan_parity_tokens(parity_map: Path) -> set[str]:
    text = parity_map.read_text(encoding="utf-8")
    return {match.group(1).lower() for match in PARITY_CMD_RE.finditer(text)}


def _prefix(token: str) -> str:
    if ":" not in token:
        return "root"
    return token.split(":", 1)[0]


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _render_report(
    *,
    total: int,
    mapped: set[str],
    missing: set[str],
    claude_tokens: set[str],
    parity_tokens: set[str],
    parity_map_path: str,
    commands_path: str,
) -> str:
    coverage = (len(mapped) / total * 100.0) if total else 100.0
    missing_by_prefix: dict[str, list[str]] = defaultdict(list)
    for token in sorted(missing):
        missing_by_prefix[_prefix(token)].append(token)

    prefix_counts = Counter(_prefix(token) for token in claude_tokens)
    mapped_prefix_counts = Counter(_prefix(token) for token in mapped)

    lines: list[str] = [
        "# Codex Claude Parity Gaps Report",
        f"_Generated: {dt.date.today().isoformat()}_",
        "",
        "## Scope",
        f"- Commands source: `{commands_path}`",
        f"- Parity map: `{parity_map_path}`",
        "",
        "## Summary",
        f"- Claude command tokens: **{total}**",
        f"- Parity map tokens: **{len(parity_tokens)}**",
        f"- Mapped tokens: **{len(mapped)}**",
        f"- Missing tokens: **{len(missing)}**",
        f"- Coverage: **{coverage:.1f}%**",
        "",
        "## Prefix Coverage",
        "| Prefix | Claude Tokens | Mapped Tokens | Missing Tokens |",
        "| --- | ---: | ---: | ---: |",
    ]

    for prefix in sorted(prefix_counts):
        claude_count = prefix_counts[prefix]
        mapped_count = mapped_prefix_counts.get(prefix, 0)
        lines.append(f"| `{prefix}` | {claude_count} | {mapped_count} | {claude_count - mapped_count} |")

    lines.extend(["", "## Missing Tokens by Prefix"])
    if not missing_by_prefix:
        lines.append("- None")
    else:
        for prefix in sorted(missing_by_prefix):
            lines.append(f"- `{prefix}`")
            for token in missing_by_prefix[prefix]:
                lines.append(f"  - `{token}`")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="Check Claude command parity coverage for Codex.")
    parser.add_argument(
        "--commands-root",
        type=Path,
        default=root / ".claude" / "commands",
        help="Path to .claude/commands directory.",
    )
    parser.add_argument(
        "--parity-map",
        type=Path,
        default=root / "pmoves" / "docs" / "AGENTS" / "CODEX_CLAUDE_PARITY_MAP.md",
        help="Path to CODEX_CLAUDE_PARITY_MAP.md",
    )
    parser.add_argument(
        "--write-report",
        type=Path,
        default=root / "pmoves" / "docs" / "AGENTS" / "CODEX_CLAUDE_PARITY_GAPS.md",
        help="Optional report output path. Pass empty string to skip writing.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any command token is missing.",
    )
    args = parser.parse_args(argv)

    commands_root = args.commands_root.resolve()
    parity_map = args.parity_map.resolve()
    write_report = args.write_report

    if not commands_root.exists():
        print(f"ERROR: commands root not found: {commands_root}", file=sys.stderr)
        return 2
    if not parity_map.exists():
        print(f"ERROR: parity map not found: {parity_map}", file=sys.stderr)
        return 2

    claude_tokens = _scan_claude_commands(commands_root)
    parity_tokens = _scan_parity_tokens(parity_map)

    mapped = claude_tokens & parity_tokens
    missing = claude_tokens - parity_tokens
    total = len(claude_tokens)
    coverage = (len(mapped) / total * 100.0) if total else 100.0

    print(f"claude_tokens={total}")
    print(f"parity_tokens={len(parity_tokens)}")
    print(f"mapped_tokens={len(mapped)}")
    print(f"missing_tokens={len(missing)}")
    print(f"coverage={coverage:.1f}%")

    if write_report and str(write_report).strip():
        report = _render_report(
            total=total,
            mapped=mapped,
            missing=missing,
            claude_tokens=claude_tokens,
            parity_tokens=parity_tokens,
            parity_map_path=_display_path(parity_map, root),
            commands_path=_display_path(commands_root, root),
        )
        write_report.parent.mkdir(parents=True, exist_ok=True)
        write_report.write_text(report, encoding="utf-8")
        print(f"wrote_report={write_report}")

    if args.strict and missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
