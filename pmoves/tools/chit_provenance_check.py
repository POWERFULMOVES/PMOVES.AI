#!/usr/bin/env python3
"""Is this node's CHIT bundle still recoverable, and does it know it isn't?

WHY A STANDING CHECK AND NOT ANOTHER WARNING.

`secrets-rotate` already warns when it replaces a CI-pulled bundle with a local
export, and PR #2938 widened that to fire on the standing state rather than only
the transition. Both are correct and both are ROTATE-TRIGGERED. A node that has
not rotated recently sits in the degraded state and is never told.

Measured on Z890, 2026-09-04, with nothing rotating for days:

    bundle age            163 hours
    provenance marker     ABSENT  -- local export
    manifest projection   40 declared keys the bundle cannot supply,
                          including LOGFLARE_*, MCP_GATEWAY_AUTH_TOKEN,
                          P7_CONTROL_TOKEN, SECRET_KEY_BASE, VAULT_ENC_KEY
    recovery artifact     1-day retention; the producing run was 6 days ago

Nothing on the node said so, because nobody rotated.

WHAT MAKES IT URGENT RATHER THAN UNTIDY. The remedy has a 24-hour shelf life.
`sync-secrets-local.yml` uploads with `retention-days: 1`, so `secrets-pull`
works only if a producer ran today. Past that the fix is no longer "pull the
bundle", it is "run the workflow, wait, then pull" -- a different, longer
procedure that an operator discovers at exactly the wrong moment. A degradation
whose remedy expires before the degradation is noticed is worth surfacing on its
own schedule.

WHAT THIS DOES NOT DO. It does not enumerate the missing keys itself. That
projection already exists (`make -C pmoves manifest-audit`, which is
`secrets_sync.py report --allow-missing`), and a second implementation would
drift from the first. This shells out to it and reports what it found. It never
pulls, never writes, never prints a secret VALUE -- names and counts only, so it
is safe to run inside an agent transcript.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"

WORKFLOW = "sync-secrets-local.yml"
# Same override the puller honours (pull_chit_bundle.sh:21). Hard-coding it
# meant a node with PMOVES_REPO set would have its artifact checked against
# upstream while `secrets-pull` queried the fork -- so the check could report
# a live artifact that the pull could not find, or demand a producer run when
# the overridden repo already had one.
REPO = os.environ.get("PMOVES_REPO", "POWERFULMOVES/PMOVES.AI")
RETENTION_HOURS = 24


def default_bundle() -> Path:
    """Mirror CHIT_EXPORT_PATH from pmoves/mk/codex.mk lines 4-6.

    Deliberately duplicated rather than shelled out to `make`: this check must
    run when the environment is already broken, and asking a Makefile where its
    own secrets live is a dependency on the thing being diagnosed.
    """
    override = os.environ.get("CHIT_EXPORT_PATH")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pmoves" / "chit" / "env.cgp.json"


def audit_missing(bundle: Path) -> tuple[int, list[str], str]:
    """Count + name the declared keys this bundle cannot supply.

    Delegates to secrets_sync.py -- the SAME projection `make manifest-audit`
    prints. Reimplementing the manifest walk here would be a second source of
    truth for which keys matter, and the two would drift silently.
    """
    cmd = [
        sys.executable,
        str(PMOVES / "tools" / "secrets_sync.py"),
        "report",
        "--manifest",
        "pmoves/chit/secrets_manifest.yaml",
        "--allow-missing",
        "--cgp",
        str(bundle),
    ]
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, [], "could not run the projection: %s" % exc

    blob = (out.stdout or "") + (out.stderr or "")
    m = re.search(r"Missing secrets \(non-fatal\):\s*(.+)", blob)
    if not m:
        if out.returncode != 0:
            # LAST line, not first. A python traceback's first line is
            # "Traceback (most recent call last):" -- true of every failure and
            # therefore useless. The cause is on the last line, and here it is
            # usually "ModuleNotFoundError: No module named 'yaml'", which names
            # a fixable environment problem rather than an unexplained failure.
            lines = [ln.strip() for ln in blob.splitlines() if ln.strip()]
            why = lines[-1] if lines else "no output"
            if "No module named" in why:
                # NAME THE REMEDY, because this one has a specific and common
                # cause. CODEX_PY prefers .venv-pmoves and falls back to a bare
                # interpreter when it is absent (codex.mk:20-21). A git WORKTREE
                # has no venv -- it is gitignored and per-checkout -- so every
                # agent working in one hits the fallback, which routinely lacks
                # PyYAML. Measured: identical `manifest-audit` succeeds in the
                # main checkout and fails in a worktree. Without this line the
                # message reads like a broken node rather than an unbootstrapped
                # directory, which is what I concluded the first time.
                why += "  -- run: make -C pmoves venv-bringup"
            return -1, [], "could not run (%s)" % why[:200]
        return 0, [], ""
    names = [n.strip() for n in m.group(1).split(",") if n.strip()]
    return len(names), names, ""


def recovery_window(node: str, offline: bool) -> str:
    """Is a pullable artifact still alive? Best effort, never fatal.

    Same query shape as scripts/pull_chit_bundle.sh (newest successful run,
    then an UNEXPIRED chit-bundle-* artifact) so the two cannot disagree about
    what "recoverable" means.
    """
    if offline:
        return "not checked (--offline)"
    try:
        run = subprocess.run(
            ["gh", "run", "list", "--repo", REPO, "--workflow", WORKFLOW,
             "--status", "success", "--limit", "1", "--json", "databaseId,createdAt"],
            capture_output=True, text=True, timeout=45,
        )
        if run.returncode != 0:
            return "not checked (gh unavailable or unauthenticated)"
        runs = json.loads(run.stdout or "[]")
        if not runs:
            return "NO successful producer run found at all"
        run_id = runs[0]["databaseId"]
        arts = subprocess.run(
            ["gh", "api", "repos/%s/actions/runs/%s/artifacts" % (REPO, run_id)],
            capture_output=True, text=True, timeout=45,
        )
        if arts.returncode != 0:
            return "not checked (artifact query failed)"
        data = json.loads(arts.stdout or "{}").get("artifacts", [])
        live = [a for a in data if a.get("name", "").startswith("chit-bundle-")
                and not a.get("expired")]
        mine = [a for a in live if a.get("name", "").startswith("chit-bundle-%s-" % node)]
        if mine:
            return "OK -- an unexpired artifact for '%s' exists (run %s)" % (node, run_id)
        if live:
            # ANOTHER NODE'S BUNDLE IS STILL A PULL. pull_chit_bundle.sh:60-62
            # prefers `chit-bundle-<node>-*` and then FALLS BACK to any
            # unexpired `chit-bundle-*`. Reporting this as unrecoverable and
            # sending the operator to dispatch a workflow would be a false
            # alarm that costs a CI run and several minutes -- and an advisory
            # that cries wolf is the one that gets switched off.
            return ("OK -- no artifact for '%s', but %d other unexpired bundle(s) "
                    "exist and the puller falls back to them (run %s)"
                    % (node, len(live), run_id))
        return "EXPIRED -- newest run %s has no unexpired chit-bundle-* (1-day retention)" % run_id
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        return "not checked (%s)" % type(exc).__name__


def _needs_producer(window: str) -> bool:
    """Is dispatching a workflow the actual remedy, or would a pull work?

    Named once and shared by both call sites. The distinction is the whole
    point of the check: `secrets-pull` is right when ANY unexpired bundle
    exists (the puller falls back across nodes), and wrong -- it will fail --
    when none does. Telling an operator to dispatch when a pull would have
    worked costs a CI run and several minutes; an advisory that cries wolf is
    the one that gets switched off.
    """
    return window.startswith("EXPIRED") or window.startswith("NO successful")


def main() -> int:
    ap = argparse.ArgumentParser(description="CHIT bundle provenance + recoverability")
    ap.add_argument("--bundle", default=None)
    ap.add_argument("--node", default=os.environ.get("PMOVES_NODE", "5090"))
    # The DISPATCH target is the producer, not this node. Pattern-B nodes
    # (Z890, the default 5090) are consumers with no self-hosted runner, and
    # sync-secrets-local.yml schedules on one -- so `-f targets=z890` names a
    # job that cannot be picked up. pull_chit_bundle.sh:27 already carries the
    # distinction as PMOVES_BUNDLE_PRODUCER (default b850); same default here so
    # the two roads cannot disagree.
    ap.add_argument("--producer",
                    default=os.environ.get("PMOVES_BUNDLE_PRODUCER", "b850"))
    ap.add_argument("--offline", action="store_true", help="skip the artifact query")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when the bundle is a local export")
    ap.add_argument("--max-names", type=int, default=12)
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    bundle = Path(args.bundle) if args.bundle else default_bundle()
    marker = Path(str(bundle) + ".provenance")

    print("chit-provenance-check: can this node still recover its bundle?")
    print()
    print("  bundle     %s" % bundle)

    if not bundle.is_file():
        print("             ABSENT")
        print()
        # RECOVERY IS CHECKED HERE TOO. An earlier version returned straight
        # after naming `secrets-pull`, which is the one case where the operator
        # has NO bundle at all -- so being told to run a command that will fail
        # is worse here than anywhere else. If the artifact has expired, the
        # pull is not the remedy and saying so costs one API call.
        window = recovery_window(args.node, args.offline)
        print("  recovery   %s" % window)
        print()
        print("  No bundle at all, so the funnel has nothing to project from.")
        print("      PMOVES_NODE=%s make -C pmoves secrets-pull" % args.node)
        if _needs_producer(window):
            print("  That will fail as things stand -- produce an artifact first:")
            print("      make -C pmoves secrets-sync-trigger TARGETS=%s"
                  % args.producer)
        return 1 if args.strict else 0

    age_h = (time.time() - bundle.stat().st_mtime) / 3600.0
    print("             present, %.0f hours old" % age_h)

    ci = marker.is_file()
    print("  provenance %s" % ("CI-pulled (marker present)" if ci
                               else "LOCAL EXPORT (no marker)"))
    print()

    if ci:
        print("  OK  This bundle came from sync-secrets-local.yml, so the")
        print("      prod-only keys it delivers are present.")
        print()
        print("  recovery   %s" % recovery_window(args.node, args.offline))
        return 0

    n, names, err = audit_missing(bundle)
    if err:
        print("  projection %s" % err)
    elif n == 0:
        print("  projection every manifest-declared key resolves from this bundle.")
        print("             So the missing marker may be cosmetic here -- but it")
        print("             still means the next funnel has no CI source.")
    else:
        print("  projection %d declared key(s) this bundle cannot supply:" % n)
        for name in names[: args.max_names]:
            print("               %s" % name)
        if n > args.max_names:
            print("               ... and %d more" % (n - args.max_names))
        print("             (same projection as `make -C pmoves manifest-audit`)")
    print()

    window = recovery_window(args.node, args.offline)
    print("  recovery   %s" % window)
    print()
    print("  Every secrets-funnel from here regenerates tier files WITHOUT the")
    print("  keys above. The loss is silent until a service that needs one")
    print("  restarts, which is usually much later and looks unrelated.")
    print()
    print("  Restore:   PMOVES_NODE=%s make -C pmoves secrets-pull" % args.node)
    if _needs_producer(window):
        print("  The artifact is gone (retention is 1 day), so produce one first:")
        print("      make -C pmoves secrets-sync-trigger TARGETS=%s" % args.producer)
        print("  ...then wait for it to finish and re-run secrets-pull.")

    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
