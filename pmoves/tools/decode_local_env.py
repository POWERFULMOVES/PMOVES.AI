#!/usr/bin/env python3
"""Decode base64-encoded secrets from local.env written by sync-secrets-spark.yml.

Values prefixed with 'b64:' are base64-decoded; others passed through.
"""
from __future__ import annotations
import argparse
import base64
import os
import sys
from pathlib import Path

DEFAULT_PATHS = [
    Path(os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))) / 'pmoves' / 'secrets' / 'local.env',
    Path('/pmoves/secrets/local.env'),
]


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE file, handling b64: prefixes."""
    result = {}
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        if val.startswith('b64:'):
            try:
                val = base64.b64decode(val[4:]).decode('utf-8')
            except Exception:
                pass  # keep raw value on decode failure
        result[key] = val
    return result


def export_env(vars_dict: dict[str, str], export: bool = False) -> None:
    """Print env vars for eval/sourcing."""
    prefix = 'export ' if export else ''
    for key, val in sorted(vars_dict.items()):
        # Use single-quote wrapping to preserve all special chars
        safe_val = val.replace("'", "'\\''")
        print(f"{prefix}{key}='{safe_val}'")


def main():
    parser = argparse.ArgumentParser(description='Decode local.env secrets')
    parser.add_argument('path', nargs='?', default=None, help='Path to local.env')
    parser.add_argument('--export', action='store_true', help='Prefix with export')
    parser.add_argument('--key', '-k', help='Get single key value')
    parser.add_argument('--shell', action='store_true', help='Output as shell eval-safe')
    args = parser.parse_args()

    path = Path(args.path) if args.path else None
    if not path:
        for p in DEFAULT_PATHS:
            if p.exists():
                path = p
                break
    if not path or not path.exists():
        print('Error: local.env not found', file=sys.stderr)
        sys.exit(1)

    vars_dict = parse_env_file(path)

    if args.key:
        val = vars_dict.get(args.key, '')
        if args.shell:
            safe_val = val.replace("'", "'\\''")
            print(f"'{safe_val}'")
        else:
            print(val)
    else:
        export_env(vars_dict, export=args.export)


if __name__ == '__main__':
    main()
