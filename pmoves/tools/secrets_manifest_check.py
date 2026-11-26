"""Read-only dry run: does the secrets manifest load under the funnel's models?

The manifest is zero-access to agents, so a change to how its fields are
parsed (``ManifestShape``: label, required, min_length, prefix) cannot be
measured against it by the author. This lets a node holder answer that BEFORE
merge, without running the funnel: it loads the manifest exactly as
``secrets_sync.load_manifest`` does, but checks EVERY entry instead of stopping
at the first, and decodes nothing -- the CHIT bundle is never opened.

Prints only entry ids and the problem with each (field names, types, the
label NAME); a manifest holds no secret values, and none are printed.

Exit codes: 0 every entry loads / 1 at least one entry would be refused /
3 the document itself cannot be read (missing, not YAML, wrong version).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

import yaml

from pmoves.tools.secret_shape_rules import EXIT_FINDINGS, EXIT_OK, EXIT_UNMEASURED
from pmoves.tools.secrets_sync import _load_manifest_document, _parse_entry


def check_manifest(path: Path) -> Tuple[int, List[Tuple[str, str]]]:
    """Return (entries checked, [(entry id, problem), ...]). Raises on document errors."""
    _cgp_path, default_targets, entries_raw = _load_manifest_document(path)
    problems: List[Tuple[str, str]] = []
    checked = 0
    for index, item in enumerate(entries_raw):
        entry_id = item.get("id") if isinstance(item, dict) else None
        name = entry_id if isinstance(entry_id, str) else f"<entry #{index}>"
        try:
            if _parse_entry(item, default_targets) is not None:
                checked += 1
        except ValueError as exc:
            problems.append((name, str(exc)))
    return checked, problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", required=True, help="path to the v1 secrets manifest")
    args = parser.parse_args(argv)
    path = Path(args.manifest)
    try:
        checked, problems = check_manifest(path)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        reason = exc.__class__.__name__ if isinstance(exc, (OSError, yaml.YAMLError)) else str(exc)
        print(f"secrets-manifest-check: COULD-NOT-MEASURE -- {path.name}: {reason}", file=sys.stderr)
        print("VERDICT: UNMEASURED exit=3")
        return EXIT_UNMEASURED
    for entry_id, problem in problems:
        print(f"entry {entry_id}: {problem}")
    print(f"secrets-manifest-check: {checked} entr{'y' if checked == 1 else 'ies'} load, "
          f"{len(problems)} would be refused")
    code = EXIT_FINDINGS if problems else EXIT_OK
    print(f"VERDICT: {'FAIL' if problems else 'PASS'} exit={code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
