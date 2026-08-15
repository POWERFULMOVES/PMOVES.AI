#!/usr/bin/env python3
"""Assert the vendored pretext build matches the Pmoves-pretext gitlink.

The vendored copy at pmoves/services/a2ui-renderer/vendor/pretext/ is compiler
output committed to the tree. Nothing forces it to stay in step with the
submodule commit it was built from, so this check does.

It fails (exit 1) when:
  * the recorded source commit in vendor/pretext/README.md does not match the
    Pmoves-pretext gitlink recorded in the index, or
  * the vendored package.json is missing, unparseable, or has lost
    "type": "module" (which is what keeps Node's require(esm) path working --
    see vendor/pretext/README.md), or
  * dist/layout.js -- the file the "main" field points at -- is absent.

Run:  python pmoves/tools/check_vendored_pretext.py
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR = REPO_ROOT / "pmoves" / "services" / "a2ui-renderer" / "vendor" / "pretext"
SUBMODULE = "Pmoves-pretext"

# "- **Source commit:** `<40 hex>` ..."
COMMIT_RE = re.compile(r"\*\*Source commit:\*\*\s*`([0-9a-f]{40})`")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def gitlink_sha() -> str:
    """The commit the superproject records for the submodule."""
    out = subprocess.run(
        ["git", "ls-tree", "HEAD", SUBMODULE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if out.returncode != 0 or not out.stdout.strip():
        fail(f"could not read the {SUBMODULE} gitlink from HEAD: {out.stderr.strip()}")
    # "160000 commit <sha>\t<path>"
    parts = out.stdout.split()
    if len(parts) < 3 or parts[0] != "160000":
        fail(f"{SUBMODULE} is not a gitlink in HEAD (got: {out.stdout.strip()!r})")
    return parts[2]


def recorded_sha() -> str:
    readme = VENDOR / "README.md"
    if not readme.is_file():
        fail(f"missing {readme.relative_to(REPO_ROOT)} -- vendored builds must record provenance")
    match = COMMIT_RE.search(io.open(readme, encoding="utf-8").read())
    if not match:
        fail(
            f"{readme.relative_to(REPO_ROOT)} has no '- **Source commit:** `<sha>`' line; "
            "a vendored build with no recorded source cannot be verified"
        )
    return match.group(1)


def check_package() -> str:
    manifest = VENDOR / "package.json"
    if not manifest.is_file():
        fail(f"missing {manifest.relative_to(REPO_ROOT)}")
    try:
        data = json.load(io.open(manifest, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{manifest.relative_to(REPO_ROOT)} is not valid JSON: {exc}")
    if data.get("type") != "module":
        fail(
            'vendored package.json lost \'"type": "module"\'. a2ui-renderer compiles to '
            "CommonJS and reaches pretext through Node's require(esm) path, which needs "
            "this package boundary. See vendor/pretext/README.md."
        )
    main = data.get("main", "./dist/layout.js").lstrip("./")
    if not (VENDOR / main).is_file():
        fail(f"package.json main points at {main}, which does not exist -- rebuild the vendored dist")
    return str(data.get("version", "?"))


def check_tracked() -> None:
    """Every vendored dist file on disk must also be tracked by git.

    The root .gitignore carries a blanket `dist/` rule, so without the negation in
    vendor/pretext/.gitignore this directory is silently absent from the repo while
    still present on the machine that built it -- the image then builds locally and
    nowhere else. Checking the filesystem alone cannot see that.
    """
    on_disk = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (VENDOR / "dist").rglob("*")
        if path.is_file()
    }
    if not on_disk:
        fail("vendor/pretext/dist is empty -- rebuild it (see vendor/pretext/README.md)")

    out = subprocess.run(
        ["git", "ls-files", "--", f"{VENDOR.relative_to(REPO_ROOT).as_posix()}/dist"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tracked = {line.strip() for line in out.stdout.splitlines() if line.strip()}

    untracked = sorted(on_disk - tracked)
    if untracked:
        fail(
            f"{len(untracked)} vendored dist file(s) exist on disk but are not tracked by git "
            f"(first: {untracked[0]}).\n"
            "The root .gitignore excludes dist/ -- vendor/pretext/.gitignore must negate it, "
            "or the vendored build ships to nobody."
        )


def main() -> int:
    if not VENDOR.is_dir():
        fail(f"missing vendor directory {VENDOR.relative_to(REPO_ROOT)}")

    version = check_package()
    check_tracked()
    recorded, actual = recorded_sha(), gitlink_sha()

    if recorded != actual:
        fail(
            "vendored pretext is out of step with the submodule.\n"
            f"  vendor/pretext/README.md records: {recorded}\n"
            f"  {SUBMODULE} gitlink at HEAD:      {actual}\n"
            "Rebuild the vendored dist from the gitlink commit, or bump the gitlink to match.\n"
            "Recipe: pmoves/services/a2ui-renderer/vendor/pretext/README.md"
        )

    print(f"OK: vendored pretext {version} matches {SUBMODULE} gitlink {actual[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
