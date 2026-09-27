#!/usr/bin/env python3
"""Read ONE key, NEO4J_BIND, from a node-local env file, for the Makefile.

The Makefile exports the result into every $(DC) call, so a per-node publish
address (e.g. the node's tailnet address) takes effect WITHOUT putting the
node-local file on compose's --env-file list. That list deliberately excludes
the file under SUPABASE_RUNTIME=compose (Makefile, COMPOSE_ENV_FILES).
Without this, `make env-local-set KEY=NEO4J_BIND` was silently ignored and
Neo4j published on 0.0.0.0.

The file is PARSED, never sourced: no command substitution runs, and no
other key is read. The value is written to stdout only, which the Makefile
captures; it is never echoed to the terminal.

Usage:
  neo4j_bind_from_env_file.py <env-file>          print the value, if the key is present and valid
  neo4j_bind_from_env_file.py --check-file <path> validate a CALLER-supplied value that make wrote,
                                                  raw, to <path> with $(file ...); <path> is removed

The caller's value arrives through a file, never through a shell command
string: make never interpolates it into $(shell ...), so a value carrying a
quote or a make function can neither break the command nor run anything.

Exit codes:
  0  printed a valid value, or the key/value is absent or empty (prints nothing)
  2  malformed value: not an IP literal, or an IPv6 zone id (message WITHOUT the value)
  3  could not read the file, or it is not valid UTF-8
"""
from __future__ import annotations

import ipaddress
import os
import re
import sys

KEY = re.compile(r"^\s*(?:export\s+)?NEO4J_BIND\s*=(.*)$")


def normalise(raw: str) -> str:
    """'' for empty; the literal for an IPv4 address; [literal] for IPv6.

    Compose's short `host:published:target` port syntax needs an IPv6 host in
    brackets, so a bare IPv6 literal would render garbage.
    """
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1].strip()
    if not v:
        return ""
    bare = v[1:-1] if v.startswith("[") and v.endswith("]") else v
    ip = ipaddress.ip_address(bare)  # ValueError on anything that is not an IP literal
    if ip.version == 6 and ip.scope_id:
        # fe80::1%eth0: a zone id names an interface, it cannot be published on
        raise ValueError("IPv6 zone id")
    return f"[{ip.compressed}]" if ip.version == 6 else ip.compressed


def from_file(path: str) -> str:
    value = ""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            m = KEY.match(line.rstrip("\n"))
            if m:
                value = m.group(1)  # last assignment wins, as in a sourced file
    return normalise(value.split(" #", 1)[0])


def from_check_file(path: str) -> str:
    """A caller value, written raw by make's $(file >...) (which appends a newline)."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return normalise(raw[:-1] if raw.endswith("\n") else raw)


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 3 and argv[1] == "--check-file":
            value = from_check_file(argv[2])
        elif len(argv) == 2 and not argv[1].startswith("--"):
            value = from_file(argv[1])
        else:
            print("usage: neo4j_bind_from_env_file.py <env-file> | --check-file <path>", file=sys.stderr)
            return 3
    except UnicodeDecodeError:
        # Checked BEFORE ValueError, of which it is a subclass: this is an
        # unreadable file, not a malformed address.
        print("NEO4J_BIND source is not valid UTF-8; refusing (encoding error, value withheld)",
              file=sys.stderr)
        return 3
    except ValueError:
        print("NEO4J_BIND is not an IPv4/IPv6 address literal; refusing to pass it to compose "
              "(value withheld)", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"could not read the node-local env file for NEO4J_BIND ({exc.__class__.__name__})",
              file=sys.stderr)
        return 3
    if value:
        sys.stdout.write(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
