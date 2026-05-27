"""CHIT signing module for graph-linker Neo4j writes.

Wraps node data in a CGP envelope and signs using canonical
pmoves.tools.chit_security.sign_cgp / verify_cgp.

Signing is additive and gated by the CHIT_SIGN_NEO4J env var —
existing functionality is never broken when the flag is off.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from pmoves.tools.chit_security import sign_cgp, verify_cgp

logger = logging.getLogger(__name__)

_CHIT_SIGNING_KEY = os.environ.get("CHIT_SIGNING_KEY") or os.environ.get("CHIT_PASSPHRASE")
CHIT_SIGN_NEO4J = os.environ.get("CHIT_SIGN_NEO4J", "false").lower() == "true"


def sign_neo4j_node(node_data: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap node data in a CGP envelope and sign it.

    Returns the original node_data unchanged when:
    - CHIT_SIGN_NEO4J is not enabled
    - No signing key is configured (dev mode — logs warning)

    When signing is active, adds a "sig" field with canonical HMAC.
    """
    if not CHIT_SIGN_NEO4J:
        return node_data

    passphrase = _CHIT_SIGNING_KEY
    if not passphrase:
        logger.warning(
            "CHIT_SIGN_NEO4J enabled but no CHIT_SIGNING_KEY/CHIT_PASSPHRASE set "
            "— publishing unsigned node (dev mode)"
        )
        return node_data

    try:
        return sign_cgp(node_data, passphrase=passphrase)
    except Exception as exc:
        logger.error("Failed to sign Neo4j node: %s", exc)
        return node_data


def verify_neo4j_node(node_data: Dict[str, Any]) -> bool:
    """Verify the CHIT signature on a Neo4j node.

    Returns:
        True  — signature valid, or signing disabled (pass-through)
        False — signature invalid or verification failed
    """
    if not CHIT_SIGN_NEO4J:
        return True

    passphrase = _CHIT_SIGNING_KEY
    if not passphrase:
        logger.warning(
            "CHIT_SIGN_NEO4J enabled but no signing key — skipping verification"
        )
        return True

    try:
        return verify_cgp(node_data, passphrase=passphrase)
    except Exception as exc:
        logger.error("Failed to verify Neo4j node signature: %s", exc)
        return False
