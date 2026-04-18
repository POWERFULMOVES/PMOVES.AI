"""Sign and optionally encrypt CGPs for PMOVES.AI demos.

Delegates ALL crypto to chit_security.py (the canonical CHIT implementation per CGP v1.0 spec).
This module provides only CLI convenience — no independent crypto.

Usage:
  python scripts/chit_sign.py --in tests/data/cgp_fixture.json --out data/cgp_signed.json \
         --passphrase "secret" --encrypt-anchors
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Resolve imports for chit_security
_SCRIPT_DIR = Path(__file__).resolve().parent
_PMOVES_ROOT = _SCRIPT_DIR.parent.parent.parent.parent.parent
if str(_PMOVES_ROOT) not in sys.path:
    sys.path.insert(0, str(_PMOVES_ROOT))

from pmoves.tools.chit_security import sign_cgp, encrypt_anchors  # noqa: E402
from pmoves.tools.chit_common import canon  # noqa: E402


def sign_cgp_file(cgp: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    """Sign a CGP using canonical chit_security implementation."""
    return sign_cgp(cgp, passphrase)


def encrypt_anchors_in_cgp(cgp: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    """Encrypt anchor vectors using canonical chit_security implementation."""
    return encrypt_anchors(cgp, passphrase)


def main():
    parser = argparse.ArgumentParser(description="Sign/encrypt CGPs via chit_security")
    parser.add_argument("--in", dest="inp", required=True, help="Input CGP JSON file")
    parser.add_argument("--out", dest="outp", required=True, help="Output signed CGP JSON file")
    parser.add_argument("--passphrase", default=os.environ.get("CHIT_PASSPHRASE", ""),
                        help="Passphrase for signing/encryption (or set CHIT_PASSPHRASE)")
    parser.add_argument("--encrypt-anchors", action="store_true", help="Encrypt anchor vectors")
    args = parser.parse_args()

    if not args.passphrase:
        parser.error("--passphrase or CHIT_PASSPHRASE env var is required")

    with open(args.inp) as f:
        cgp = json.load(f)

    cgp = sign_cgp_file(cgp, args.passphrase)

    if args.encrypt_anchors:
        cgp = encrypt_anchors_in_cgp(cgp, args.passphrase)

    os.makedirs(os.path.dirname(os.path.abspath(args.outp)), exist_ok=True)
    with open(args.outp, "w") as f:
        json.dump(cgp, f, indent=2)

    print(f"Signed CGP written to {args.outp}")


if __name__ == "__main__":
    main()
