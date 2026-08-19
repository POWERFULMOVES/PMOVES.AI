#!/usr/bin/env python3
"""Verify that every SHA-pinned GitHub Action actually exists.

Why this gate exists
--------------------
Pinning an action by commit SHA is the supply-chain-correct thing to do, but it
converts a wrong value into a *silently dead workflow* rather than a loud error.
A non-existent SHA fails during workflow SETUP — before `runs-on` resolves, before
any step logs, before any annotation is emitted. `gh run list` shows
`startup_failure`, which is indistinguishable from a runner hiccup.

Two such pins were live in this repo and neither was noticed:

  * ``actions/upload-artifact@50769540...`` (commented ``# v8.0.0``, a version that
    has never been released) in both branch-protection workflows. Result:
    ``branch-protection-ruleset-sync`` ran once and failed; ``branch-protection-drift``
    ran four times and failed four times. Zero successful runs, ever — so branch
    protection was never applied and drift was never evaluated, while the config
    file describing 25 enrolled repos sat unread.

  * ``docker/setup-qemu-action@49b3bc8e...`` (commented ``# v3``) in
    ``build-nats-workers.yml``. Five runs, five ``startup_failure``, going back to
    2026-07-26. The NATS worker images have never been built by CI.

The comment is the second half of the defect. ``# v8.0.0`` is what a human reads
when deciding whether a pin is current; a fabricated version comment survives a
SHA correction and keeps misinforming. So both halves are checked.

Checks
------
1. ERROR — the pinned 40-hex SHA does not resolve in the named repository.
2. WARN  — the trailing ``# vX[.Y[.Z]]`` comment names a tag that does not exist
   in that repository. (A comment that merely lags the moving major tag is NOT
   flagged: floating tags advance, and pins legitimately trail them.)

Refusing to guess
-----------------
If the GitHub API cannot be reached, this exits 3 (COULD NOT MEASURE) rather than
0. An instrument that reports "pass" when it failed to take a measurement is the
precise failure mode this gate exists to prevent — see
``pmoves/docs/audit/INSTRUMENT_TRUST_AUDIT_2026-08-15.md``.

Usage:
  python pmoves/tools/action_pin_audit.py            # audit all workflows
  python pmoves/tools/action_pin_audit.py --json     # machine-readable

Exit codes:
  0  every SHA pin resolves (version-comment warnings do not fail the gate)
  1  at least one pin is unresolvable
  3  the GitHub API was unreachable — no verdict could be reached
  4  usage / parse error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
API = "https://api.github.com"

# `uses: owner/repo[/subpath]@ref` with an optional trailing `# comment`.
USES_RE = re.compile(
    r"""^\s*-?\s*uses:\s*
        (?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)
        /(?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*)
        (?P<subpath>(?:/[A-Za-z0-9._-]+)*)
        @(?P<ref>[^\s#]+)
        (?:\s*\#\s*(?P<comment>.*))?$""",
    re.VERBOSE,
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"\bv\d+(?:\.\d+){0,2}\b")
# A COMPLETE vX.Y.Z, as opposed to a moving major like `v2`. Only these are
# compared against the tag's commit -- a bare `# v2` is a deliberate reference
# to the moving tag, so its SHA is expected to drift.
_FULL_VERSION_RE = re.compile(r"v\d+\.\d+\.\d+")


class Unreachable(RuntimeError):
    """The GitHub API could not be consulted, so no verdict is possible."""


def _token() -> Optional[str]:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(var)
        if value:
            return value
    return None


_GH_CHECKED: List[bool] = []


def _gh_available() -> bool:
    """Prefer the `gh` CLI: it already holds the repo's auth and uses the system
    trust store, which bare urllib does not on every node in this fleet."""
    if not _GH_CHECKED:
        try:
            subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=15, check=True)
            _GH_CHECKED.append(True)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            _GH_CHECKED.append(False)
    return _GH_CHECKED[0]


def _get_via_gh(path: str) -> Optional[Any]:
    result = subprocess.run(
        ["gh", "api", path.lstrip("/")], capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    stderr = result.stderr or ""
    # 404 (no such tag) and 422 (no such commit) are real answers about the pin.
    if re.search(r"\b(404|422)\b", stderr) or "Not Found" in stderr or "No commit found" in stderr:
        return None
    raise Unreachable(f"{path}: gh api failed: {stderr.strip()[:200]}")


def _get_via_urllib(path: str) -> Optional[Any]:
    request = urllib.request.Request(f"{API}{path}")
    request.add_header("Accept", "application/vnd.github+json")
    token = _token()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 422):
            return None
        # 403 with a rate-limit body is NOT an answer about the pin.
        raise Unreachable(f"{path}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise Unreachable(f"{path}: {exc}") from exc


def _get(path: str, cache: Dict[str, Any]) -> Optional[Any]:
    """GET an API path. Returns None for 404/422, raises Unreachable on transport failure."""
    if path in cache:
        return cache[path]
    try:
        if _gh_available():
            payload = _get_via_gh(path)
        else:
            payload = _get_via_urllib(path)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise Unreachable(f"{path}: {exc}") from exc
    cache[path] = payload
    return payload


def workflow_files() -> List[Path]:
    """Tracked workflow files, so an untracked scratch copy is never audited."""
    try:
        out = subprocess.run(
            ["git", "ls-files", ".github/workflows"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
        paths = [REPO_ROOT / line for line in out.splitlines() if line.strip()]
        if paths:
            return [p for p in paths if p.suffix in (".yml", ".yaml") and p.is_file()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    if not WORKFLOW_DIR.is_dir():
        return []
    return sorted(
        p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml") and p.is_file()
    )


def _display_path(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise. `relative_to` raises for
    any path outside the repo, which would make the tool unusable against a
    scratch copy or a checkout mounted elsewhere."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def collect_pins(paths: List[Path]) -> List[Dict[str, Any]]:
    """Every `uses:` line pinned to a 40-hex SHA, with its source location."""
    pins: List[Dict[str, Any]] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            ref = match.group("ref")
            if not SHA_RE.match(ref):
                continue  # tag/branch refs are a separate policy question
            comment = (match.group("comment") or "").strip()
            version = VERSION_RE.search(comment)
            pins.append({
                "file": _display_path(path),
                "line": lineno,
                "owner": match.group("owner"),
                "repo": match.group("repo"),
                "sha": ref,
                "comment": comment,
                "version": version.group(0) if version else None,
            })
    return pins


def audit(pins: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    cache: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    for pin in pins:
        slug = f"{pin['owner']}/{pin['repo']}"
        if _get(f"/repos/{slug}/commits/{pin['sha']}", cache) is None:
            errors.append({**pin, "reason": f"no such commit in {slug}"})
            continue  # a bad SHA makes the version comment moot
        version = pin["version"]
        if not version:
            continue
        ref = _get(f"/repos/{slug}/git/ref/tags/{version}", cache)
        if ref is None:
            warnings.append({**pin, "reason": f"comment names {version}, which is not a tag in {slug}"})
            continue

        # The tag EXISTS. That was the whole check, and it is not enough: a pin can
        # name a real version while pointing somewhere else entirely. Measured on
        # 2026-08-19, step-security/harden-runner@05e31511 was commented `# v2.13.1`
        # while 05e31511 is the MOVING `v2` tag; v2.13.1 is f4a75cfd. The pin
        # resolved, the tag existed, the audit passed, and the comment named the
        # wrong release -- in a file whose stated purpose is that the comment is
        # "what a human reads when deciding whether a pin is current".
        #
        # Only full vX.Y.Z comments are compared. A bare `# v2`/`# v3` is a
        # deliberate reference to the moving major, so its SHA is expected to drift
        # and comparing it would flag correct pins.
        if not _FULL_VERSION_RE.fullmatch(version):
            continue
        target = _tag_commit(slug, ref, cache)
        if target is not None and target != pin["sha"]:
            warnings.append({**pin, "reason": (
                f"comment names {version}, but that tag is {target[:12]} "
                f"and this pin is {pin['sha'][:12]}"
            )})
    return errors, warnings


def _tag_commit(slug: str, ref: Any, cache: Dict[str, Any]) -> Optional[str]:
    """Commit a tag ref points at, dereferencing annotated tags.

    A lightweight tag's ref object IS the commit. An ANNOTATED tag's ref object is
    a tag object that has to be followed to reach the commit -- comparing the ref
    sha directly reports a mismatch on every annotated tag, which is most releases.
    """
    obj = (ref or {}).get("object") or {}
    sha, kind = obj.get("sha"), obj.get("type")
    if not sha:
        return None
    if kind != "tag":
        return sha
    tag = _get(f"/repos/{slug}/git/tags/{sha}", cache)
    return ((tag or {}).get("object") or {}).get("sha")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)

    paths = workflow_files()
    if not paths:
        print("[error] no workflow files found", file=sys.stderr)
        return 4
    pins = collect_pins(paths)

    try:
        errors, warnings = audit(pins)
    except Unreachable as exc:
        # Deliberately NOT exit 0. See module docstring.
        print(f"[unmeasured] GitHub API unreachable: {exc}", file=sys.stderr)
        print("[unmeasured] no verdict reached — this is not a pass", file=sys.stderr)
        if args.json:
            print(json.dumps({"status": "unmeasured", "detail": str(exc)}, indent=2))
        return 3

    if args.json:
        print(json.dumps({
            "status": "fail" if errors else "pass",
            "workflows": len(paths),
            "pins": len(pins),
            "errors": errors,
            "warnings": warnings,
        }, indent=2))
        return 1 if errors else 0

    print(f"Action pin audit: {len(pins)} SHA pins across {len(paths)} workflows")
    for warning in warnings:
        print(f"[WARN]  {warning['file']}:{warning['line']}  "
              f"{warning['owner']}/{warning['repo']}@{warning['sha'][:12]} — {warning['reason']}")
    for error in errors:
        print(f"[ERROR] {error['file']}:{error['line']}  "
              f"{error['owner']}/{error['repo']}@{error['sha'][:12]} — {error['reason']}")
    if errors:
        print(f"\nFAILED: {len(errors)} unresolvable pin(s). "
              f"A workflow with an unresolvable pin fails at setup and produces no logs.")
        return 1
    print(f"PASS: every SHA pin resolves ({len(warnings)} version-comment warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
