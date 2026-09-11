"""Tests for pmoves/tools/cipher_identity.py.

Every assertion here is pinned to a line of `Pmoves-cipher/src/pmoves/auth.ts`,
because the whole tool is a claim about what that file does with a bearer:

  auth.ts:46   if (!token.startsWith('cipher_')) { ... }
  auth.ts:49   return {agentId: 'bootstrap', ...}
  auth.ts:60   const uuidHex = token.slice(7)
  auth.ts:106  if (!legacyToken && skipIfUnset) { req.agentId = undefined }

If cipher's auth changes, these tests should fail loudly rather than let the
launcher keep announcing an identity carry that no longer exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

TOOLS = Path(__file__).resolve().parents[3] / "pmoves" / "tools"
sys.path.insert(0, str(TOOLS))

import cipher_identity as ci  # noqa: E402


def _cards(tmp_path: Path, entries) -> Path:
    """entries: iterable of (agent_id, active)."""
    doc = {
        "schema_version": "1.0.0",
        "cards": [
            {
                "card_id": f"00000000-0000-4000-8000-{i:012d}",
                "active": active,
                "ml": {"primary_method": "github-app"},
                "h": {"agent_id": agent, "role": "agent"},
            }
            for i, (agent, active) in enumerate(entries, start=1)
        ],
    }
    p = tmp_path / "cards.yaml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# classify_token — the seven-character fork
# ---------------------------------------------------------------------------

def test_minted_prefix_selects_per_agent_mode():
    # auth.ts:46 takes the Supabase branch only when the prefix is present.
    assert ci.classify_token("cipher_0123456789abcdef") == ci.MODE_PER_AGENT


def test_token_without_prefix_is_bootstrap_not_per_agent():
    # NEGATIVE CONTROL for the above: if classify_token ignored the prefix and
    # returned per-agent for any non-empty token, the test above would still
    # pass. This one pins the other side of auth.ts:46.
    assert ci.classify_token("cipher-0123") == ci.MODE_BOOTSTRAP
    assert ci.classify_token("ciphe_0123") == ci.MODE_BOOTSTRAP
    assert ci.classify_token("CIPHER_0123") == ci.MODE_BOOTSTRAP  # JS startsWith is case-sensitive


def test_absent_token_is_advisory():
    # auth.ts:106-108 — no bearer and no server token means agentId undefined.
    assert ci.classify_token(None) == ci.MODE_ADVISORY
    assert ci.classify_token("") == ci.MODE_ADVISORY


def test_classify_token_never_returns_the_token():
    # The tool's core safety property: a secret goes in, only a mode comes out.
    secret = "cipher_deadbeefdeadbeefdeadbeefdeadbeef"
    assert secret not in ci.classify_token(secret)


# ---------------------------------------------------------------------------
# card loading — the unlock
# ---------------------------------------------------------------------------

def test_only_active_cards_count(tmp_path):
    path = _cards(tmp_path, [("live-agent", True), ("retired-agent", False)])
    agents, err = ci.load_active_card_agents(path)
    assert err is None
    assert "live-agent" in agents
    # NEGATIVE CONTROL: an inactive card must not authorise anything. Without
    # this, `active: false` would be decoration and revocation would be a no-op.
    assert "retired-agent" not in agents


def test_missing_card_file_reports_instead_of_raising(tmp_path):
    agents, err = ci.load_active_card_agents(tmp_path / "nope.yaml")
    assert agents == set()
    assert err and "no card file" in err


def test_malformed_card_file_reports_instead_of_raising(tmp_path):
    p = tmp_path / "cards.yaml"
    p.write_text("just a string, not a card list\n", encoding="utf-8")
    agents, err = ci.load_active_card_agents(p)
    assert agents == set()
    assert err  # a launcher must never die because a config file is wrong


# ---------------------------------------------------------------------------
# resolve — the measurement the launcher prints
# ---------------------------------------------------------------------------

def test_bootstrap_bearer_files_writes_under_bootstrap_not_the_agent(tmp_path):
    path = _cards(tmp_path, [("z890-claude", True)])
    row = ci.resolve("z890-claude", environ={"CIPHER_API_TOKEN": "opaque"}, cards_path=path)
    # This is the live fleet state the tool exists to make visible.
    assert row["mode"] == ci.MODE_BOOTSTRAP
    assert row["effective_id"] == "bootstrap"
    assert row["carded"] == "yes"
    assert not ci.carry_intact(row)


def test_minted_bearer_plus_active_card_is_the_only_intact_carry(tmp_path):
    path = _cards(tmp_path, [("z890-claude", True)])
    row = ci.resolve("z890-claude", environ={"CIPHER_API_TOKEN": "cipher_abc"}, cards_path=path)
    assert row["mode"] == ci.MODE_PER_AGENT
    assert row["effective_id"] == "z890-claude"
    assert ci.carry_intact(row)


def test_minted_bearer_without_a_card_is_not_intact(tmp_path):
    # NEGATIVE CONTROL for the test above: carry_intact must require BOTH the
    # minted prefix and the card. A token whose issuing authority no longer
    # exists is exactly the "ledger without signature" split #2935 named.
    path = _cards(tmp_path, [("some-other-agent", True)])
    row = ci.resolve("z890-claude", environ={"CIPHER_API_TOKEN": "cipher_abc"}, cards_path=path)
    assert row["mode"] == ci.MODE_PER_AGENT
    assert row["carded"] == "no"
    assert not ci.carry_intact(row)
    assert "no active signing card" in row["why"]


def test_advisory_when_no_token_visible(tmp_path):
    path = _cards(tmp_path, [("z890-claude", True)])
    row = ci.resolve("z890-claude", environ={}, cards_path=path)
    assert row["mode"] == ci.MODE_ADVISORY
    assert row["effective_id"] == ""
    assert not ci.carry_intact(row)


def test_no_agent_is_unknown_not_a_false_bootstrap(tmp_path):
    path = _cards(tmp_path, [("z890-claude", True)])
    row = ci.resolve("", environ={"CIPHER_API_TOKEN": "opaque"}, cards_path=path)
    # Reporting "writes land as bootstrap" for a session with no resolved
    # identity would be a guess wearing a measurement's clothes.
    assert row["mode"] == ci.MODE_UNKNOWN
    assert row["effective_id"] == ""


def test_unverifiable_card_status_always_says_why(tmp_path):
    # Regression: the first live run printed "signing card: unknown" with no
    # reason, in the advisory branch only. A verdict without its reason is the
    # defect this tool was written to expose.
    row = ci.resolve("z890-claude", environ={}, cards_path=tmp_path / "gone.yaml")
    assert row["carded"] == "unknown"
    assert "card status unverifiable" in row["why"]


def test_resolve_never_echoes_the_token(tmp_path):
    path = _cards(tmp_path, [("z890-claude", True)])
    secret = "cipher_deadbeefdeadbeefdeadbeefdeadbeef"
    row = ci.resolve("z890-claude", environ={"CIPHER_API_TOKEN": secret}, cards_path=path)
    joined = " ".join(row.values())
    assert secret not in joined
    # NEGATIVE CONTROL: also reject the bare uuid half, which is what an
    # over-eager "helpful" message would most plausibly leak.
    assert secret[len(ci.MINTED_PREFIX):] not in joined
