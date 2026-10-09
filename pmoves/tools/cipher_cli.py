#!/usr/bin/env python3
"""cipher_cli.py — pmoves-cipher CLI dispatcher.

A thin, opinionated front end to the chit_* tool family in pmoves/tools/. Each
subcommand wraps one chit_* script (or `curl` for `health`) and prints a
single-line summary a CI job or human can grep. The CLI exists so the
launcher-trio (deploy/provision/pmoves-cipher.{sh,ps1,cmd}) can be a single
`pmoves-cipher <subcommand>` command on PATH, and so the chit_* tools stay
independent of one wrapper.

SDK provenance
--------------
The wrappers intentionally do NOT `import` the chit_* scripts. Each subcommand
spawns the underlying script as a subprocess so the chit_* tools remain the
unit-of-work for their respective lanes (manifest reconciliation, CGP decode,
secrets sync). Tests exercise the boundary at the HTTP layer (for `health`)
and at the argparse layer (for the rest), and assert the exact argv we pass.

Each subcommand argument maps to the underlying script's expected arg:

  cipher_cli register  <lane> <summary>  -> chit_manifest_register.py
  cipher_cli verify    <file>            -> chit_verify.py          --cgp <file>
  cipher_cli decode    <file>            -> chit_decode_secrets.py  --cgp <file>
  cipher_cli encode    <file>            -> chit_encode_secrets.py  --env-file <file>
  cipher_cli bundle    <lane>            -> chit_sync_workflow_bundle.py
  cipher_cli health                       -> curl -sf http://127.0.0.1:8105/health

The lane + summary passed to `register` and `bundle` are also APPENDED to a
JSON-Lines lane ledger (pmoves/data/chit/lanes.jsonl). That ledger is the
audit trail `register` produces that chit_manifest_register.py does not --
manifest reconciliation is about secrets, lanes are about PMOVES work slices.

Exit codes
----------
  0  subcommand completed its primary action (regardless of what the wrapped
     tool printed; a tool that already returned 0 to us)
  2  usage error (missing/invalid args, input file does not exist) -- also
     the code passed through when the wrapped tool is missing or unspawnable
  3  wrapped tool failed: its exit was the chit family's generic 1, which
     this CLI normalizes so callers never see the generic Unix 1
  4  health endpoint unreachable / HTTP error (emitted by `health`)

Passthrough rule: a wrapped tool that exits with rc >= 2 surfaces its own
code verbatim. Its stderr already reached the terminal (subprocess.run does
not capture it), so the operator sees the failure where it happened, and the
chit family's documented codes stay observable (e.g.
chit_manifest_register's 4 for parse/usage errors). Only rc == 1 is
remapped, to 3. The non-zero vocabulary stays deliberately narrow (2/3/4)
so callers can branch on them without false positives (e.g. a chit tool
that prints a warning to stderr but returns 0 stays a 0 from this CLI).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Sequence, Tuple

# Where the chit_* tools live, computed from this file's location so the
# launcher does not have to know.
PMOVES_TOOLS = Path(__file__).resolve().parent
PMOVES_DATA = PMOVES_TOOLS.parent / "data"
LANES_LEDGER = PMOVES_DATA / "chit" / "lanes.jsonl"

# Health endpoint for the running cipher API. Hardcoded loopback -- the API
# runs on the same node as the CLI on every operator-described topology.
# Cross-node access uses .claude/mcp.json::pmoves-cipher, not this CLI.
HEALTH_URL = os.environ.get("PMOVES_CIPHER_HEALTH_URL", "http://127.0.0.1:8105/health")
HEALTH_TIMEOUT = float(os.environ.get("PMOVES_CIPHER_HEALTH_TIMEOUT", "3"))


# ----------------------------------------------------------------------------
# Lane ledger -- append-only JSONL audit trail for `register <lane> <summary>`
# and `bundle <lane>` invocations. Lives under pmoves/data/chit/ which is
# gitignored WHOLESALE (pmoves/.gitignore excludes data/chit/; an earlier
# revision of this comment claimed the ledger SHOULD be committed -- that
# was wrong, and entries embed host/user that must not reach a public repo
# anyway). The ledger is intentionally local-node audit data. Lane history
# that must outlive the node lives in cipher MCP / lane-aware AGNOTE rows
# (pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md), not in git.
# ----------------------------------------------------------------------------
def _ensure_ledger() -> Path:
    LANES_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if not LANES_LEDGER.exists():
        LANES_LEDGER.touch()
    return LANES_LEDGER


def _append_lane(action: str, lane: str, summary: str, extra: Optional[dict] = None) -> None:
    ledger = _ensure_ledger()
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": action,
        "lane": lane,
        "summary": summary,
        "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown",
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
    }
    if extra:
        entry.update(extra)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


# ----------------------------------------------------------------------------
# Subcommand runners -- one function per subcommand. Each returns a (rc, msg)
# tuple; main() picks the exit code. Print-as-you-go is fine: callers (CI, a
# human) want to see what happened.
# ----------------------------------------------------------------------------
def _run_chit(script: str, argv: Sequence[str], label: str) -> Tuple[int, str]:
    """Invoke pmoves/tools/<script> with argv. Returns (rc, last-line-summary)."""
    path = PMOVES_TOOLS / script
    if not path.exists():
        print(f"error: required tool not found: {path}", file=sys.stderr)
        return 2, f"missing tool: {script}"
    cmd = [sys.executable, str(path), *argv]
    print(f"[cipher_cli] {label}: {' '.join(cmd)}", file=sys.stderr)
    try:
        completed = subprocess.run(cmd, check=False)
    except OSError as e:
        print(f"error: failed to spawn {script}: {e}", file=sys.stderr)
        return 2, f"spawn failed: {script}"
    return completed.returncode, f"{label} exited {completed.returncode}"


def _map_wrapped_rc(rc: int) -> int:
    """Normalize a wrapped tool's exit code to this CLI's exit contract.

    0 stays 0. The chit family's generic 1 becomes 3 (wrapped-tool failed)
    so this CLI never leaks the generic Unix 1. rc >= 2 passes through
    verbatim: the tool's stderr already reached the terminal (subprocess.run
    does not capture it), and the tool's own documented codes (e.g.
    chit_manifest_register's 4 for parse/usage errors) stay observable.
    """
    if rc == 0:
        return 0
    if rc == 1:
        return 3
    return rc


def cmd_register(args: argparse.Namespace) -> int:
    lane = args.lane
    summary = args.summary
    if not lane or not summary:
        print("error: register requires <lane> and <summary>", file=sys.stderr)
        return 2

    # Append to the lane ledger FIRST so the audit trail exists even if the
    # chit_manifest_register invocation below fails. The lane is the operator's
    # intent; the manifest reconciliation is a downstream side-effect.
    _append_lane("register", lane, summary, extra={"manifest_check": True})

    # Run chit_manifest_register.py in --check mode so we report any pending
    # additions without writing (the lane operator will run the full sync via
    # `bundle` or the explicit `make -C pmoves secrets-funnel` lane). The
    # check is non-destructive; the underlying tool exits 1 when additions are
    # pending, which we surface verbatim so the operator can decide.
    rc, msg = _run_chit("chit_manifest_register.py", ["--check"], "manifest_check")
    if rc == 0:
        print(f"register: lane={lane} summary={summary!r} manifest_check=ok")
    elif rc == 1:
        # Pending additions is the EXPECTED state when a new lane introduces a
        # new secret; not an error from this CLI's perspective.
        print(
            f"register: lane={lane} summary={summary!r} manifest_check=pending "
            "(run `make -C pmoves secrets-funnel` to apply)"
        )
    else:
        print(f"register: lane={lane} summary={summary!r} {msg}", file=sys.stderr)
        return _map_wrapped_rc(rc)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"error: verify: file does not exist: {path}", file=sys.stderr)
        return 2
    rc, msg = _run_chit("chit_verify.py", ["--cgp", str(path)], "verify")
    print(f"verify: {path} {msg}")
    return _map_wrapped_rc(rc)


def cmd_decode(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"error: decode: file does not exist: {path}", file=sys.stderr)
        return 2
    # decode is read-only by contract: we do NOT pass --out. The wrapped tool
    # writes to stdout (or fails) which is what the operator wants when
    # "decoding" an env.cgp.json to inspect it.
    rc, msg = _run_chit("chit_decode_secrets.py", ["--cgp", str(path)], "decode")
    print(f"decode: {path} {msg}")
    return _map_wrapped_rc(rc)


def cmd_encode(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"error: encode: file does not exist: {path}", file=sys.stderr)
        return 2
    # encode writes back. The wrapped tool defaults --out to pmoves/data/chit/
    # env.cgp.json (the canonical location) and --namespace to
    # 'pmoves.secrets'. We do NOT override either, so `cipher_cli encode
    # env.shared` is the standard "regenerate the canonical bundle" call.
    rc, msg = _run_chit("chit_encode_secrets.py", ["--env-file", str(path)], "encode")
    print(f"encode: {path} {msg}")
    return _map_wrapped_rc(rc)


def cmd_bundle(args: argparse.Namespace) -> int:
    lane = args.lane
    if not lane:
        print("error: bundle requires <lane>", file=sys.stderr)
        return 2

    _append_lane("bundle", lane, "<sync_workflow_bundle>")

    # chit_sync_workflow_bundle.py takes no positional args; it reads
    # ~/.config/pmoves/chit/env.cgp.json (or the Windows twin under %APPDATA%)
    # and writes back into pmoves/env.shared. The lane label is recorded in
    # the ledger above so the bundle output can be traced to a lane.
    rc, msg = _run_chit("chit_sync_workflow_bundle.py", [], "bundle")
    print(f"bundle: lane={lane} {msg}")
    return _map_wrapped_rc(rc)


def cmd_health(args: argparse.Namespace) -> int:
    # `health` is the only subcommand that does NOT spawn a chit_* tool. It
    # hits the live cipher API at /health (loopback only). This is the
    # operator's "is the cipher container even up" check; it does not require
    # bearer auth because /health is the public health probe.
    curl = shutil.which("curl")
    if curl:
        # Use the system curl when available -- the operator's mental model
        # is `curl -sf http://127.0.0.1:8105/health`, and the codebase has
        # many such one-liners. Subprocess.run with check=False lets us
        # distinguish connect-refused (no curl exit 7) from HTTP 500.
        try:
            completed = subprocess.run(
                [curl, "-sf", "--max-time", str(int(HEALTH_TIMEOUT)), HEALTH_URL],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as e:
            print(f"health: spawn failed: {e}", file=sys.stderr)
            return 4
        if completed.returncode == 0:
            body = completed.stdout.strip()
            print(f"health: ok ({HEALTH_URL})")
            if body:
                print(body)
            return 0
        if completed.returncode == 22:
            # curl 22 = HTTP >= 400 with -f. The server answered, so the
            # service is up but reports an error.
            print(f"health: http error (curl 22) {HEALTH_URL}", file=sys.stderr)
            return 4
        # curl 7 = couldn't connect; 28 = timeout. Service is DOWN.
        print(f"health: down (curl {completed.returncode}) {HEALTH_URL}", file=sys.stderr)
        return 4

    # No curl on PATH (rare on the operator-described topologies, but the
    # POSIX launcher does run on stripped-down nodes). Fall back to stdlib so
    # the subcommand still has a working implementation. We intentionally do
    # NOT raise -- the goal is "give the operator an answer".
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=HEALTH_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip()
            print(f"health: ok ({HEALTH_URL})")
            if body:
                print(body)
            return 0
    except urllib.error.HTTPError as e:
        print(f"health: http {e.code} ({HEALTH_URL})", file=sys.stderr)
        return 4
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"health: down ({e}) ({HEALTH_URL})", file=sys.stderr)
        return 4


# ----------------------------------------------------------------------------
# Argparse wiring -- one subparser per subcommand. The CLI is intentionally
# minimal: each subcommand takes the args documented in the module docstring
# and forwards them to the wrapped tool. No flags are duplicated here; if you
# need a flag the underlying tool already supports, call that tool directly.
# ----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pmoves-cipher",
        description="pmoves-cipher CLI dispatcher (wraps chit_* tools + /health).",
    )
    sub = p.add_subparsers(dest="subcommand", required=True)

    # register <lane> <summary>
    sp = sub.add_parser("register", help="record a lane + summary; idempotent manifest check")
    sp.add_argument("lane", help="work lane identifier (typically the branch name)")
    sp.add_argument("summary", help="one-line description of the lane's intent")
    sp.set_defaults(func=cmd_register)

    # verify <file>
    sp = sub.add_parser("verify", help="verify a CGP packet (chit_verify.py --cgp)")
    sp.add_argument("file", help="path to a CGP JSON file")
    sp.set_defaults(func=cmd_verify)

    # decode <file>
    sp = sub.add_parser("decode", help="decode a CGP packet to .env-style text (read-only)")
    sp.add_argument("file", help="path to a CGP JSON file")
    sp.set_defaults(func=cmd_decode)

    # encode <file>
    sp = sub.add_parser("encode", help="encode an env file into a CGP packet (writes back)")
    sp.add_argument("file", help="path to an env file (e.g. env.shared)")
    sp.set_defaults(func=cmd_encode)

    # bundle <lane>
    sp = sub.add_parser("bundle", help="sync the local CHIT bundle into env.shared")
    sp.add_argument("lane", help="work lane identifier for the audit trail")
    sp.set_defaults(func=cmd_bundle)

    # health
    sp = sub.add_parser("health", help="check the live cipher API at /health (loopback)")
    sp.set_defaults(func=cmd_health)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
