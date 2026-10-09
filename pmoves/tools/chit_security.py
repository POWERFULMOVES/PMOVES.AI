from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import os
import re
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
    2. CHIT_SIGNING_KEY_FILE  (file path containing the key)
    3. CHIT_PASSPHRASE   (legacy fallback — same key for signing + encryption)
    4. CHIT_PASSPHRASE_FILE   (file path containing the passphrase)

    Raises:
        RuntimeError: if none of the above are set.
    """
    val = None
    source = None
    for key in ("CHIT_SIGNING_KEY", "CHIT_PASSPHRASE"):
        v = os.environ.get(key)
        if v:
            val = v
            source = key
            break
        file_path = os.environ.get(f"{key}_FILE")
        if file_path:
            p = Path(file_path)
            if p.is_file():
                content = p.read_text(encoding="utf-8").strip()
                if content:
                    val = content
                    source = f"{key}_FILE"
                    break
    if not val:
        raise RuntimeError("CHIT_SIGNING_KEY or CHIT_PASSPHRASE env var (or _FILE) is required")
    if source == "CHIT_PASSPHRASE":
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


# ---------------------------------------------------------------------------
# Key id (`kid`) resolution
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS
# ---------------
# `sign_cgp()` has always stamped a `kid` into `sig`, but `verify_cgp()` never
# read it.  The field was write-only: every verifier resolved exactly one key
# via `_get_signing_key()`, so a signature naming any other key id was still
# checked against the single deployment key.  Consequence: per-agent signing
# keys were unreachable — if an agent set `CHIT_SIGNING_KEY_ID` plus its own
# key, its signatures would verify for nobody.  Every CHIT signature therefore
# authenticated the *deployment*, not the agent that produced it.
#
# This block makes verification resolve the key BY `kid`, so multiple keys can
# coexist and a per-agent signature becomes verifiable.  It issues no keys.
#
# CONFIGURATION (follows the existing `_get_signing_key()` pattern exactly —
# an env var, or an `_FILE` variant pointing at a file containing the value):
#
#     CHIT_SIGNING_KEY__<KID>        key material for that kid
#     CHIT_SIGNING_KEY__<KID>_FILE   path to a file containing it
#
# `<KID>` is the kid upper-cased with every non-alphanumeric run collapsed to
# a single underscore, e.g. kid `agent-b850-claude` -> `AGENT_B850_CLAUDE`, so
# the var is `CHIT_SIGNING_KEY__AGENT_B850_CLAUDE`.  The separator is a DOUBLE
# underscore precisely so that the pre-existing `CHIT_SIGNING_KEY_ID` and
# `CHIT_SIGNING_KEY_FILE` cannot be misparsed as per-kid entries.
#
# BACKWARDS COMPATIBILITY (mandatory — the existing trail history must keep
# verifying unchanged):
#   * A payload with NO `kid` at all resolves to the default key.
#   * `kid == DEFAULT_KID` ("chit-signing-v01"), which every signature in the
#     current trail history carries, resolves to the default key.
#   * The value of `CHIT_SIGNING_KEY_ID`, if set, also resolves to the default
#     key — that env var names the local default kid, and the key behind it is
#     still the deployment key until an operator provisions a per-kid one.
#   * With no per-kid key configured anywhere, resolution degrades to exactly
#     today's behaviour for every kid.
#
# FAIL-CLOSED (see `_kid_strict()`): once an operator provisions any per-kid
# key they have opted into per-agent identity, and a `kid` that cannot be
# resolved is then a HARD FAILURE.  It must never silently fall back to the
# default key and report valid — that is a check that cannot fail.
#
# NO KEY MATERIAL IS EVER LOGGED OR RAISED.  Everything below carries env var
# NAMES and kid names only.  `KidResolutionError` is constructed from names,
# never from a resolved value, so no error path can leak a key.

DEFAULT_KID = "chit-signing-v01"
_KID_ENV_PREFIX = "CHIT_SIGNING_KEY__"
_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}


class KidResolutionError(RuntimeError):
    """Raised when a `kid` names a signing key that cannot be resolved.

    Subclasses RuntimeError so that callers already catching the RuntimeError
    from `_get_signing_key()` keep working.

    Carries the kid and the env var NAMES that were consulted.  It never holds
    or formats key material, so this exception cannot leak a key even when it
    is logged, str()'d, or included in a traceback.
    """

    def __init__(self, kid: str, tried: List[str]) -> None:
        self.kid = kid
        self.tried = list(tried)
        super().__init__(
            f"no signing key configured for kid {kid!r}; "
            f"set one of: {', '.join(self.tried)}"
        )


class SignatureStatus(str, Enum):
    """Outcome of a signature check.

    Deliberately distinguishes "the MAC did not match" from "I could not
    resolve the key this signature names".  Collapsing those two into a single
    False loses exactly the distinction the fleet exit-code doctrine cares
    about (0 clean / 1 findings / 3 could-not-measure).
    """

    OK = "ok"
    """MAC verified against a key resolved from this signature's own `kid`."""

    OK_UNPINNED = "ok_unpinned"
    """MAC verified, but the key was NOT selected by `kid` — it came from the
    deployment default or an explicit passphrase argument.  The signature is
    authentic with respect to that key; it does NOT establish that the named
    agent produced it."""

    MISMATCH = "mismatch"
    """Key resolved, MAC did not match (tampered, wrong key, malformed b64)."""

    NO_SIGNATURE = "no_signature"
    """The payload carries no `sig` block."""

    UNRESOLVED_KID = "unresolved_kid"
    """The signature names a `kid` whose key is not configured here.  This is
    could-not-verify, NOT verified — and NOT a silent pass."""


@dataclass(frozen=True)
class VerifyResult:
    """Expressive result of `verify_cgp_detailed()`.

    `key_source` is an env var NAME (or the literal "argument"), never a value.
    `detail` is likewise built from names only.
    """

    status: SignatureStatus
    kid: str | None = None
    key_source: str | None = None
    detail: str = ""

    def __bool__(self) -> bool:
        # Only the two OK statuses are truthy.  An unresolved kid is falsy, so
        # even a caller that ignores `status` entirely still fails closed.
        return self.status in (SignatureStatus.OK, SignatureStatus.OK_UNPINNED)

    @property
    def verified(self) -> bool:
        return bool(self)

    @property
    def exit_code(self) -> int:
        """Fleet doctrine: 0 clean / 1 findings / 3 could-not-measure."""
        if bool(self):
            return 0
        if self.status is SignatureStatus.UNRESOLVED_KID:
            return 3
        return 1


def _kid_env_name(kid: str) -> str:
    """Normalize a kid into its per-kid env var name (no key material)."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", kid).strip("_").upper()
    return f"{_KID_ENV_PREFIX}{slug}"


def _configured_kid_env_names() -> List[str]:
    """Env var NAMES that provision a per-kid signing key. Values never read."""
    names = []
    for name, value in os.environ.items():
        if not name.startswith(_KID_ENV_PREFIX) or not value:
            continue
        names.append(name)
    return sorted(names)


def _kid_strict() -> bool:
    """Whether an unresolvable `kid` is a hard failure.

    `CHIT_KID_STRICT`:
      * truthy  -> always strict (end-state hardening: only explicitly
                   provisioned per-kid keys resolve; the default-kid aliases
                   are still honoured so trail history survives).
      * falsey  -> never strict (explicit migration escape hatch).
      * unset   -> AUTO: strict as soon as any per-kid key is configured.

    AUTO is what keeps constraint (fail closed) and constraint (do not break
    the existing history) from contradicting each other.  Today no per-kid key
    exists anywhere in the fleet, so AUTO is non-strict and behaviour is
    byte-identical to before this change.  The moment an operator provisions a
    per-agent key they have asserted that kids mean something, and from then on
    a kid we cannot resolve is a failure rather than a default-key fallback.
    The gate keys off OPERATOR CONFIGURATION, never off payload content, so a
    crafted payload cannot talk the verifier out of strict mode.
    """
    raw = (os.environ.get("CHIT_KID_STRICT") or "").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSEY:
        return False
    return bool(_configured_kid_env_names())


def _read_key_env(name: str) -> str | None:
    """Read a key from `name` or `{name}_FILE`, mirroring `_get_signing_key()`."""
    v = os.environ.get(name)
    if v:
        return v
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        p = Path(file_path)
        if p.is_file():
            content = p.read_text(encoding="utf-8").strip()
            if content:
                return content
    return None


def resolve_signing_key(kid: str | None) -> Tuple[str, str, bool]:
    """Resolve the signing key for `kid`.

    Returns `(key, source_name, pinned)` where `source_name` is an env var NAME
    and `pinned` is True only when the key was selected by `kid` itself.

    Raises:
        KidResolutionError: strict mode and the kid is not provisioned.
        RuntimeError: no signing key configured at all (from `_get_signing_key`).
    """
    # Legacy payloads carry no kid at all -> the default key, or the history
    # breaks.  Explicit, not incidental.
    if not kid:
        return _get_signing_key(), "CHIT_SIGNING_KEY", False

    env_name = _kid_env_name(kid)
    pinned = _read_key_env(env_name)
    if pinned is not None:
        return pinned, env_name, True

    # Default-key aliases: the historical constant every existing signature
    # carries, and whatever this deployment calls its default kid.
    default_kid = os.environ.get("CHIT_SIGNING_KEY_ID") or DEFAULT_KID
    if kid in (DEFAULT_KID, default_kid):
        return _get_signing_key(), "CHIT_SIGNING_KEY", False

    if _kid_strict():
        raise KidResolutionError(kid, [env_name, f"{env_name}_FILE"])

    # Single-key regime: exactly today's behaviour.  Reported as unpinned so a
    # caller can tell that the deployment key, not the named agent, is what
    # this signature actually authenticates.
    return _get_signing_key(), "CHIT_SIGNING_KEY", False


def sign_cgp(cgp: Dict[str, Any], passphrase: str | None = None, kid: str | None = None) -> Dict[str, Any]:
    """Sign `cgp` with HMAC-SHA256 and stamp `sig: {alg, kid, hmac}`.

    The kid is resolved FIRST and then used to select the key, so that a
    per-agent kid signs with that agent's key.  Without this, signing would
    still use the deployment key while stamping an agent's kid, producing an
    artifact that the (now kid-aware) verifier could never validate.

    Algorithm, canonicalisation and wire format are unchanged.
    """
    doc = json.loads(json.dumps(cgp))  # deep copy
    kid = kid or os.environ.get("CHIT_SIGNING_KEY_ID") or DEFAULT_KID
    if passphrase is not None:
        signing_key = passphrase
    else:
        signing_key, _source, _pinned = resolve_signing_key(kid)
    meta = {"alg": "HMAC-SHA256", "kid": kid}
    doc_nosig = json.loads(json.dumps(doc))
    doc_nosig.pop("sig", None)
    mac = hmac.new(signing_key.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    doc["sig"] = {**meta, "hmac": base64.b64encode(mac).decode("ascii")}
    return doc


def verify_cgp_detailed(cgp: Dict[str, Any], passphrase: str | None = None) -> VerifyResult:
    """Verify `cgp`, resolving the key by the `kid` the signature names.

    Returns a `VerifyResult` that distinguishes "MAC mismatch" (a finding)
    from "could not resolve the key this signature names" (could-not-measure).
    `verify_cgp()` collapses both to False, which is fail-closed but loses the
    distinction; prefer this function where the difference matters.

    Never logs, raises, or returns key material.
    """
    if not isinstance(cgp, dict) or "sig" not in cgp:
        return VerifyResult(
            status=SignatureStatus.NO_SIGNATURE,
            detail="payload carries no sig block",
        )
    sig = cgp["sig"] if isinstance(cgp.get("sig"), dict) else {}
    kid = sig.get("kid") or None
    mac_b64 = sig.get("hmac", "")

    if passphrase is not None:
        signing_key = passphrase
        source = "argument"
        pinned = False
    else:
        try:
            signing_key, source, pinned = resolve_signing_key(kid)
        except KidResolutionError as exc:
            # Fail closed.  Do NOT fall back to the default key: reporting
            # "valid" here would be a check that cannot fail.  `exc` is built
            # from env var names only, so this detail cannot leak a key.
            return VerifyResult(
                status=SignatureStatus.UNRESOLVED_KID,
                kid=kid,
                key_source=None,
                detail=str(exc),
            )

    doc_nosig = json.loads(json.dumps(cgp))
    doc_nosig.pop("sig", None)
    mac2 = hmac.new(signing_key.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
    try:
        mac1 = base64.b64decode(mac_b64)
    except Exception:
        return VerifyResult(
            status=SignatureStatus.MISMATCH,
            kid=kid,
            key_source=source,
            detail="sig.hmac is not valid base64",
        )
    if not hmac.compare_digest(mac1, mac2):
        return VerifyResult(
            status=SignatureStatus.MISMATCH,
            kid=kid,
            key_source=source,
            detail=f"HMAC mismatch under key from {source}",
        )
    if pinned:
        return VerifyResult(
            status=SignatureStatus.OK,
            kid=kid,
            key_source=source,
            detail=f"verified against key pinned to kid {kid!r} via {source}",
        )
    return VerifyResult(
        status=SignatureStatus.OK_UNPINNED,
        kid=kid,
        key_source=source,
        detail=(
            f"verified against {source}; kid {kid!r} is not pinned to its own key, "
            "so this authenticates the deployment rather than the named agent"
        ),
    )


def verify_cgp(cgp: Dict[str, Any], passphrase: str | None = None) -> bool:
    """Boolean signature check. Fail-closed on an unresolvable `kid`.

    RETURN TYPE IS DELIBERATELY STILL `bool`.  Returning `VerifyResult` here
    would be more expressive but is a live foot-gun: a dataclass is truthy by
    default, so every existing `if verify_cgp(...)` caller would silently
    become always-true — the exact defect class this change exists to remove.
    Existing tests also assert `is True` / `is False`, which a non-bool breaks
    for no safety gain.  Callers wanting the three-way distinction should call
    `verify_cgp_detailed()`, whose `VerifyResult.__bool__` is itself defined so
    that an unresolved kid is falsy.
    """
    return bool(verify_cgp_detailed(cgp, passphrase))


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
    # Pass `passphrase` through rather than a pre-resolved default key: with
    # per-kid resolution live, eagerly resolving here would force the default
    # key even for a signature that names an agent kid.
    return sign_cgp(doc, passphrase=passphrase, kid=kid)


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
    "verify_cgp_detailed",
    "VerifyResult",
    "SignatureStatus",
    "KidResolutionError",
    "resolve_signing_key",
    "DEFAULT_KID",
    "encrypt_anchors",
    "decrypt_anchors",
    "_get_signing_key",
    "_get_encryption_key",
]
