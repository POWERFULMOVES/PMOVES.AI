#!/usr/bin/env python3
"""Normalize the tracked MCP roster before handing it to a Claude Code session.

This is the transform that used to live as a heredoc inside
``deploy/provision/claude-pmoves.sh``. It moved out here for one reason: the
heredoc could not be tested, and the bug it failed to catch was invisible
precisely because nothing exercised it.

Three passes, in order:

P2  Drop servers whose key starts with ``_``. ``_disabled`` is a note, not an
    off-switch, so Claude would otherwise launch the broken duplicate.
P3  Rewrite repo-relative ``./…`` command and arg paths to absolute, so
    ``uv --directory ./pmoves-nats-mcp`` launches from any caller CWD.
P4  Expand ``${VAR}`` references in ``url``, ``headers`` and ``env`` -- and
    DROP, loudly, any server referencing a variable that is not set.

P4 is the new one, and it is the point of the file. Claude Code's documented
behaviour for an unresolvable reference is to warn and then *use the
unexpanded ``${VAR}`` text as-is*. So ``http://${TS_Z890}:8105/mcp/sse``
was handed over as a literal hostname: the server appeared in the roster,
appeared configured, and simply never connected. A session lost its whole
memory layer that way and had no signal distinguishing it from "cipher is
down". A dropped-and-announced server is recoverable; a silently-404ing one
is not.

Scope of P4 is deliberately ``url``/``headers``/``env`` and not ``args``.
``args`` carries the nested-alias form (``${A:-${B}}``) whose whole purpose is
a fallback chain, and widening a *drop* rule over it is a separate, riskier
call than widening an *expansion*. Left to Claude Code, as today.

Usage:
    mcp_roster_normalize.py SRC DST --root /path/to/repo [--label claude-pmoves]

Exit 0 on success (DST written), non-zero on any failure -- the caller is
expected to fall back to the raw roster rather than launch with nothing.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from typing import Any, Iterable, Mapping

# Fields scanned for ${VAR} references. A miss in any of these makes the server
# unusable, which is what earns a drop.
_SCALAR_FIELDS = ("url",)
_MAPPING_FIELDS = ("headers", "env")


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


def _split_default(body: str) -> tuple[str, str | None, bool]:
    """Split ``NAME:-default`` / ``NAME-default`` at brace depth 0.

    Returns ``(name, default_or_None, colon_form)``. The default may itself
    contain ``${...}``, which is why the scan tracks depth.
    """
    depth = 0
    i = 0
    while i < len(body):
        c = body[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0:
            if c == ":" and body[i + 1 : i + 2] == "-":
                return body[:i], body[i + 2 :], True
            if c == "-":
                return body[:i], body[i + 1 :], False
        i += 1
    return body, None, False


def expand(text: str, environ: Mapping[str, str], missing: list[str]) -> str:
    """Expand ``${VAR}`` / ``${VAR:-d}`` / ``${VAR-d}``, recording misses.

    An unresolvable reference is left as its literal ``${VAR}`` text and its
    name appended to *missing*. Callers treat a non-empty *missing* as fatal
    for that server.

    "Set" means set AND non-empty for the bare and ``:-`` forms. An exported
    empty string is the classic shadow -- it satisfies a presence check while
    producing ``http://:8105/`` -- so it counts as missing, not as a value.
    The POSIX ``-`` form keeps POSIX semantics: set-but-empty is a value.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "$" and text[i + 1 : i + 2] == "{":
            end = _match_brace(text, i + 1)
            if end == -1:  # unbalanced -- not a reference, emit verbatim
                out.append(text[i])
                i += 1
                continue
            literal = text[i : end + 1]
            name, default, colon = _split_default(text[i + 2 : end])
            name = name.strip()
            val = environ.get(name)
            if val is not None and (val != "" or (default is not None and not colon)):
                out.append(val)
            elif default is not None:
                out.append(expand(default, environ, missing))
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
) -> tuple[dict[str, Any], list[tuple[str, list[str]]]]:
    """Return ``(normalized_roster, [(server, [missing_vars]), ...])``."""
    clean: dict[str, Any] = {}
    dropped: list[tuple[str, list[str]]] = []

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

        # A server declared off is off. Expanding or warning about it would
        # nag forever about a variable nobody needs.
        if cfg.get("disabled") is True:
            clean[name] = cfg
            continue

        # P4 -- variable resolution
        missing: list[str] = []
        for field in _SCALAR_FIELDS:
            if isinstance(cfg.get(field), str):
                cfg[field] = expand(cfg[field], environ, missing)
        for field in _MAPPING_FIELDS:
            block = cfg.get(field)
            if isinstance(block, dict):
                cfg[field] = {
                    k: (expand(v, environ, missing) if isinstance(v, str) else v)
                    for k, v in block.items()
                }

        if missing:
            dropped.append((name, sorted(set(missing))))
            continue

        clean[name] = cfg

    out = dict(data)
    out["mcpServers"] = clean
    return out, dropped


def _write_private(dst: str, payload: dict[str, Any]) -> None:
    """Write *payload* to *dst* atomically, mode 0600.

    P4 expands secrets (bearer tokens, API keys) into this file, which the
    previous version did not -- it only ever held literal ``${VAR}`` text. The
    path is predictable and lives in a world-writable directory, so it is
    created via mkstemp in the destination directory and renamed into place
    rather than opened by name.
    """
    directory = os.path.dirname(os.path.abspath(dst)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".mcp-roster.", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _warn(label: str, lines: Iterable[str]) -> None:
    for line in lines:
        print(f"[{label}] {line}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", help="tracked roster, e.g. .claude/mcp.json")
    ap.add_argument("dst", help="normalized roster to hand to --mcp-config")
    ap.add_argument("--root", required=True, help="repo root for ./ rewriting")
    ap.add_argument("--label", default="mcp-roster", help="stderr message prefix")
    args = ap.parse_args(argv)

    with open(args.src) as fh:
        data = json.load(fh)

    payload, dropped = normalize(data, args.root, os.environ)

    for server, missing in dropped:
        _warn(
            args.label,
            [
                f"WARN: dropping MCP server '{server}' — unset variable(s): "
                + ", ".join(missing),
                "      it would have been handed over with the literal ${...} "
                "text and failed silently.",
            ],
        )

    _write_private(args.dst, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
