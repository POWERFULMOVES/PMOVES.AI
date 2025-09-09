from __future__ import annotations

import base64
import hmac
import hashlib
import json
import os
import struct
from typing import Any, Dict, List

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
    from cryptography.hazmat.primitives import hashes  # type: ignore
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False


def _canon(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_cgp(cgp: Dict[str, Any], passphrase: str, kid: str | None = None) -> Dict[str, Any]:
    doc = json.loads(json.dumps(cgp))  # deep copy
    kid = kid or hashlib.sha256(passphrase.encode()).hexdigest()[:16]
    meta = {"alg": "HMAC-SHA256", "kid": kid}
    doc_nosig = json.loads(json.dumps(doc))
    doc_nosig.pop("sig", None)
    mac = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    doc["sig"] = {**meta, "hmac": base64.b64encode(mac).decode("ascii")}
    return doc


def verify_cgp(cgp: Dict[str, Any], passphrase: str) -> bool:
    if "sig" not in cgp:
        return False
    sig = cgp["sig"]
    mac_b64 = sig.get("hmac", "")
    doc_nosig = json.loads(json.dumps(cgp))
    doc_nosig.pop("sig", None)
    mac2 = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return False
    return hmac.compare_digest(mac1, mac2)


def _derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=length, salt=salt, iterations=100_000)
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


def encrypt_anchors(cgp: Dict[str, Any], passphrase: str, kid: str | None = None) -> Dict[str, Any]:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    doc = json.loads(json.dumps(cgp))
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt, 32)
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
    return sign_cgp(doc, passphrase, kid=kid)


def decrypt_anchors(cgp: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    doc = json.loads(json.dumps(cgp))
    for s in doc.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            enc = const.get("anchor_enc")
            if not enc:
                continue
            iv = base64.b64decode(enc["iv"])
            salt = base64.b64decode(enc["salt"])
            ct = base64.b64decode(enc["ct"])
            key = _derive_key(passphrase, salt, 32)
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
]

