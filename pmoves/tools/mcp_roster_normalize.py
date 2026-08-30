#!/usr/bin/env python3
"""Normalize the tracked MCP roster before handing it to a Claude Code session.

This is the transform that used to live as a heredoc inside
``deploy/provision/claude-pmoves.sh`` (and, in PowerShell, inside its ``.ps1``
twin). It moved out here for two reasons: a heredoc cannot be tested, and a
transform that exists twice drifts. Both launchers now call this.

Four passes, in order:

P2  Drop servers whose key starts with ``_``. ``_disabled`` is a note, not an
    off-switch, so Claude would otherwise launch the broken duplicate.
P3  Rewrite repo-relative ``./…`` command and arg paths to absolute, so
    ``uv --directory ./pmoves-nats-mcp`` launches from any caller CWD.
P4  Expand ``${VAR}`` in ``url``, ``headers`` and ``env``.
P5  Act on what would not expand -- DROP a server whose ``url`` is
    unresolvable, WARN about one whose ``headers``/``env`` are.

P4/P5 are the new ones, and they are the point of the file. Claude Code's
documented behaviour for an unresolvable reference is to warn and then *use the
unexpanded ``${VAR}`` text as-is*. So ``http://${TS_Z890}:8105/mcp/sse`` was
handed over as a literal hostname: the server appeared in the roster, appeared
configured, and simply never connected. A session lost its whole memory layer
that way and had no signal distinguishing it from "cipher is down".

WHY THE SPLIT VERDICT IN P5. An unresolvable ``url`` is structurally dead --
``http://:8105/`` can never connect -- so keeping it only preserves the silence.
An unresolvable ``headers``/``env`` value is not: several servers here treat an
absent credential as "run anonymously" (``huggingface``'s own roster note calls
HF_TOKEN a rate-limit upgrade; ``cloudflare`` authenticates through the local
wrangler session). Dropping those would remove working servers to fix a
different bug. They are announced and kept.

Scope is ``url``/``headers``/``env`` and not ``args``. ``args`` carries the
nested-alias form (``${A:-${B}}``) whose purpose is a fallback chain, and
widening a *drop* rule over it is a separate, riskier call. Left to Claude
Code, as today.

Usage:
    mcp_roster_normalize.py SRC --root REPO [--out-dir DIR] [--label NAME]

Writes the normalized roster to a fresh mode-0600 file in *out-dir* and prints
its path on stdout. Exit 0 on success, non-zero on any failure -- the caller is
expected to fall back to the raw roster rather than launch with nothing.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping

# An unresolvable value in these fields makes the server structurally dead.
_DROP_FIELDS = ("url",)
# An unresolvable value in these degrades the server but may still work.
_WARN_FIELDS = ("headers", "env")

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_OUT_PREFIX = "claude-pmoves-mcp-roster."
_OUT_SUFFIX = ".json"
# Startup-read file: the only consumer is Claude Code's config load at session
# start. 1h bounds token-on-disk tightly with no realistic session-start miss
# (pair-review nit: the earlier 12h window was 12x looser than needed).
_STALE_SECONDS = 3600

# Top-level key carrying the P5 verdicts into the roster itself. Pair-review
# finding: the stderr warnings print immediately before `exec claude` and the
# TUI overwrites them within a second -- no agent can read what was dropped or
# degraded. The payload is the durable channel: Claude Code reads only
# `mcpServers`, and the tracked roster already ships a `_pinned_versions_note`
# top-level key, so a `_`-prefixed sibling is established convention and rides
# the file the session (or any doctor check) can re-read.
_VERDICTS_KEY = "_pmoves_roster_verdicts"


def _match_brace(text: str, start: int) -> int:
    """Index of the ``}`` closing the ``{`` at *start*, or -1. Nesting-aware."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_default(body: str) -> tuple[str, str | None]:
    """Split ``NAME:-default`` at brace depth 0. Returns ``(name, default|None)``.

    The default may itself contain ``${...}``, which is why the scan tracks
    depth.

    ONLY the ``:-`` form is recognised. POSIX also spells a default ``${A-B}``,
    but supporting it here would be actively dangerous: ``${TS-Z890}`` is one
    keystroke from the ``${TS_Z890}`` this whole change is about, and under
    POSIX rules it parses as "TS, defaulting to Z890" -- yielding the plausible
    hostname ``http://Z890:8105/`` with no warning and no drop, which is
    strictly worse than the bug being fixed. An identifier check does not save
    it, because ``TS`` is a perfectly valid identifier. Refusing the form
    entirely makes that typo a malformed reference, which gets reported.
    Nothing in the roster uses it, and Claude Code documents only ``:-``.
    """
    depth = 0
    i = 0
    while i < len(body):
        c = body[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0 and c == ":" and body[i + 1 : i + 2] == "-":
            return body[:i], body[i + 2 :]
        i += 1
    return body, None


def expand(text: str, environ: Mapping[str, str], missing: list[str]) -> str:
    """Expand ``${VAR}`` and ``${VAR:-default}``, recording misses.

    An unresolvable reference is left as its literal ``${VAR}`` text and its
    name appended to *missing*. Callers treat a non-empty *missing* as a finding
    against that server.

    "Set" means set AND non-empty. An exported empty string is the classic
    shadow -- it satisfies a presence check while producing ``http://:8105/``
    -- so it counts as missing, not as a value.

    A malformed reference (empty name, unbalanced braces) is recorded too,
    under its literal text. Passing it through silently would be the same
    looks-fine-fails-later failure this module exists to end.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "$" and text[i + 1 : i + 2] == "{":
            end = _match_brace(text, i + 1)
            if end == -1:
                missing.append(text[i:])  # unbalanced -- report, don't swallow
                out.append(text[i:])
                break
            literal = text[i : end + 1]
            name, default = _split_default(text[i + 2 : end])
            name = name.strip()
            if not _IDENT.match(name):
                missing.append(literal)  # malformed reference, e.g. "${ }"
                out.append(literal)
                i = end + 1
                continue
            val = environ.get(name)
            if val:  # set AND non-empty; see docstring
                out.append(val)
            elif default is not None:
                inner: list[str] = []
                rendered = expand(default, environ, inner)
                if inner:
                    # The whole chain failed. Name the OUTERMOST var first: the
                    # inner one is typically a deprecated alias, and telling an
                    # operator to set that is telling them the wrong thing.
                    missing.append(name)
                    missing.extend(inner)
                out.append(rendered)
            else:
                missing.append(name)
                out.append(literal)
            i = end + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _abs_path(value: Any, root: str) -> Any:
    if isinstance(value, str) and value.startswith("./"):
        return os.path.join(root, value[2:])
    return value


def normalize(
    data: Mapping[str, Any],
    root: str,
    environ: Mapping[str, str],
) -> tuple[dict[str, Any], list[tuple[str, list[str]]], list[tuple[str, list[str]]]]:
    """Return ``(roster, dropped, degraded)``.

    *dropped* and *degraded* are ``[(server, [missing_names]), ...]``.

    Note there is no special case for a ``"disabled": true`` server. That key
    is a Cline/Roo convention and is not in Claude Code's documented .mcp.json
    schema, so treating it as an off-switch would mean betting the exact
    silent-failure this module prevents on an assumption. A disabled server
    with an unresolvable url is dropped like any other; it was off anyway.
    """
    clean: dict[str, Any] = {}
    dropped: list[tuple[str, list[str]]] = []
    degraded: list[tuple[str, list[str]]] = []

    for name, cfg in (data.get("mcpServers") or {}).items():
        if name.startswith("_"):  # P2
            continue
        if not isinstance(cfg, dict):
            clean[name] = cfg
            continue

        cfg = copy.deepcopy(cfg)

        # P3 -- repo-relative launch paths
        if isinstance(cfg.get("command"), str):
            cfg["command"] = _abs_path(cfg["command"], root)
        if isinstance(cfg.get("args"), list):
            cfg["args"] = [_abs_path(a, root) for a in cfg["args"]]

        # P4 -- variable expansion, kept per-field so P5 can tell the
        # structurally-dead from the merely-degraded.
        fatal: list[str] = []
        soft: list[str] = []
        for field in _DROP_FIELDS:
            if isinstance(cfg.get(field), str):
                cfg[field] = expand(cfg[field], environ, fatal)
        for field in _WARN_FIELDS:
            block = cfg.get(field)
            if isinstance(block, dict):
                cfg[field] = {
                    k: (expand(v, environ, soft) if isinstance(v, str) else v)
                    for k, v in block.items()
                }

        # P5 -- verdict
        if fatal:
            dropped.append((name, sorted(set(fatal))))
            continue
        if soft:
            degraded.append((name, sorted(set(soft))))
        clean[name] = cfg

    out = dict(data)
    out["mcpServers"] = clean
    return out, dropped, degraded


def _sweep_stale(out_dir: str) -> None:
    """Remove our own expired roster files. Never fatal.

    The file holds expanded bearer tokens and the launcher ``exec``s, so no
    trap can clean up after the session. Sweeping on the next launch bounds how
    long a token sits on disk.
    """
    uid = os.getuid() if hasattr(os, "getuid") else None
    cutoff = time.time() - _STALE_SECONDS
    try:
        entries = list(os.scandir(out_dir))
    except OSError:
        return
    for entry in entries:
        if not entry.name.startswith(_OUT_PREFIX) or not entry.name.endswith(_OUT_SUFFIX):
            continue
        try:
            st = entry.stat(follow_symlinks=False)
            if uid is not None and st.st_uid != uid:
                continue
            if st.st_mtime < cutoff:
                os.unlink(entry.path)
        except OSError:
            continue


def write_private(out_dir: str, payload: dict[str, Any]) -> str:
    """Write *payload* to a fresh mode-0600 file in *out_dir*; return its path.

    P4 expands secrets (bearer tokens, API keys) into this file, which the
    previous version did not -- it only ever held literal ``${VAR}`` text.

    The name is unpredictable rather than ``…-roster.<uid>.json``. A predictable
    name in a world-writable directory is not only a disclosure surface: another
    local user could create it first, our write would fail, and the launcher
    would fall back to the RAW roster -- reinstating the silent ``${TS_Z890}``
    failure on demand. mkstemp gives us a name nobody can squat.
    """
    fd, path = tempfile.mkstemp(dir=out_dir, prefix=_OUT_PREFIX, suffix=_OUT_SUFFIX)
    try:
        # mkstemp already creates 0600; re-assert it where the platform lets us.
        # os.fchmod is POSIX-only -- on Windows mkstemp's ACL is the guarantee.
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _warn(label: str, lines: Iterable[str]) -> None:
    for line in lines:
        print(f"[{label}] {line}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Normalize the PMOVES MCP roster.")
    ap.add_argument("src", help="tracked roster, e.g. .claude/mcp.json")
    ap.add_argument("--root", required=True, help="repo root for ./ rewriting")
    ap.add_argument("--out-dir", default=None, help="where to write (default: temp dir)")
    ap.add_argument("--label", default="mcp-roster", help="stderr message prefix")
    args = ap.parse_args(argv)

    out_dir = args.out_dir or tempfile.gettempdir()

    # utf-8-sig, not the default: it strips a UTF-8 BOM when present and is a
    # no-op when absent. A BOM'd roster fails a plain open()+json.load() with
    # "Expecting value: line 1 column 1", and because the roster carries bare
    # ${VAR}s the caller then takes its fail-closed path and refuses to launch.
    # Any Windows producer can hand us one -- `Set-Content -Encoding UTF8` under
    # PowerShell 5.1 writes EF BB BF -- so the reader tolerates it rather than
    # trusting every writer to get it right.
    with open(args.src, encoding="utf-8-sig") as fh:
        data = json.load(fh)

    payload, dropped, degraded = normalize(data, args.root, os.environ)

    # The durable half of the announcement. stderr still gets the human-facing
    # lines; this key is what survives the TUI for the session/agent that has to
    # work out why a server is missing. Written even when clean -- empty lists
    # are a positive assertion the check RAN, distinguishable from a fallback
    # path that never invoked this tool at all.
    payload[_VERDICTS_KEY] = {
        "source": os.path.abspath(args.src),
        "dropped": [
            {"server": server, "missing": missing} for server, missing in dropped
        ],
        "degraded": [
            {"server": server, "missing": missing} for server, missing in degraded
        ],
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    for server, missing in dropped:
        _warn(args.label, [
            f"WARN: dropping MCP server '{server}' — unset variable(s): " + ", ".join(missing),
            "      its url would have been handed over with the literal ${...} "
            "text and failed silently.",
        ])
    for server, missing in degraded:
        _warn(args.label, [
            f"WARN: MCP server '{server}' kept but degraded — unset variable(s): "
            + ", ".join(missing),
            "      it may run unauthenticated, or fail on first call.",
        ])

    _sweep_stale(out_dir)
    print(write_private(out_dir, payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
