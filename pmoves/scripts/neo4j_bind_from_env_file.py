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
  neo4j_bind_from_env_file.py <env-file>   print the value, if the key is present and valid
  neo4j_bind_from_env_file.py --check      validate $NEO4J_BIND_CHECK (a caller-supplied value)

Exit codes:
  0  printed a valid value, or the key is absent/empty (prints nothing)
  2  malformed value (message on stderr WITHOUT the value)
  3  could not read the file
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
    return f"[{ip.compressed}]" if ip.version == 6 else ip.compressed


def from_file(path: str) -> str:
    value = ""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            m = KEY.match(line.rstrip("\n"))
            if m:
                value = m.group(1)  # last assignment wins, as in a sourced file
    return normalise(value.split(" #", 1)[0])


def main(argv: list[str]) -> int:
    try:
        if argv[1:] == ["--check"]:
            value = normalise(os.environ.get("NEO4J_BIND_CHECK", ""))
        elif len(argv) == 2:
            value = from_file(argv[1])
        else:
            print("usage: neo4j_bind_from_env_file.py <env-file> | --check", file=sys.stderr)
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
