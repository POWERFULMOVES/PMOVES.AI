#!/usr/bin/env python3
"""Encode environment secrets into a CHIT Geometry Packet (CGP)."""

from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PMOVES_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PMOVES_DIR / "env.shared"
DEFAULT_OUT = PMOVES_DIR / "data/chit/env.cgp.json"

from pmoves.chit import encode_secret_map


def load_env_file(path: Path, keys: set[str] | None = None) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(path)
    secrets: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if keys and key not in keys:
            continue
        # A value that is NOTHING BUT a trailing comment is not a value.
        #
        # env.shared.example shipped lines like
        #     PMOVES_BRIDGE_TOKEN=   # REQUIRED - generate: openssl rand -hex 32
        # and this loader returned the 80-character comment as the secret. It is
        # non-empty, so secrets_sync._first_usable accepted it and build_outputs
        # emitted a PUBLIC TEMPLATE STRING into env.tier-worker while the
        # required-secret check reported the funnel as successful. Three REQUIRED
        # keys were exposed this way -- PMOVES_BRIDGE_TOKEN, PMOVES_BRIDGE_API_KEY
        # and GATE_API_KEY -- none of which brand_defaults mints, so nothing
        # downstream ever overwrote the placeholder. (NATS_EVENT_BUS_TOKEN had the
        # same line shape but is minted, which is why it never surfaced.)
        #
        # Only the unambiguous case is handled here: the value, once stripped, is
        # entirely a comment. `KEY=real  # note` is deliberately left alone -- a
        # secret may legitimately contain '#', and guessing would corrupt it.
        # The template no longer emits that shape, which is where it belongs.
        secrets[key] = "" if value.strip().startswith("#") else value
    if not secrets:
        raise RuntimeError(f"{path} did not contain any key=value pairs")
    return secrets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        type=Path,
        help=f"Environment file to encode (default: {DEFAULT_ENV_FILE})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        type=Path,
        help=f"Output CGP JSON path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--namespace",
        default="pmoves.secrets",
        help="Namespace stored in CGP meta",
    )
    parser.add_argument(
        "--description",
        default="PMOVES shared secrets",
        help="Human-friendly description recorded in meta.summary",
    )
    parser.add_argument(
        "--keys",
        nargs="*",
        default=None,
        help="Optional subset of keys to export",
    )
    parser.add_argument(
        "--no-cleartext",
        dest="include_cleartext",
        action="store_false",
        help="Store values using hex encoding instead of cleartext",
    )
    parser.set_defaults(include_cleartext=True)

    args = parser.parse_args()

    secrets = load_env_file(args.env_file, set(args.keys) if args.keys else None)
    cgp = encode_secret_map(
        secrets,
        namespace=args.namespace,
        description=args.description,
        include_cleartext=args.include_cleartext,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(cgp, indent=2), encoding="utf-8")
    print(f"CGP written to {args.out}")


if __name__ == "__main__":
    main()
