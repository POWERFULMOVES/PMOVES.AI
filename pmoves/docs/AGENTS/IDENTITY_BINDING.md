# Identity binding — PMOVES vocabulary ↔ Spynel harness prefix slots

Implements recommendation #1 (P1) of `pmoves/docs/AGENTS/PMOVES-SPYNEL-VS-REGISTRIES-REVIEW-2026-09-21.md:206`.
Gated by `pmoves/tests/test_identity_binding.py`. All citations are superproject paths;
this document makes no claim about any submodule's code.

## The binding in one line

**The PMOVES vocabulary is the sole surface that declares identity. The Spynel
`harness.*_agent_prefix` slots declare none, so there is nothing for the CLAIM line to
override — the CLAIM line is simply the only writer.**

The review stated it as "Spynel `harness.developer_agent_prefix` is overridden by the
CHIT-signed CLAIM line; the PMOVES vocabulary provides the *valid prefixes* set." That is
the right conclusion from a wrong premise, and the difference matters. Measured
2026-09-21: per `spynel docs harnesses` § *Agent prefixes*, a prefix slot is "an optional
validated one-line harness-native command, such as `/goal` or `/ultrathink`" that Spynel
outer-trims and joins to the prompt with one ASCII space. It is a **prompt prefix, not an
identity prefix**. The two surfaces do not compete; one is empty of identity by
construction.

## Which surface answers which question

| Question | Authoritative surface |
|---|---|
| What is the set of valid identities and spellings? | `pmoves/config/identity_vocabulary.yaml:87` (`identities:`), plus `lanes:` `:380`, `harnesses:` `:449`, `provisioning:` `:397` |
| What identity does *this* session use? | Neither. It is the `OWNER=` argument at `pmoves/Makefile:395`, defaulting to `$REGISTER_OWNER` (`pmoves/Makefile:386`, `pmoves/tools/register_append.py:981`) |
| What author string actually lands in the register? | The CLAIM/RELEASE/NOTE row written by `pmoves/tools/register_append.py`; `:1083` refuses a row with no owner |
| Is that author string legal? | `pmoves/tools/identity_lineage.py:538` (`verify`), via `canonical_identity` `:326` — enforced post-hoc by `pmoves/tests/test_identity_lineage.py`, per the vocabulary's own rule at `pmoves/config/identity_vocabulary.yaml:37-40` |
| What text is prepended to the agent prompt? | `.spynel/config.yaml:12-15` |

## The four configured slots and what may fill them

`.spynel/config.yaml:7` `harness:` carries exactly four:

| Slot | Line | May be filled by a vocabulary entry? |
|---|---|---|
| `chat_agent_prefix` | `.spynel/config.yaml:12` | No — harness-native command only |
| `developer_agent_prefix` | `.spynel/config.yaml:13` | No — harness-native command only |
| `reviewer_agent_prefix` | `.spynel/config.yaml:14` | No — harness-native command only |
| `heartbeat_agent_prefix` | `.spynel/config.yaml:15` | No — harness-native command only |

The mapping is empty in both directions, and that is the contract: putting a vocabulary
identity into a prefix slot would inject that string into the prompt, not into the
register, producing an identity claim no gate reads.

## Precedence when they disagree

1. The CLAIM-line author string (`OWNER=`) is what the register records — always.
2. `pmoves/config/identity_vocabulary.yaml` decides whether that string is legal.
3. `.spynel/config.yaml` prefix slots have no vote. A disagreement between a prefix slot
   and the vocabulary is not a tie to break; it is a misconfiguration to remove.

## The empty-slot default — the live state, not an edge case

All four slots are `""` today (`.spynel/config.yaml:12-15`, verified 2026-09-21). Per
`spynel docs harnesses`, an empty prefix "preserves the prompt byte-for-byte", so a
Spynel-dispatched session receives **no identity at all** from the harness. It resolves
identity only when it reaches `make -C pmoves register-claim` and supplies `OWNER=`.
Nothing validates that string at write time; `identity_lineage.verify()` catches it
afterward.

That gap is live, not hypothetical. `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:2980` is a
NOTE filed `2026-09-21T21:19:28Z` by author `SPARK-CLAUDE` — a Spynel developer session on
this node with `developer_agent_prefix: ""`. `SPARK-CLAUDE` is **not** in the vocabulary,
so `verify()` currently returns exactly one finding naming it, while
`pmoves/config/signing_identity_cards.yaml:253` does carry `agent_id: "spark-claude"`. The
card exists; the vocabulary entry does not. Closing it is a vocabulary append, out of
scope here and deliberately not performed by this document.

## The missing fifth slot

`.spynel/instructions/` holds five role files — `agent-chat.md`, `agent-developer.md`,
`agent-reviewer.md`, `agent-heartbeat.md`, `agent-notification.md` — but `.spynel/config.yaml`
defines only four prefix slots. There is **no `notification_agent_prefix`**. Recorded, not
papered over: under this binding the asymmetry is harmless, because a prefix slot carries
no identity and the notification agent files no register row. It would become load-bearing
only if prefix slots ever gained identity meaning, which is exactly what the ratchet test
guards against.
