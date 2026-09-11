#!/usr/bin/env python3
"""Answer one question: which agent will the memory layer attribute this session's writes to?

A session already knows who it is. `pmoves/tools/node_identity.py` resolves the
node's registered agent, and `claude-pmoves.sh` puts that identity in the model's
context. A session also already knows whether cipher is reachable
(`cipher_preflight.py`). Between those two facts sits a gap nobody measured:

    the identity the session believes it has
    is not the identity its memories are filed under.

Grounded in `Pmoves-cipher/src/pmoves/auth.ts`, `resolveToken()` forks on ONE
character sequence:

    auth.ts:44-52   token does NOT start with "cipher_"  -> compared against the
                    CIPHER_API_TOKEN env var; on match the request is attributed
                    to agentId "bootstrap". No Supabase lookup happens at all.
    auth.ts:54-90   token DOES start with "cipher_"      -> the uuid is looked up
                    in pmoves_core.cipher_agent_tokens and the request is
                    attributed to THAT row's agent_id -- the minted agent.
    auth.ts:103-110 no Bearer at all, server token unset -> agentId undefined,
                    "advisory" mode: the caller self-declares in tool args.

So bootstrap is not an agent and never was. It is the single-token launch path,
and the minted agent is what it exists to hand off to. The handoff is a seven
character prefix, and nothing in this repo checks it -- which is why a session
can announce "I am z890-claude", write to memory all day, and have every one of
those rows land under `bootstrap` without one line of output saying so.

This tool says so. It reports, WITHOUT ever printing or logging the token:

  * which signing card (pmoves/config/signing_identity_cards.yaml) authorises
    this agent to be loaded -- the card is the unlock, not decoration;
  * which of auth.ts's three modes this session's env puts it in;
  * therefore the agent_id its memories will actually carry.

It changes nothing and blocks nothing. Same fail-open-loudly discipline as the
identity and cipher blocks in claude-pmoves.sh: an unmeasured carry is a
degraded session, not a broken one, but it must never be a SILENT one.

Exit codes:
  0  carry intact  -- session identity == effective cipher agent_id
  1  carry gap     -- they differ (bootstrap / advisory / uncarded)
  2  usage or parse error
  3  nothing to measure (no agent id to resolve)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from shlex import quote

REPO_ROOT = Path(__file__).resolve().parents[2]
CARDS = REPO_ROOT / "pmoves" / "config" / "signing_identity_cards.yaml"

# auth.ts:46 + auth.ts:60 -- `token.startsWith("cipher_")` then `token.slice(7)`.
# The prefix is the entire discriminator between bootstrap and per-agent mode.
MINTED_PREFIX = "cipher_"

# auth.ts:49 -- the literal agentId a non-prefixed token resolves to.
BOOTSTRAP_AGENT = "bootstrap"

MODE_PER_AGENT = "per-agent"
MODE_BOOTSTRAP = "bootstrap"
MODE_ADVISORY = "advisory"
MODE_UNKNOWN = "unknown"


def load_active_card_agents(cards_path: Path = CARDS) -> tuple[set, str | None]:
    """Return (active agent_ids, error). Never raises: a missing card file is a
    measurement gap to report, not a reason to take down a launcher."""
    try:
        import yaml
    except ImportError:
        return set(), "PyYAML not available"
    if not cards_path.is_file():
        return set(), "no card file at " + str(cards_path)
    try:
        data = yaml.safe_load(cards_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report, never crash the caller
        return set(), "card file did not parse: " + str(exc)
    cards = data["cards"] if isinstance(data, dict) and "cards" in data else data
    if not isinstance(cards, list):
        return set(), "card file did not parse to a list of cards"
    agents = set()
    for card in cards:
        if not isinstance(card, dict) or not card.get("active", False):
            continue
        half = card.get("h")
        if not isinstance(half, dict):
            continue
        agent = half.get("agent_id")
        if isinstance(agent, str) and agent.strip():
            agents.add(agent.strip())
    return agents, None


def classify_token(token: str | None) -> str:
    """Map a bearer to one of auth.ts's three modes.

    Takes the token only to read its first seven characters. The value is never
    returned, printed, or stored -- the only thing that leaves this function is
    one of the MODE_* constants.
    """
    if not token:
        return MODE_ADVISORY
    if token.startswith(MINTED_PREFIX):
        return MODE_PER_AGENT
    return MODE_BOOTSTRAP


def resolve(agent, environ=None, cards_path: Path = CARDS) -> dict:
    """Measure the carry. Pure: no network, no token disclosure, no side effects."""
    env = os.environ if environ is None else environ
    agent = (agent or "").strip()

    mode = classify_token(env.get("CIPHER_API_TOKEN"))
    active, card_err = load_active_card_agents(cards_path)

    row = {
        "agent": agent,
        "mode": mode,
        "carded": "",
        "effective_id": "",
        "why": "",
    }

    if not agent:
        row["mode"] = MODE_UNKNOWN
        row["why"] = (
            "no agent id to resolve (PMOVES_RESOLVED_IDENTITY unset and --agent not given)"
        )
        return row

    if card_err:
        row["carded"] = "unknown"
    else:
        row["carded"] = "yes" if agent in active else "no"

    if mode == MODE_PER_AGENT:
        # The bearer is a minted token. Which agent it resolves to lives in
        # Supabase and is deliberately NOT probed here: resolving it would mean
        # sending the token somewhere, and a measurement that spends the secret
        # it is measuring is not a measurement. The prefix proves the per-agent
        # code path; the card proves the agent is authorised to exist.
        row["effective_id"] = agent
        if row["carded"] == "no":
            row["why"] = (
                "minted token in use, but '" + agent + "' has no active signing card -- "
                "the token outlives the authority that issued it"
            )
        elif row["carded"] == "unknown":
            row["why"] = "minted token in use; card status unverifiable (" + str(card_err) + ")"
        else:
            row["why"] = "minted token + active card: writes carry '" + agent + "'"
    elif mode == MODE_BOOTSTRAP:
        row["effective_id"] = BOOTSTRAP_AGENT
        row["why"] = (
            "bearer has no 'cipher_' prefix, so auth.ts takes the single-token path "
            "and files every write under '" + BOOTSTRAP_AGENT + "', not '" + agent + "' "
            "(auth.ts:44-52). bootstrap is the launcher, and nothing has been launched."
        )
    else:  # MODE_ADVISORY
        row["effective_id"] = ""
        row["why"] = (
            "no CIPHER_API_TOKEN visible to this process: either the session is in "
            "advisory mode (auth.ts:103-110, agentId self-declared per call) or the "
            "token is injected downstream and simply not readable from here"
        )

    # A tool that reports "card status: unknown" without saying WHY is committing
    # the defect it was written to expose. Caught on the first live run: bare
    # `python` on this node has no PyYAML, so every agent read as uncarded and
    # the output gave the operator nothing to act on. The reason now always ships
    # with the verdict -- in every branch, not just the per-agent one.
    if row["carded"] == "unknown" and card_err and card_err not in row["why"]:
        row["why"] = row["why"] + "; card status unverifiable (" + str(card_err) + ")"
    return row


def _emit_shell(row: dict) -> None:
    print("PMOVES_CIPHER_AGENT=" + quote(row["agent"]))
    print("PMOVES_CIPHER_MODE=" + quote(row["mode"]))
    print("PMOVES_CIPHER_CARDED=" + quote(row["carded"]))
    print("PMOVES_CIPHER_EFFECTIVE_ID=" + quote(row["effective_id"]))
    print("PMOVES_CIPHER_WHY=" + quote(row["why"]))


def carry_intact(row: dict) -> bool:
    return bool(row["agent"]) and row["effective_id"] == row["agent"] and row["carded"] == "yes"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--agent",
        default=None,
        help="agent id to measure; defaults to $PMOVES_RESOLVED_IDENTITY then $PMOVES_NODE_IDENTITY",
    )
    ap.add_argument("--shell", action="store_true", help="emit shell-evalable assignments")
    args = ap.parse_args(argv)

    agent = args.agent
    if agent is None:
        agent = (
            os.environ.get("PMOVES_RESOLVED_IDENTITY")
            or os.environ.get("PMOVES_NODE_IDENTITY")
            or ""
        )

    row = resolve(agent)

    if args.shell:
        _emit_shell(row)
    else:
        print("agent          " + (row["agent"] or "(unresolved)"))
        print("signing card   " + (row["carded"] or "(unknown)"))
        print("cipher mode    " + row["mode"])
        print("writes land as " + (row["effective_id"] or "(advisory / self-declared)"))
        print("why            " + row["why"])

    if row["mode"] == MODE_UNKNOWN:
        return 3
    return 0 if carry_intact(row) else 1


if __name__ == "__main__":
    sys.exit(main())
