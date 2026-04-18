"""
scripts/chit_sign.py — Sign and optionally encrypt CGPs for PMOVES.AI demos.

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
_PMOVES_ROOT = _SCRIPT_DIR.parent.parent.parent
if str(_PMOVES_ROOT) not in sys.path:
    sys.path.insert(0, str(_PMOVES_ROOT))

from tools.chit_security import sign_cgp, encrypt_anchors  # noqa: E402
from tools.chit_common import canon  # noqa: E402


def process(cgp: Dict[str, Any], passphrase: str, encrypt: bool = False) -> Dict[str, Any]:
    """Sign and optionally encrypt a CGP using canonical chit_security implementation."""
    if encrypt:
        return encrypt_anchors(cgp, passphrase)
    return sign_cgp(cgp, passphrase)


def main():
    ap = argparse.ArgumentParser(description="Sign/encrypt CGPs via chit_security")
    ap.add_argument("--in", dest="inp", required=True, help="Input CGP JSON file")
    ap.add_argument("--out", dest="outp", required=True, help="Output signed CGP JSON file")
    ap.add_argument("--passphrase", dest="passphrase", default=None,
                    help="Passphrase (or set CHIT_PASSPHRASE env var)")
    ap.add_argument("--encrypt-anchors", dest="encrypt", action="store_true",
                    help="Encrypt anchor vectors with AES-GCM")
    args = ap.parse_args()

    passphrase = args.passphrase or os.environ.get("CHIT_PASSPHRASE", "")
    if not passphrase:
        ap.error("--passphrase or CHIT_PASSPHRASE env var is required")

    with open(args.inp, "r", encoding="utf-8") as f:
        cgp = json.load(f)

    result = process(cgp, passphrase, args.encrypt)

    out_dir = os.path.dirname(os.path.abspath(args.outp))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.outp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {args.outp}")


if __name__ == "__main__":
    main()
