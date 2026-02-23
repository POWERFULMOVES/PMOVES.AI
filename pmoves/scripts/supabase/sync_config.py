#!/usr/bin/env python3
"""Keep Supabase config entrypoint stable for Make targets.

This project currently relies on Supabase CLI defaults for runtime switching.
The script intentionally validates the target config path and exits cleanly.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to supabase/config.toml")
    parser.add_argument("--runtime", default="cli", help="Desired runtime marker (cli|compose)")
    args = parser.parse_args()

    config = Path(args.config)
    if not config.exists():
        raise FileNotFoundError(f"Supabase config not found: {config}")

    # Intentionally no mutation for now; this keeps historical make workflows working.
    print(f"Supabase config present: {config} (runtime={args.runtime})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
