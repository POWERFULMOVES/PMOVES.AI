"""The allowed_signers keyring must be derived from the cards, not maintained.

SIGNING_IDENTITY_CARDS.md describes CI verify as "branch protection runs
`git verify-commit` against `allowed_signers`", but no such file existed — that
half of the design was never runnable, which is why review of #2668 could ask
for a signature that nothing could have checked.

A hand-maintained keyring is worse than none: it drifts from the registry it
represents, and verification keeps succeeding against the wrong set. So the file
is generated and drift-gated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import build_allowed_signers as bas  # noqa: E402


def _card(agent, line=None, active=True):
    c = {"h": {"agent_id": agent}, "active": active, "ml": {}}
    if line:
        c["ml"]["ssh_allowed_signers_line"] = line
    return c


GOOD = "alice ssh-ed25519 AAAAKEY alice@example.com"


def test_only_cards_with_a_key_appear():
    text, _ = bas.render([_card("alice", GOOD), _card("bob")])
    body = [l for l in text.splitlines() if l and not l.startswith("#")]
    assert body == [GOOD], body


def test_inactive_card_is_not_trusted():
    """Deactivating a card must actually revoke it, not merely annotate it."""
    text, warns = bas.render([_card("alice", GOOD, active=False)])
    body = [l for l in text.splitlines() if l and not l.startswith("#")]
    assert body == []
    assert any("inactive" in w for w in warns), warns


def test_non_email_principal_is_flagged():
    """git matches the principal against the committer identity. An agent_id
    principal parses fine and then never matches — verification fails closed for
    a reason invisible in the file."""
    _, warns = bas.render([_card("alice", "alice ssh-ed25519 AAAAKEY x@y.z")])
    assert any("not an email" in w for w in warns), warns


def test_email_principal_is_not_flagged():
    _, warns = bas.render([_card("alice", "alice@example.com ssh-ed25519 AAAAKEY c")])
    assert not any("not an email" in w for w in warns), warns


def test_output_is_deterministic():
    """Sorted, so the drift gate compares content and not dict ordering."""
    a, b = _card("zeta", "zeta ssh-ed25519 K1 z@x"), _card("alpha", "alpha ssh-ed25519 K2 a@x")
    one, _ = bas.render([a, b])
    two, _ = bas.render([b, a])
    assert one == two
    body = [l.split()[0] for l in one.splitlines() if l and not l.startswith("#")]
    assert body == sorted(body), body


def test_header_names_the_generator_and_the_source():
    text, _ = bas.render([_card("alice", GOOD)])
    assert "do not hand-edit" in text
    assert "signing_identity_cards.yaml" in text
    assert "allowed-signers" in text


def test_real_registry_renders():
    """The committed cards must produce a keyring — a smoke test against drift
    in the card schema itself."""
    text, _ = bas.render(bas._load_cards())
    body = [l for l in text.splitlines() if l and not l.startswith("#")]
    assert body, "no trusted keys rendered from the real registry"
    for line in body:
        parts = line.split()
        assert len(parts) >= 3, line
        assert parts[1].startswith(("ssh-", "ecdsa-", "sk-")), line
