#!/usr/bin/env python3
"""Keep every inline ``redact_url`` fallback identical to services/common/redact.py.

Services whose image may not ship ``services/common`` import the canonical
helper inside ``try:`` and define a copy in ``except ImportError:``. This tool
rewrites each copy from the canonical source (and points the import at
``services.common.redact``). ``--check`` only reports drift.

Exit codes: 0 clean, 1 drift found (with --check), 3 could not measure.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]
CANONICAL = PMOVES / "services" / "common" / "redact.py"
IMPORT_LINE = "from services.common.redact import redact_url"
HANDLER_COMMENT = "# image ships without services/common; copy of services/common/redact.py"


def canonical_function() -> str:
    src = CANONICAL.read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == "redact_url":
            return ast.get_source_segment(src, node)
    raise SystemExit(3)


def canonical_block() -> str:
    fn = "\n".join(("    " + line) if line else "" for line in canonical_function().splitlines())
    return (
        "try:\n"
        f"    {IMPORT_LINE}\n"
        f"except ImportError:  {HANDLER_COMMENT}\n"
        "    import re as _re\n"
        "\n"
        f"{fn}\n"
    )


def fallback_blocks(tree: ast.Module):
    """Yield module-level try/except ImportError blocks that define redact_url."""
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        imports = any(
            isinstance(n, ast.ImportFrom)
            and (n.module or "").startswith("services.common")
            and any(a.name == "redact_url" for a in n.names)
            for n in node.body
        )
        defines = any(
            isinstance(n, ast.FunctionDef) and n.name == "redact_url"
            for h in node.handlers
            for n in h.body
        )
        if imports and defines:
            yield node


def copy_functions(path: Path):
    tree = ast.parse(path.read_text())
    for block in fallback_blocks(tree):
        for h in block.handlers:
            for n in h.body:
                if isinstance(n, ast.FunctionDef) and n.name == "redact_url":
                    yield n


def files_with_copies():
    for path in sorted(PMOVES.rglob("*.py")):
        if path == CANONICAL or "node_modules" in path.parts:
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if "def redact_url" in text and "except ImportError" in text:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, do not rewrite")
    args = parser.parse_args()
    want = canonical_block()
    drift = 0
    for path in files_with_copies():
        src = path.read_text()
        lines = src.splitlines(keepends=True)
        for block in sorted(fallback_blocks(ast.parse(src)), key=lambda b: -b.lineno):
            have = "".join(lines[block.lineno - 1 : block.end_lineno])
            if have.rstrip("\n") == want.rstrip("\n"):
                continue
            drift += 1
            print(f"{'DRIFT' if args.check else 'SYNC '} {path.relative_to(PMOVES.parent)}:{block.lineno}")
            if not args.check:
                lines[block.lineno - 1 : block.end_lineno] = [want]
        if not args.check:
            path.write_text("".join(lines))
    return 1 if (drift and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
