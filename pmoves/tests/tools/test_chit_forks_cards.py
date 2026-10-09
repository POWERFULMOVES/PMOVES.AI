"""Every `signing_card:` in a CHIT-FORK record must name a real ACTIVE card.

`CHIT_FORKS.md` (#3063) declares the rule: *"A constant with a card has an author
and a verification surface; a constant without a card is downstream's
responsibility until it breaks."* Nothing checked that the cards it names EXIST.

That is the same gap, one level up. A record asserting `signing_card: 5090-claude`
carries exactly as much authority as the claim that `5090-claude` is a real,
active signing identity — and until this test, a typo, a renamed agent, or a
deactivated card left the record reading as authoritative while pointing at
nobody.

This is the first cross-cutting use of the card check. `mint_cipher_token.py`
already gates minting on it, so a memory identity cannot exist without a card;
this gates *authorship of a fork override* on the same function, from the same
module, so the two cannot drift apart about what an active card is.

`signing_card: none` is DELIBERATELY VALID. It is the record's way of saying "no
PMOVES authorship here, this is upstream's constant" — the memory-manager
constants row. Treating that as an error would push records toward inventing an
owner, which is the opposite of the doctrine.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
RECORD = REPO_ROOT / "pmoves" / "docs" / "PMOVESCHIT" / "CHIT_FORKS.md"
sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))

from cipher_identity import load_active_card_agents  # noqa: E402

NO_OWNER = {"none", "n/a", "unassigned"}


def _records():
    if not RECORD.is_file():
        pytest.skip("CHIT_FORKS.md not present")
    blocks = re.findall(r"```yaml\n(.*?)```", RECORD.read_text(encoding="utf-8"), re.S)
    if not blocks:
        pytest.skip("CHIT_FORKS.md carries no yaml record yet")
    return [yaml.safe_load(b) for b in blocks]


def _cards_named(doc) -> list:
    """Every signing_card value in a record, with its context for the message."""
    found = []
    art = (doc or {}).get("artifact") or {}
    for override in art.get("overrides") or []:
        if isinstance(override, dict) and "signing_card" in override:
            found.append((str(override.get("file", "<no file>")), override["signing_card"]))
    if "signing_card" in art:
        found.append(("<record owner>", art["signing_card"]))
    return found


def _normalise(value) -> str:
    """`5090-claude (this lane)` -> `5090-claude`."""
    return re.sub(r"\s*\(.*\)\s*$", "", str(value)).strip()


def test_the_record_parses():
    docs = _records()
    assert docs and docs[0], "CHIT_FORKS.md yaml block did not parse to a record"


def test_every_signing_card_names_an_active_card():
    active, err = load_active_card_agents()
    if err:
        pytest.skip(f"cards unreadable: {err}")
    bad = []
    for doc in _records():
        for where, raw in _cards_named(doc):
            name = _normalise(raw)
            if name.lower() in NO_OWNER:
                continue
            if name not in active:
                bad.append(f"{where} -> signing_card {name!r}")
    assert not bad, (
        "CHIT-FORK records name signing cards that are not ACTIVE in "
        "pmoves/config/signing_identity_cards.yaml:\n  " + "\n  ".join(bad) +
        "\nA record whose owner does not exist asserts authorship it cannot back."
    )


def test_none_is_accepted_as_an_explicit_non_owner():
    """NEGATIVE CONTROL for the test above.

    If the check simply rejected everything unknown, the memory-manager row
    (`signing_card: none` — upstream's constants, deliberately unowned) would
    fail and the honest answer would be punished. Prove `none` survives.
    """
    active, err = load_active_card_agents()
    if err:
        pytest.skip(f"cards unreadable: {err}")
    assert _normalise("none").lower() in NO_OWNER
    assert "none" not in active, (
        "an agent literally named 'none' exists, which makes the explicit "
        "non-owner value ambiguous — rename the agent or change the sentinel"
    )


def test_the_record_pins_both_commits():
    """A record that names an artifact without pinning it cannot be verified.

    #3063 merged with `<filled when PR opens>` in both fields, so 'which
    auth.ts?' was unanswerable from the record — the exact question the doctrine
    exists to answer. Placeholders must not survive review again.
    """
    for doc in _records():
        art = (doc or {}).get("artifact") or {}
        fork = str(art.get("pmoves_fork_commit") or "")
        upstream = str(((art.get("upstream") or {}).get("pinned_commit")) or "")
        for label, value in (("pmoves_fork_commit", fork), ("upstream.pinned_commit", upstream)):
            assert value and "filled when" not in value and not value.startswith("<"), (
                f"{label} is still a placeholder ({value!r}); a fork record without "
                "a commit pin names an artifact it cannot identify"
            )
            assert re.fullmatch(r"[0-9a-f]{40}", value), (
                f"{label} is {value!r}; pin the full 40-char sha so the record "
                "resolves without guessing which abbreviation was meant"
            )
