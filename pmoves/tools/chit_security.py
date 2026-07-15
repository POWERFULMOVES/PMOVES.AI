from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import os
import struct
from pathlib import Path
from typing import Any, Dict, List

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
    from cryptography.hazmat.primitives import hashes  # type: ignore
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False


from pmoves.tools.chit_common import canon as _canon  # noqa: F401 — re-export for backward compat

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key separation: CHIT_SIGNING_KEY / CHIT_ENCRYPTION_KEY vs CHIT_PASSPHRASE
# ---------------------------------------------------------------------------

def _get_signing_key() -> str:
    """Return the HMAC signing key from environment or file.

    Priority:
    1. CHIT_SIGNING_KEY  (recommended — separate key for signing)
    2. CHIT_PASSPHRASE   (legacy fallback — same key for signing + encryption)
    3. CHIT_SIGNING_KEY_FILE  (file path containing the key)
    4. CHIT_PASSPHRASE_FILE   (file path containing the passphrase)

    Raises:
        RuntimeError: if none of the above are set.
    """
    for key in ("CHIT_SIGNING_KEY", "CHIT_PASSPHRASE"):
        val = os.environ.get(key)
        if val:
            break
        file_path = os.environ.get(f"{key}_FILE")
        if file_path:
            p = Path(file_path)
            if p.is_file():
                val = p.read_text(encoding="utf-8").strip()
                if val:
                    break
    else:
        raise RuntimeError("CHIT_SIGNING_KEY or CHIT_PASSPHRASE env var (or _FILE) is required")
    if not os.environ.get("CHIT_SIGNING_KEY") and os.environ.get("CHIT_PASSPHRASE"):
        logger.warning(
            "Using CHIT_PASSPHRASE for signing — recommend setting CHIT_SIGNING_KEY "
            "separately for key separation"
        )
    return val


def _get_encryption_key() -> str:
    """Return the AES encryption key from environment.

    Priority:
    1. CHIT_ENCRYPTION_KEY  (recommended — separate key for encryption)
    2. CHIT_PASSPHRASE       (legacy fallback — same key for signing + encryption)

    Raises:
        RuntimeError: if neither env var is set.
    """
    key = os.environ.get("CHIT_ENCRYPTION_KEY") or os.environ.get("CHIT_PASSPHRASE", "")
    if not key:
        raise RuntimeError("CHIT_ENCRYPTION_KEY or CHIT_PASSPHRASE env var is required")
    if not os.environ.get("CHIT_ENCRYPTION_KEY") and os.environ.get("CHIT_PASSPHRASE"):
        logger.warning(
            "Using CHIT_PASSPHRASE for encryption — recommend setting CHIT_ENCRYPTION_KEY "
            "separately for key separation"
        )
    return key


def sign_cgp(cgp: Dict[str, Any], passphrase: str | None = None, kid: str | None = None) -> Dict[str, Any]:
    signing_key = passphrase or _get_signing_key()
    doc = json.loads(json.dumps(cgp))  # deep copy
    kid = kid or os.environ.get("CHIT_SIGNING_KEY_ID") or "chit-signing-v01"
    meta = {"alg": "HMAC-SHA256", "kid": kid}
    doc_nosig = json.loads(json.dumps(doc))
    doc_nosig.pop("sig", None)
    mac = hmac.new(signing_key.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    doc["sig"] = {**meta, "hmac": base64.b64encode(mac).decode("ascii")}
    return doc


def verify_cgp(cgp: Dict[str, Any], passphrase: str | None = None) -> bool:
    signing_key = passphrase or _get_signing_key()
    if "sig" not in cgp:
        return False
    sig = cgp["sig"]
    mac_b64 = sig.get("hmac", "")
    doc_nosig = json.loads(json.dumps(cgp))
    doc_nosig.pop("sig", None)
    mac2 = hmac.new(signing_key.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return False
    return hmac.compare_digest(mac1, mac2)


def _derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=length, salt=salt, iterations=600_000)
    return kdf.derive(passphrase.encode("utf-8"))


def _pack_floats(arr: List[float]) -> bytes:
    import numpy as np
    a = (np.asarray(arr, dtype="float32")).tobytes()
    return struct.pack(">I", len(arr)) + a


def _unpack_floats(buf: bytes) -> List[float]:
    import numpy as np
    n = struct.unpack(">I", buf[:4])[0]
    a = np.frombuffer(buf[4:], dtype="float32", count=n)
    return a.astype(float).tolist()


def encrypt_anchors(cgp: Dict[str, Any], passphrase: str | None = None, kid: str | None = None) -> Dict[str, Any]:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    encryption_key = passphrase or _get_encryption_key()
    signing_key = passphrase or _get_signing_key()
    doc = json.loads(json.dumps(cgp))
    salt = os.urandom(16)
    key = _derive_key(encryption_key, salt, 32)
    for s in doc.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            if "anchor" not in const:
                continue
            plain = _pack_floats(const["anchor"])  # type: ignore[arg-type]
            iv = os.urandom(12)
            aead = AESGCM(key)
            aad = _canon({"id": const.get("id", "")})
            ct = aead.encrypt(iv, plain, aad)
            const.pop("anchor", None)
            const["anchor_enc"] = {
                "alg": "AES-GCM",
                "iv": base64.b64encode(iv).decode("ascii"),
                "salt": base64.b64encode(salt).decode("ascii"),
                "ct": base64.b64encode(ct).decode("ascii"),
            }
    return sign_cgp(doc, passphrase=signing_key, kid=kid)


def decrypt_anchors(cgp: Dict[str, Any], passphrase: str | None = None) -> Dict[str, Any]:
    encryption_key = passphrase or _get_encryption_key()
    doc = json.loads(json.dumps(cgp))
    has_encrypted_anchors = any(
        const.get("anchor_enc")
        for s in doc.get("super_nodes", []) or []
        for const in s.get("constellations", []) or []
    )
    if not has_encrypted_anchors:
        return doc
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    for s in doc.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            enc = const.get("anchor_enc")
            if not enc:
                continue
            iv = base64.b64decode(enc["iv"])
            salt = base64.b64decode(enc["salt"])
            ct = base64.b64decode(enc["ct"])
            key = _derive_key(encryption_key, salt, 32)
            aead = AESGCM(key)
            aad = _canon({"id": const.get("id", "")})
            pt = aead.decrypt(iv, ct, aad)
            const.pop("anchor_enc", None)
            const["anchor"] = _unpack_floats(pt)
    return doc


__all__ = [
    "sign_cgp",
    "verify_cgp",
    "encrypt_anchors",
    "decrypt_anchors",
    "_get_signing_key",
    "_get_encryption_key",
]
