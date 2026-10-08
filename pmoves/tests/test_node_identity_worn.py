"""An identity WORN on a node that is not its home node.

A.12 multiplicity (operator ruling 2026-10-08): a node gets its own default
identity AND an existing identity can be worn there. identity_vocabulary.yaml
already declares the doctrine in `node_relations` ("an identity worn on hardware
that is not its home node", ledger form `CLAUDE-OPUS (Z890-mirror-on-5090)`), and
identity_lineage.wearing() reads it. node_identity.py did not: the register name
was refused on any non-home node, and the cipher agentId came from the NODE's
default identity rather than the identity actually worn.

Every file here is a fixture. No real node_relations row exists for a new node,
and none is invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))
import identity_lineage  # noqa: E402
import node_identity  # noqa: E402

TOKEN = "KNUCKLES-mirror-on-st-maarten"

NODES = {"version": 1, "nodes": [
    {"canonical": "knuckles", "kind": "node", "aliases": ["knuckles", "pmoves-b850"],
     "default_identity": {"claude-code": "claude_b850"},
     "cipher_agent_id": {"claude-code": "b850-claude"}},
    {"canonical": "z890", "kind": "node", "aliases": ["z890"],
     "default_identity": {"claude-code": "claude_z890"},
     "cipher_agent_id": {"claude-code": "z890-claude"}},
    # The new node: its OWN default identity, and claude_b850 wearable on it.
    {"canonical": "st-maarten", "kind": "node", "aliases": ["st-maarten", "pmoves-st-maarten"],
     "default_identity": {"claude-code": "claude_st_maarten"},
     "cipher_agent_id": {"claude-code": "st-maarten-claude"}},
]}

REGISTRY = {"agents": {
    "claude_b850": {"signature": "b850-claude",
                    "topology": {"node_affinity": ["pmoves-b850", "st-maarten"]}},
    "claude_z890": {"signature": "z890-claude", "topology": {"node_affinity": ["z890"]}},
    "claude_st_maarten": {"signature": "st-maarten-claude",
                          "topology": {"node_affinity": ["st-maarten"]}},
    # Registered on st-maarten but nobody's default for claude-code anywhere.
    "kimi_st_maarten": {"signature": "st-maarten-kimi",
                        "topology": {"node_affinity": ["st-maarten"]}},
}}

IDENTITIES = [
    {"canonical": "b850-claude", "aliases": ["B850-CLAUDE", "claude_b850"],
     "node": "knuckles", "register_form": "B850-CLAUDE (Knuckles)"},
    {"canonical": "z890-claude", "aliases": ["Z890-CLAUDE", "claude_z890"],
     "node": "z890", "register_form": "Z890-CLAUDE"},
    {"canonical": "st-maarten-claude", "aliases": ["ST-MAARTEN-CLAUDE", "claude_st_maarten"],
     "node": "st-maarten", "register_form": "ST-MAARTEN-CLAUDE"},
]

# mirrored_from spelled as an ALIAS on purpose: both sides must be normalised.
MIRROR = {"token": TOKEN, "node": "st-maarten", "mirrored_from": "pmoves-b850"}


@pytest.fixture
def files(tmp_path: Path):
    def write(relations: list[dict] | None = None) -> dict[str, Path]:
        nodes = tmp_path / "node-vocabulary.yaml"
        registry = tmp_path / "agent_registry.yaml"
        idents = tmp_path / "identity_vocabulary.yaml"
        nodes.write_text(yaml.safe_dump(NODES), encoding="utf-8")
        registry.write_text(yaml.safe_dump(REGISTRY), encoding="utf-8")
        doc = {"version": 1, "identities": IDENTITIES}
        if relations is not None:
            doc["node_relations"] = relations
        idents.write_text(yaml.safe_dump(doc), encoding="utf-8")
        return {"nodes": nodes, "registry": registry, "idents": idents}
    return write


def _name(files: dict[str, Path], identity: str, node: str, **env: str):
    vocab = node_identity.load_vocabulary(files["nodes"])
    return node_identity.resolve_register_name(
        identity, node, vocab=vocab, env=dict(env), path=files["idents"])


# --- (a) home node: unchanged ------------------------------------------------

def test_home_node_is_unchanged(files):
    f = files([MIRROR])
    name, form, _ = _name(f, "claude_b850", "knuckles")
    assert (name, form) == ("B850-CLAUDE", "B850-CLAUDE (Knuckles)")


# --- (b) declared mirror: worn name with the declared token verbatim ---------

def test_a_declared_mirror_names_the_worn_identity(files):
    f = files([MIRROR])
    name, form, why = _name(f, "claude_b850", "st-maarten")
    assert (name, form) == ("B850-CLAUDE", f"B850-CLAUDE ({TOKEN})"), why
    assert TOKEN in why and "node_relations" in why, why


def test_the_worn_form_folds_back_to_the_worn_identity():
    """The collision gate must attribute what a worn session signs to the
    identity it was told it is -- the parenthetical never changes WHO."""
    assert identity_lineage.canonical_identity(f"B850-CLAUDE ({TOKEN})") == "b850-claude"


# --- (c) no relation: still refused -----------------------------------------

def test_no_relation_is_still_refused(files):
    f = files(None)
    name, form, why = _name(f, "claude_b850", "st-maarten")
    assert (name, form) == (None, None)
    assert "declared for node 'knuckles', not 'st-maarten'" in why, why


# --- (d) a relation from a DIFFERENT home node is not this identity's --------

def test_a_relation_mirrored_from_another_node_is_refused(files):
    f = files([{"token": "Z890-mirror-on-st-maarten", "node": "st-maarten",
                "mirrored_from": "z890"}])
    name, form, why = _name(f, "claude_b850", "st-maarten")
    assert (name, form) == (None, None)
    assert "declared for node 'knuckles', not 'st-maarten'" in why, why


def test_the_mirror_is_keyed_on_the_identitys_home_not_on_any_identity(files):
    f = files([MIRROR])                      # declares knuckles -> st-maarten only
    name, form, _ = _name(f, "claude_z890", "st-maarten")
    assert (name, form) == (None, None)


def test_two_tokens_for_one_mirror_is_a_refusal_not_a_choice(files):
    f = files([MIRROR, {"token": "B850-on-st-maarten", "node": "st-maarten",
                        "mirrored_from": "knuckles"}])
    name, form, why = _name(f, "claude_b850", "st-maarten")
    assert (name, form) == (None, None)
    assert TOKEN in why and "B850-on-st-maarten" in why, why


# --- (e) the second-session override keeps its own rule ----------------------

def test_the_override_still_requires_an_identity_declared_for_this_node(files):
    """PMOVES_REGISTER_IDENTITY exists to give a SECOND session a distinct BASE.
    Letting it reach a foreign identity through a mirror would hand that session
    another identity's owner string -- the collision the rule prevents."""
    f = files([MIRROR])
    name, form, why = _name(f, "claude_st_maarten", "st-maarten",
                            PMOVES_REGISTER_IDENTITY="B850-CLAUDE")
    assert (name, form) == (None, None)
    assert "not 'st-maarten'" in why, why


def test_the_override_for_this_nodes_own_identity_still_works(files):
    f = files([MIRROR])
    name, form, _ = _name(f, "claude_b850", "st-maarten",
                          PMOVES_REGISTER_IDENTITY="ST-MAARTEN-CLAUDE")
    assert (name, form) == ("ST-MAARTEN-CLAUDE", "ST-MAARTEN-CLAUDE")


# --- end to end through the CLI the launcher evals ---------------------------

def _run_main(files, monkeypatch, capsys, **env: str) -> dict[str, str]:
    import shlex
    monkeypatch.setattr(node_identity, "VOCABULARY_PATH", files["nodes"])
    monkeypatch.setattr(node_identity, "REGISTRY_PATH", files["registry"])
    monkeypatch.setattr(node_identity, "IDENTITY_VOCABULARY_PATH", files["idents"])
    for key in ("PMOVES_NODE_IDENTITY", "PMOVES_REGISTER_IDENTITY", "PMOVES_CIPHER_AGENT_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert node_identity.main(["--harness", "claude-code", "--shell"]) == 0
    out = {}
    for line in capsys.readouterr().out.splitlines():
        key, _, value = line.partition("=")
        parts = shlex.split(value) if value else []
        out[key] = parts[0] if parts else ""
    return out


def test_multiplicity_the_new_nodes_own_default_is_unaffected(files, monkeypatch, capsys):
    out = _run_main(files([MIRROR]), monkeypatch, capsys, PMOVES_NODE_ID="st-maarten")
    assert out["PMOVES_RESOLVED_IDENTITY"] == "claude_st_maarten"
    assert out["PMOVES_CIPHER_AGENT_ID"] == "st-maarten-claude"
    assert out["PMOVES_REGISTER_FORM"] == "ST-MAARTEN-CLAUDE"


def test_multiplicity_a_worn_identity_binds_all_three_namespaces(files, monkeypatch, capsys):
    """Wearing B850-CLAUDE on st-maarten must carry B850-CLAUDE's cipher card,
    not the node default's. Memory written under st-maarten-claude while the
    session believes it is B850-CLAUDE is the wrong-agent defect cipher's
    agentId exists to prevent."""
    out = _run_main(files([MIRROR]), monkeypatch, capsys,
                    PMOVES_NODE_ID="st-maarten", PMOVES_NODE_IDENTITY="claude_b850")
    assert out["PMOVES_RESOLVED_IDENTITY"] == "claude_b850", out
    assert out["PMOVES_CIPHER_AGENT_ID"] == "b850-claude", out
    assert out["PMOVES_REGISTER_FORM"] == f"B850-CLAUDE ({TOKEN})", out


def test_an_identity_no_node_declares_gets_no_cipher_id_not_the_nodes(files, monkeypatch, capsys):
    out = _run_main(files([MIRROR]), monkeypatch, capsys,
                    PMOVES_NODE_ID="st-maarten", PMOVES_NODE_IDENTITY="kimi_st_maarten")
    assert out["PMOVES_RESOLVED_IDENTITY"] == "kimi_st_maarten", out
    assert out["PMOVES_CIPHER_AGENT_ID"] == "", out
    assert "kimi_st_maarten" in out["PMOVES_CIPHER_AGENT_WHY"], out
