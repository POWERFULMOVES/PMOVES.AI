"""CHIT signing for graph-linker Neo4j writes. Fail-closed.

Every write graph-linker makes is signed with the canonical
`pmoves.tools.chit_security.sign_cgp`, and the signature is PERSISTED on the
node(s) the write creates, as three flat properties (Neo4j property values
cannot be maps):

    chit_sig        base64 HMAC-SHA256 over the canonical signed document
    chit_kid        the key id the signature names
    chit_signed_at  ISO-8601 UTC timestamp, itself covered by the MAC

The signed document is `{"writer", "signed_at", "params"}`, where `params` is
the exact Cypher parameter dict of the write.  `verify_write()` rebuilds that
document, so a write can be re-verified from the event it came from.

FAIL-CLOSED.  No key, an unresolvable kid, or a parameter dict that cannot be
canonicalised means NO WRITE: `sign_write()` raises `ChitSigningError`, the
failure is counted on `graph_linker_chit_sign_failures_total{reason}`, and the
NATS handler dead-letters the message.  There is no unsigned dev mode — the
previous version returned the dict unsigned on a missing key and its signature
was passed to Cypher as an unused parameter, so nothing was ever persisted.

Precedents: consciousness-service `chr_algorithm.py:119-126,486-492` and
`main.py:45-50` (refuse when no key under CHIT_REQUIRE_SIGNATURE), hi-rag-v2
`routes/geometry.py:147-157` (refuse at the boundary).  graph-linker is
stricter than both: the refusal is unconditional, because a provenance writer
that can write unsigned is the defect this module exists to remove.

The key is resolved per call through `resolve_signing_key` (via `sign_cgp`
with no `passphrase=`), so `*_FILE` variants and per-kid keys work and a key
rotation does not need a restart.  Never logs or returns key material.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from prometheus_client import Counter

from pmoves.tools.chit_security import (
    DEFAULT_KID,
    KidResolutionError,
    VerifyResult,
    resolve_signing_key,
    sign_cgp,
    verify_cgp_detailed,
)

logger = logging.getLogger(__name__)

WRITER_ID = "graph-linker"
CHIT_FIELDS = ("chit_sig", "chit_kid", "chit_signed_at")

CHIT_SIGN_FAILURES = Counter(
    "graph_linker_chit_sign_failures_total",
    "Neo4j writes refused because they could not be CHIT-signed",
    ["reason"],
)


class ChitSigningError(RuntimeError):
    """A write was refused because it could not be signed.

    `reason` is one of: no_key, unresolved_kid, unserializable, sign_error.
    Built from reason codes and exception TYPE names only — never key material.
    """

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(f"CHIT signing failed ({reason}): {detail}; write refused")


def _signed_doc(params: Dict[str, Any], signed_at: str) -> Dict[str, Any]:
    return {"writer": WRITER_ID, "signed_at": signed_at, "params": params}


def sign_write(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return `params` plus `chit_sig`, `chit_kid`, `chit_signed_at`.

    Raises:
        ChitSigningError: the write must not happen.  Already counted.
    """
    signed_at = datetime.now(timezone.utc).isoformat()
    try:
        # Canonicalise first so a non-JSON value is reported as itself,
        # not as a signing fault.
        json.dumps(params)
        signed = sign_cgp(_signed_doc(params, signed_at))
    except KidResolutionError as exc:
        reason, detail = "unresolved_kid", str(exc)  # names only, no key
    except (TypeError, ValueError) as exc:
        reason, detail = "unserializable", type(exc).__name__
    except RuntimeError as exc:
        # _get_signing_key raises RuntimeError naming the env vars it tried.
        reason, detail = "no_key", str(exc)
    except Exception as exc:  # noqa: BLE001 - counted, logged and re-raised
        reason, detail = "sign_error", type(exc).__name__
    else:
        sig = signed["sig"]
        return {
            **params,
            "chit_sig": sig["hmac"],
            "chit_kid": sig["kid"],
            "chit_signed_at": signed_at,
        }

    CHIT_SIGN_FAILURES.labels(reason=reason).inc()
    logger.error("graph-linker CHIT signing failed (%s): %s — write refused", reason, detail)
    raise ChitSigningError(reason, detail)


def verify_write(signed_params: Dict[str, Any]) -> VerifyResult:
    """Verify a dict produced by `sign_write` (or rebuilt from its event).

    Returns `verify_cgp_detailed`'s result, so callers can tell OK from
    OK_UNPINNED (deployment key, not a per-writer key), MISMATCH,
    UNRESOLVED_KID and NO_SIGNATURE.
    """
    params = {k: v for k, v in signed_params.items() if k not in CHIT_FIELDS}
    doc = _signed_doc(params, signed_params.get("chit_signed_at", ""))
    if signed_params.get("chit_sig"):
        doc["sig"] = {
            "alg": "HMAC-SHA256",
            "kid": signed_params.get("chit_kid"),
            "hmac": signed_params["chit_sig"],
        }
    return verify_cgp_detailed(doc)


def signing_status() -> Tuple[bool, str]:
    """Whether a signing key resolves right now, for /ready.  No key material."""
    kid = os.environ.get("CHIT_SIGNING_KEY_ID") or DEFAULT_KID
    try:
        resolve_signing_key(kid)
    except KidResolutionError:
        return False, "unresolved_kid"
    except RuntimeError:
        return False, "no_key"
    return True, "ok"
