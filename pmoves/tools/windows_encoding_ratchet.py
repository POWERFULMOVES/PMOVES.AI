#!/usr/bin/env python3
"""Ratchet: no text-mode file I/O without an explicit ``encoding=``.

WHY
---
Python's ``open()``/``Path.read_text()`` default to the LOCALE encoding when
``encoding`` is omitted. On a Windows host whose locale is cp1252, reading a
UTF-8 file raises ``UnicodeDecodeError`` -- so a test that only reads a compose
file can fail on Windows and pass on Linux CI, for a reason that has nothing to
do with what the test asserts.

That is not hypothetical. Measured on 2026-11-01: 25 tests in
``pmoves/tests/smoke/test_compose_structure.py`` and
``pmoves/tests/smoke/test_port_conflicts.py`` failed on the operator's Windows
host with exactly that error, and ALL 27 passed with ``PYTHONUTF8=1`` -- which
proves the failures were decoding, not logic. The same defect existed in
``pmoves/scripts/validate_service_tools_packaging.py``.

WHAT THIS MEASURES (and what it does not)
-----------------------------------------
It measures text-mode ``open(...)``, ``.read_text(...)``,
``.write_text(...)`` and ``Path.open(...)`` calls that omit an explicit
``encoding=`` keyword, in ``pmoves/**/*.py``.

``.open(...)`` is judged only when the receiver is NOT one of the known
NON-PATH openers listed in :data:`NON_PATH_OPENERS`. Those openers -- ``wave``,
``os``, ``Image``, ``fitz``, ``tarfile`` and friends -- open BINARY handles
where an ``encoding`` argument has no meaning at all, so demanding one there
would be a false positive.

MEASURED at the time of writing: 153 ``.open(...)`` attribute call sites
exist in ``pmoves/``; 54 of them omit ``encoding=``; of those 54, 48 are
non-path openers (binary/media/module) and 6 are genuine text-mode Path opens.
All 6 were fixed in the same commit that added this tool, so no text-mode
``.open()`` site is left unjudged. The live count is printed on every run.

Calls whose ``encoding`` argument is passed POSITIONALLY: ``open()`` takes
``encoding`` as its 4th positional parameter; a call with 4+ positional
arguments cannot be judged from the AST alone, so this tool treats it as a
GAP (it cannot prove the encoding was given). MEASURED at the time of
writing: ZERO such call sites exist in ``pmoves/``.

FAIL CLOSED
-----------
A file that cannot be read, or that cannot be parsed as Python, is an
INSTRUMENT ERROR, not a skip. The gate exits non-zero. A gate that cannot
measure its input must not report success.

BASELINE CONTRACT
-----------------
``pmoves/configs/encoding_ratchet/_known_gaps.yaml`` records the PRE-EXISTING
population, per file, with its count. The contract is the same shape as
``pmoves/configs/image_staleness/_known_gaps.yaml``:

* a file NOT in the baseline that has gaps  -> NEW GAP        -> gate FAILS
* a file in the baseline whose count ROSE    -> NEW GAP        -> gate FAILS
* a file in the baseline whose count FELL    -> STALE BASELINE -> gate FAILS
* a file in the baseline with NO gaps left   -> STALE BASELINE -> gate FAILS
* a file in the baseline that no longer exists -> ORPHANED     -> gate FAILS

The last three exist so the baseline cannot outlive the defect it records:
fixing a file does not silently re-arm the defect when the baseline is later
pruned.

Exit codes: 0 clean | 1 gate failed | 2 instrument/setup error.

Usage:
    python pmoves/tools/windows_encoding_ratchet.py --check
    python pmoves/tools/windows_encoding_ratchet.py --write-baseline --yes
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES_DIR = REPO_ROOT / "pmoves"
DEFAULT_BASELINE = PMOVES_DIR / "configs" / "encoding_ratchet" / "_known_gaps.yaml"

# Directories that are not PMOVES runtime code. `docs/` holds prose and
# research artefacts -- some of them are not even valid Python, and a scan
# that tried to parse them would be measuring the wrong thing.
SKIP_DIRS = {"docs", "__pycache__", ".venv", "venv", "node_modules", ".git"}

# The calls this tool measures.
TEXT_CALLS = {"read_text", "write_text"}

# `open()`'s signature: open(file, mode, buffering, encoding, ...).
# 4 positional arguments means `encoding` MAY have been given positionally.
OPEN_ENCODING_POSITIONAL_INDEX = 3

# `.open(...)` attribute calls whose receiver is one of these are NOT
# path opens. They open binary handles -- audio, images, archives, raw file
# descriptors -- where an `encoding` argument has no meaning, so demanding one
# would be a false positive. MEASURED 2026-11-01: 48 of the 54 `.open()`
# call sites in pmoves/ that omit `encoding=` have a receiver from this list.
NON_PATH_OPENERS = {
    "Image",
    "bz2",
    "codecs",
    "dbm",
    "fitz",
    "gzip",
    "io",
    "lzma",
    "mmap",
    "os",
    "shelve",
    "subprocess",
    "sys",
    "tarfile",
    "tempfile",
    "urllib",
    "wave",
    "webbrowser",
    "zipfile",
}


class InstrumentError(RuntimeError):
    """The ratchet could not measure its input."""


def _mode_argument(node: ast.Call, path_open: bool) -> ast.expr | None:
    """The AST node holding the mode string, for builtin open() or Path.open().

    The two signatures differ: builtin ``open(file, mode, ...)`` takes the mode
    SECOND, while ``Path.open(mode, ...)`` takes it FIRST. Reading the wrong
    slot silently mis-classifies binary as text.
    """
    if path_open:
        mode = node.args[0] if node.args else None
    else:
        mode = node.args[1] if len(node.args) >= 2 else None
    for kw in node.keywords:
        if kw.arg == "mode":
            mode = kw.value
    return mode


def _is_binary_mode(node: ast.Call, path_open: bool) -> bool:
    """True when the call opens the file in binary mode.

    Binary mode has no encoding, so requiring one would be a false positive.
    """
    mode = _mode_argument(node, path_open)
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return "b" in mode.value
    return False


def _has_encoding_keyword(node: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in node.keywords)


def _open_encoding_may_be_positional(node: ast.Call) -> bool:
    """True when `open()` was called with >= 4 positional args.

    We cannot prove the encoding was supplied, so the site counts as a gap.
    """
    return len(node.args) > OPEN_ENCODING_POSITIONAL_INDEX


def _is_non_path_opener(node: ast.Call) -> bool:
    """True when the receiver of `.open(...)` is a known binary/media opener."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    recv = func.value
    if isinstance(recv, ast.Name):
        return recv.id in NON_PATH_OPENERS
    return False


def find_gaps(source: str, filename: str) -> tuple[list[dict], int]:
    """Text-mode file I/O calls in `source` that omit `encoding=`.

    Returns (gaps, skipped_non_path_openers).
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise InstrumentError(f"{filename}: cannot parse as Python: {exc}") from exc

    gaps: list[dict] = []
    skipped = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        path_open = False
        if isinstance(func, ast.Attribute) and func.attr in TEXT_CALLS:
            call_name = func.attr
        elif isinstance(func, ast.Attribute) and func.attr == "open":
            if _is_non_path_opener(node):
                skipped += 1
                continue
            path_open = True
            call_name = "Path.open"
        elif isinstance(func, ast.Name) and func.id == "open":
            call_name = "open"
        else:
            continue
        if _has_encoding_keyword(node):
            continue
        if _is_binary_mode(node, path_open):
            continue
        reason = "no encoding= keyword"
        if call_name == "open" and _open_encoding_may_be_positional(node):
            reason = "no encoding= keyword; encoding may be positional"
        gaps.append({"line": node.lineno, "call": call_name, "reason": reason})
    return gaps, skipped


def scan(root: Path) -> tuple[dict[str, int], list[dict], dict]:
    """Return (per-file gap counts, instrument errors, out-of-scope info)."""
    if not root.is_dir():
        raise InstrumentError(f"not a directory: {root}")

    files = sorted(p for p in root.rglob("*.py") if not (SKIP_DIRS & set(p.relative_to(root).parts)))
    if not files:
        raise InstrumentError(f"no Python files under {root} -- nothing to measure")

    counts: dict[str, int] = {}
    errors: list[dict] = []
    path_open_calls = 0
    non_path_skipped = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append({"file": rel, "error": f"unreadable: {exc}"})
            continue
        try:
            gaps, skipped = find_gaps(source, rel)
        except InstrumentError as exc:
            errors.append({"file": rel, "error": str(exc)})
            continue
        non_path_skipped += skipped
        path_open_calls += _count_attribute_opens(source, rel)
        if gaps:
            counts[rel] = len(gaps)

    out_of_scope = {
        "attribute_open_calls": path_open_calls,
        "non_path_openers_skipped": non_path_skipped,
        "note": (
            "`.open()` calls on known binary/media openers are skipped: they open "
            "binary handles where an encoding argument has no meaning"
        ),
    }
    return counts, errors, out_of_scope


def _count_attribute_opens(source: str, filename: str) -> int:
    """Total `.open(...)` attribute call sites in `source` (judged or not)."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
        ):
            count += 1
    return count


def load_baseline(path: Path) -> dict[str, int]:
    """Read the baseline mapping. A missing baseline is an empty baseline."""
    if not path.exists():
        return {}
    import yaml  # local import: the baseline is optional, the scan is not

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    known = data.get("known_gaps") or {}
    if not isinstance(known, dict):
        raise InstrumentError(f"{path}: known_gaps must be a mapping")
    out: dict[str, int] = {}
    for name, entry in known.items():
        if isinstance(entry, dict):
            count = entry.get("count")
            if not isinstance(count, int):
                raise InstrumentError(f"{path}: known_gaps[{name}] has no integer count")
            out[str(name)] = count
        elif isinstance(entry, int):
            out[str(name)] = entry
        else:
            raise InstrumentError(f"{path}: known_gaps[{name}] has an unreadable shape")
    return out


def write_baseline(path: Path, counts: dict[str, int], reason: str) -> None:
    import yaml

    body = {
        "known_gaps": {
            name: {
                "count": count,
                "reason": reason,
            }
            for name, count in sorted(counts.items())
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# pmoves/configs/encoding_ratchet/_known_gaps.yaml\n"
        "#\n"
        "# Pre-existing text-mode file I/O sites that omit an explicit `encoding=`.\n"
        "#\n"
        "# Generated by `python pmoves/tools/windows_encoding_ratchet.py\n"
        "# --write-baseline --yes`, then reviewed. Each entry records the number of\n"
        "# sites in that file, so the baseline rots visibly:\n"
        "#\n"
        "#   count ROSE   -> a new gap; the gate fails\n"
        "#   count FELL   -> a gap was fixed; the baseline is stale; the gate fails\n"
        "#   file gone    -> an orphaned entry; the gate fails\n"
        "#\n"
        "# Prune an entry as you fix its file. Do not regenerate wholesale.\n"
    )
    path.write_text(
        header + yaml.safe_dump(body, sort_keys=True, default_flow_style=False),
        encoding="utf-8",
    )


def compare(counts: dict[str, int], baseline: dict[str, int], root: Path) -> dict:
    """Diff the measured population against the baseline.

    The three failure kinds are kept distinct on purpose:

    * a baseline entry whose file NO LONGER EXISTS is ORPHANED -- the file was
      deleted, and the baseline must not outlive it;
    * a baseline entry whose file exists but has no gaps left is STALE -- the
      defect was fixed, and the entry must be pruned so it cannot re-arm;
    * a baseline entry whose count FELL is STALE too -- the same pruning
      duty, for the same reason.
    """
    new_gaps: list[dict] = []
    stale: list[dict] = []
    orphans: list[dict] = []

    for name, count in sorted(counts.items()):
        if name not in baseline:
            new_gaps.append({"file": name, "count": count, "reason": "not in baseline"})
        elif count > baseline[name]:
            new_gaps.append(
                {
                    "file": name,
                    "count": count,
                    "baseline_count": baseline[name],
                    "reason": "gap count rose above the baseline",
                }
            )
        elif count < baseline[name]:
            stale.append(
                {
                    "file": name,
                    "count": count,
                    "baseline_count": baseline[name],
                    "reason": "gap count fell below the baseline -- update the baseline",
                }
            )

    for name, count in sorted(baseline.items()):
        if not (root / name).exists():
            orphans.append(
                {"file": name, "reason": "file no longer exists -- drop the baseline entry"}
            )
        elif name not in counts:
            stale.append(
                {
                    "file": name,
                    "count": 0,
                    "baseline_count": count,
                    "reason": "no gaps left in this file -- drop the baseline entry",
                }
            )

    return {"new_gaps": new_gaps, "stale_gaps": stale, "orphan_gaps": orphans}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=PMOVES_DIR, help="tree to scan (default: pmoves/)")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="baseline file")
    parser.add_argument("--write-baseline", action="store_true", help="rewrite the baseline from the current scan")
    parser.add_argument("--yes", action="store_true", help="acknowledge rewriting the baseline")
    parser.add_argument("--json", action="store_true", help="emit the payload as JSON")
    parser.add_argument("--check", action="store_true", help="run the gate (default)")
    args = parser.parse_args()

    try:
        counts, errors, out_of_scope = scan(args.root)
        baseline = load_baseline(args.baseline)
    except InstrumentError as exc:
        print(f"windows-encoding-ratchet: INSTRUMENT ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive, but must fail closed
        print(f"windows-encoding-ratchet: INSTRUMENT ERROR: {exc}", file=sys.stderr)
        return 2

    if args.write_baseline:
        if not args.yes:
            print(
                "error: --write-baseline rewrites the whole baseline; pass --yes to acknowledge",
                file=sys.stderr,
            )
            return 2
        write_baseline(
            args.baseline,
            counts,
            "pre-existing text-mode file I/O without an explicit encoding= (Windows cp1252 class)",
        )
        print(f"windows-encoding-ratchet: baseline written: {args.baseline} ({len(counts)} file(s))")
        return 0

    diff = compare(counts, baseline, args.root)
    payload = {
        "scanned_root": str(args.root),
        "files_with_gaps": len(counts),
        "total_gaps": sum(counts.values()),
        "baseline_files": len(baseline),
        "counts": counts,
        "new_gaps": diff["new_gaps"],
        "stale_gaps": diff["stale_gaps"],
        "orphan_gaps": diff["orphan_gaps"],
        "problems": errors,
        "out_of_scope": out_of_scope,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("windows-encoding-ratchet: no text-mode file I/O without an explicit encoding=")
        print(f"  scanned tree        : {args.root}")
        print(f"  files with gaps     : {payload['files_with_gaps']}")
        print(f"  total gap sites     : {payload['total_gaps']}")
        print(f"  baseline files      : {payload['baseline_files']}")
        print(
            f"  .open() calls       : {out_of_scope['attribute_open_calls']} attribute call(s); "
            f"{out_of_scope['non_path_openers_skipped']} skipped as binary/media openers"
        )
        if payload["problems"]:
            print(f"  {len(payload['problems'])} INSTRUMENT ERROR(S) -- the scan could not measure:")
            for item in payload["problems"]:
                print(f"    - {item['file']}: {item['error']}")
        if payload["new_gaps"]:
            print(f"  {len(payload['new_gaps'])} NEW GAP(S) -- the gate FAILS:")
            for item in payload["new_gaps"]:
                extra = f" (baseline {item['baseline_count']})" if "baseline_count" in item else ""
                print(f"    - {item['file']}: {item['count']} site(s){extra}")
        if payload["stale_gaps"]:
            print(f"  {len(payload['stale_gaps'])} STALE baseline entr(ies) -- the gate FAILS:")
            for item in payload["stale_gaps"]:
                print(f"    - {item['file']}: {item['reason']}")
        if payload["orphan_gaps"]:
            print(f"  {len(payload['orphan_gaps'])} ORPHANED baseline entr(ies) -- the gate FAILS:")
            for item in payload["orphan_gaps"]:
                print(f"    - {item['file']}: {item['reason']}")

    # A NEW gap, a STALE baseline, an ORPHANED entry, or an INSTRUMENT ERROR
    # all fail the gate. A gate that cannot measure fails closed.
    return (
        1
        if (
            payload["new_gaps"]
            or payload["stale_gaps"]
            or payload["orphan_gaps"]
            or payload["problems"]
        )
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
