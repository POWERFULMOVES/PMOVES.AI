"""Minimal HMAC-SHA256 CGP signer vendored for the flute-gateway runtime.

This module mirrors the signing surface of `pmoves.tools.chit_security`
(specifically `sign_cgp` and `verify_cgp`) but lives inside flute-gateway
so the Docker image does not need the full `pmoves` package on its
PYTHONPATH. The canonical security module imports `pmoves.tools.chit_common`
which is not copied into the flute-gateway container.

`tests/test_geometry_bridge.py::test_sign_byte_equivalence_with_canonical`
guards against drift: it imports both this vendored signer and the
canonical `pmoves.tools.chit_security.sign_cgp` and asserts they produce
byte-identical signatures on the same input. If you change one, change
the other to match — or accept that the test will fail.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from pmoves.services.common.env import get_secret
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _canon(obj: Any) -> bytes:
    """Canonical JSON for signing — must match `pmoves.tools.chit_common.canon`."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signing_key() -> str:
    """Resolve the HMAC signing key from env (matches canonical priority)."""
    return get_secret("CHIT_SIGNING_KEY") or get_secret("CHIT_PASSPHRASE", "")


def sign_cgp(
    cgp: Dict[str, Any],
    passphrase: str | None = None,
    kid: str | None = None,
) -> Dict[str, Any]:
    """Sign a CGP packet with HMAC-SHA256.

    Adds `sig: {alg, kid, hmac}` to a deep copy of `cgp` and returns it.
    Raises `RuntimeError` if no key is provided and neither
    `CHIT_SIGNING_KEY` nor `CHIT_PASSPHRASE` is set in env.
    """
    key = passphrase or _signing_key()
    if not key:
        raise RuntimeError(
            "CHIT_SIGNING_KEY or CHIT_PASSPHRASE env var required for sign_cgp()"
        )
    doc = json.loads(json.dumps(cgp))  # deep copy
    kid = kid or hashlib.sha256(key.encode()).hexdigest()[:16]
    doc_nosig = json.loads(json.dumps(doc))
    doc_nosig.pop("sig", None)
    mac = hmac.new(key.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    doc["sig"] = {
        "alg": "HMAC-SHA256",
        "kid": kid,
        "hmac": base64.b64encode(mac).decode("ascii"),
    }
    return doc


def verify_cgp(cgp: Dict[str, Any], passphrase: str | None = None) -> bool:
    """Verify HMAC signature on a CGP packet."""
    key = passphrase or _signing_key()
    if not key:
        return False
    if "sig" not in cgp:
        return False
    mac_b64 = cgp["sig"].get("hmac", "")
    doc_nosig = json.loads(json.dumps(cgp))
    doc_nosig.pop("sig", None)
    mac2 = hmac.new(key.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return False
    return hmac.compare_digest(mac1, mac2)
