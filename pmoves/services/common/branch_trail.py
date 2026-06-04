"""Branch lifecycle CHIT trail emit primitive (AGNOTE4482 §9.4).

Canonical emit primitive for branch lifecycle events. Publishes a signed
trail entry to NATS subject ``branch.<path-segments>.trail.v1`` where the
``<path-segments>`` are the branch name with ``/`` replaced by ``.``.

This is Layer 1 of the §9.4 design (see plan file for full architecture).
Layer 2 (CLI wrapper) and Layer 3 (HTTP gateway) wrap this module —
all three converge here.

Events tracked: ``create``, ``link_pr``, ``merge``, ``delete``.

Reuses (zero changes to upstream code):
    - pmoves.tools.sign_trail.build_payload — agent identity lookup + payload skeleton
    - pmoves.tools.chit_security.sign_cgp   — HMAC-SHA256 signing
    - pmoves.services.common.nats_client.publish_cgp — async NATS publish

Usage::

    from pmoves.services.common.branch_trail import emit
    import asyncio

    asyncio.run(emit(
        branch="feat/9.4-test",
        event="create",
        agent_id="claude-opus",
        committer="DARKXSIDE",
        sha="abc1234",
    ))
"""
from __future__ import annotations

import logging
from pmoves.services.common.env import get_secret
import re
import time
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Public API constants
# -----------------------------------------------------------------------

EVENT_TYPES: tuple[str, ...] = ("create", "link_pr", "merge", "delete")
"""Allowed values for the ``event`` argument to :func:`emit`."""

ECOSYSTEMS: tuple[str, ...] = ("github", "gitlab", "bitbucket", "gitea", "local")
"""Allowed values for the ``ecosystem`` argument."""

SUBJECT_VERSION = "v1"
"""Trailing version token in the NATS subject."""

# Branch names: git allows broad set, but we validate against NATS subject
# safety. Permit: alphanumerics, dash, underscore, dot, slash. Reject anything
# else (spaces, control chars, NATS-special tokens like ``*``/``>``).
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/]{0,254}$")


def encode_subject(branch: str) -> str:
    """Translate a branch name into its canonical NATS subject form.

    Replaces ``/`` with ``.`` so the path segments map onto NATS tokens,
    enabling wildcard subscriptions like ``branch.feat.>.trail.v1``.

    Raises:
        ValueError: if *branch* contains characters disallowed in NATS subjects.
    """
    if not _BRANCH_RE.match(branch):
        raise ValueError(
            f"branch name {branch!r} contains characters disallowed in NATS subjects "
            f"(allowed: alphanumerics, dot, dash, underscore, slash; first char "
            f"alphanumeric; max length 255)"
        )
    encoded = branch.replace("/", ".")
    if any(token == "" for token in encoded.split(".")):
        raise ValueError(
            f"branch name {branch!r} produces a disallowed empty NATS subject token "
            "(consecutive separators or trailing dot/slash are not allowed)"
        )
    return f"branch.{encoded}.trail.{SUBJECT_VERSION}"


def build_branch_event(
    branch: str,
    event: str,
    *,
    pr_url: Optional[str] = None,
    committer: Optional[str] = None,
    sha: Optional[str] = None,
    ecosystem: str = "github",
    runner: Optional[str] = None,
    ts: Optional[float] = None,
) -> dict[str, Any]:
    """Build the ``branch_event`` sub-object embedded in a signed trail payload.

    Validates inputs and produces a JSON-serializable dict matching the
    ``branch.lifecycle.v1`` shape (formal JSON schema lands in a contracts PR).
    """
    if event not in EVENT_TYPES:
        raise ValueError(f"event must be one of {EVENT_TYPES}, got {event!r}")
    if event in {"link_pr", "merge"} and not (pr_url or "").strip():
        raise ValueError(f"pr_url is required for {event!r} branch lifecycle events")
    if ecosystem not in ECOSYSTEMS:
        raise ValueError(f"ecosystem must be one of {ECOSYSTEMS}, got {ecosystem!r}")
    # Side-effect: validate branch up front so emit() fails fast before signing
    encode_subject(branch)

    return {
        "branch_name": branch,
        "event": event,
        "ts": ts if ts is not None else time.time(),
        "pr_url": pr_url,
        "committer": committer,
        "sha": sha,
        "ecosystem": ecosystem,
        "runner": runner,
    }


def build_payload(
    branch: str,
    event: str,
    agent_id: str,
    *,
    pr_url: Optional[str] = None,
    committer: Optional[str] = None,
    sha: Optional[str] = None,
    ecosystem: str = "github",
    runner: Optional[str] = None,
    phase: str = "Phase H",
    passphrase: Optional[str] = None,
    ts: Optional[float] = None,
) -> dict[str, Any]:
    """Build the full signed payload (without publishing).

    Returns a dict shaped like ``agent.graphiti.signed.v1`` with an extra
    ``branch_event`` field. When *passphrase* is provided (or available via
    ``CHIT_SIGNING_KEY``/``CHIT_PASSPHRASE`` env vars), the payload is HMAC-signed.

    Exposed publicly so the HTTP gateway and tests can inspect or re-sign
    payloads without invoking NATS.
    """
    # Lazy-import: keep module import lightweight when callers only want
    # encode_subject() (e.g. subscribers building wildcard patterns).
    from pmoves.tools.sign_trail import build_payload as _build_signed_skeleton
    from pmoves.tools.chit_security import sign_cgp

    branch_event = build_branch_event(
        branch,
        event,
        pr_url=pr_url,
        committer=committer,
        sha=sha,
        ecosystem=ecosystem,
        runner=runner,
        ts=ts,
    )

    # Reuse sign_trail's identity-lookup logic — produces the
    # agent.graphiti.signed.v1 skeleton with glyph/color/voice/etc.
    summary = f"branch.lifecycle.{event} on {branch}"
    payload = _build_signed_skeleton(agent_id, summary, phase=phase)
    payload["spec"] = "chit.cgp.v0.2"
    payload["type"] = "branch.lifecycle.v1"
    payload["branch_event"] = branch_event

    # Sign in-place when key material is available. We don't call
    # sign_trail.sign_trail() directly because it builds its own payload
    # without our branch_event field; sign_cgp() takes any dict.
    effective_passphrase = (
        passphrase
        or get_secret("CHIT_SIGNING_KEY")
        or get_secret("CHIT_PASSPHRASE")
    )
    if effective_passphrase:
        payload = sign_cgp(payload, effective_passphrase)
    else:
        logger.warning(
            "branch_trail.build_payload: no CHIT_SIGNING_KEY/CHIT_PASSPHRASE — "
            "payload will be unsigned"
        )

    return payload


async def emit(
    branch: str,
    event: str,
    agent_id: str,
    *,
    pr_url: Optional[str] = None,
    committer: Optional[str] = None,
    sha: Optional[str] = None,
    ecosystem: str = "github",
    runner: Optional[str] = None,
    phase: str = "Phase H",
    nats_url: str = "",
    passphrase: Optional[str] = None,
    ts: Optional[float] = None,
) -> bool:
    """Emit a CHIT-signed branch lifecycle trail entry to NATS.

    Args:
        branch: Branch name with original separators (e.g. ``feat/w6-bpm-nats``).
        event: One of :data:`EVENT_TYPES`.
        agent_id: Identity emitting the trail entry — must match a key in
            ``pmoves/config/agent_signatures.yaml`` for full identity stamping.
            Unknown agents fall back to a minimal payload (sign_trail behavior).
        pr_url: Associated PR URL. Required for ``link_pr`` and ``merge``.
        committer: Username/display name of the committer or PR author.
        sha: Commit SHA (7-40 hex chars).
        ecosystem: Source ecosystem (default ``github``).
        runner: Runner identifier for cross-runner dedup.
        phase: Project phase label (passed through to identity payload).
        nats_url: Override for ``NATS_URL`` env var.
        passphrase: Override for ``CHIT_SIGNING_KEY``/``CHIT_PASSPHRASE`` env vars.
        ts: Override timestamp; defaults to ``time.time()`` at build time.

    Returns:
        True if NATS publish succeeded, False otherwise. Failures are logged,
        not raised — emit is best-effort by design (a missing trail entry must
        not block the operation that triggered it).

    Raises:
        ValueError: if *branch* or *event* are invalid (fail-fast before signing).
    """
    from pmoves.services.common.nats_client import publish_cgp

    payload = build_payload(
        branch,
        event,
        agent_id,
        pr_url=pr_url,
        committer=committer,
        sha=sha,
        ecosystem=ecosystem,
        runner=runner,
        phase=phase,
        passphrase=passphrase,
        ts=ts,
    )
    subject = encode_subject(branch)
    return await publish_cgp(payload, subject, nats_url=nats_url)


__all__ = [
    "EVENT_TYPES",
    "ECOSYSTEMS",
    "SUBJECT_VERSION",
    "encode_subject",
    "build_branch_event",
    "build_payload",
    "emit",
]
