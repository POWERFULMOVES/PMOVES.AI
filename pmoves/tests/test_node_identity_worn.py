"""An identity WORN on a node that is not its home node.

Operator correction 2026-10-08: "node_relations are not the determinant of
identity. Identity is the collection aggregate that may or may not include a
node." Identity is card + signature + alters + roles + lineage + ACK trail; the
node is a FACT about a session, never a permission to be the identity. So:

  - node_affinity is a PREFERENCE (agent_registry.yaml's own words for
    claude_b850: "a preference, not an exclusive claim"). An identity DECLARED
    via PMOVES_NODE_IDENTITY binds on any node and the explanation records it as
    off-affinity. The node's default_identity auto-binding is unchanged.
  - The register name has no node gate. Off its home node the owner string is
    `<BASE> (<node>)` -- the node token in the parenthetical, which is the shape
    identity_lineage.wearing() already parses -- or `<BASE> (<token>)` when a
    node_relations row declares a token for that mirror.
  - The cipher agentId follows the identity, not the node.
  - PMOVES_REGISTER_IDENTITY keeps its same-node second-session rule.

Every file here is a fixture. No real node_relations row exists for a new node,
and none is invented.
"""
from __future__ import annotations

import shlex
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
    # The new node: its OWN default identity. Nothing about it names claude_b850.
    {"canonical": "st-maarten", "kind": "node", "aliases": ["st-maarten", "pmoves-st-maarten"],
     "default_identity": {"claude-code": "claude_st_maarten"},
     "cipher_agent_id": {"claude-code": "st-maarten-claude"}},
    # A node whose DEFAULT points at an identity that does not claim it: the
    # auto-binding path must still refuse this, exactly as before.
    {"canonical": "orphan", "kind": "node", "aliases": ["orphan"],
     "default_identity": {"claude-code": "claude_z890"}},
    {"canonical": "cloud", "kind": "placeholder", "aliases": ["cloud"]},
]}

# claude_b850 does NOT list st-maarten: affinity is a preference, and wearing
# the identity there must not require editing it.
REGISTRY = {"agents": {
    "claude_b850": {"signature": "b850-claude", "topology": {"node_affinity": ["pmoves-b850"]}},
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


def _bind(files: dict[str, Path], node: str, **env: str):
    vocab = node_identity.load_vocabulary(files["nodes"])
    registry = node_identity.load_registry(files["registry"])
    return node_identity.resolve_identity(
        "claude-code", vocab=vocab, registry=registry, env={"PMOVES_NODE_ID": node, **env})


# --- 1. node_affinity is a preference ----------------------------------------

def test_a_declared_identity_binds_off_affinity_and_says_so(files):
    node, ident, why = _bind(files(None), "st-maarten", PMOVES_NODE_IDENTITY="claude_b850")
    assert (node, ident) == ("st-maarten", "claude_b850"), why
    assert "off-affinity on st-maarten" in why, why


def test_the_default_auto_binding_still_requires_affinity(files):
    """Nothing declared: the node's default binds only if it claims the node."""
    node, ident, why = _bind(files(None), "orphan")
    assert (node, ident) == ("orphan", None)
    assert "does not include orphan" in why, why


def test_the_default_auto_binding_is_unchanged_on_its_own_node(files):
    node, ident, why = _bind(files(None), "st-maarten")
    assert (node, ident) == ("st-maarten", "claude_st_maarten")
    assert "off-affinity" not in why, why


def test_a_declared_identity_must_still_be_registered(files):
    node, ident, why = _bind(files(None), "st-maarten", PMOVES_NODE_IDENTITY="claude_nobody")
    assert ident is None
    assert "not in" in why, why


def test_a_placeholder_is_still_not_a_node_to_record(files):
    node, ident, why = _bind(files(None), "cloud", PMOVES_NODE_IDENTITY="claude_b850")
    assert ident is None
    assert "not a machine" in why, why


# --- 2. the register name has no node gate -----------------------------------

def test_home_node_is_unchanged(files):
    name, form, _ = _name(files([MIRROR]), "claude_b850", "knuckles")
    assert (name, form) == ("B850-CLAUDE", "B850-CLAUDE (Knuckles)")


def test_off_home_the_node_is_recorded_as_a_fact(files):
    name, form, why = _name(files(None), "claude_b850", "st-maarten")
    assert (name, form) == ("B850-CLAUDE", "B850-CLAUDE (st-maarten)"), why
    assert "st-maarten" in why and "knuckles" in why, why


def test_a_declared_mirror_token_is_used_verbatim(files):
    name, form, why = _name(files([MIRROR]), "claude_b850", "st-maarten")
    assert (name, form) == ("B850-CLAUDE", f"B850-CLAUDE ({TOKEN})"), why
    assert TOKEN in why and "node_relations" in why, why


def test_a_relation_for_another_home_does_not_annotate_this_identity(files):
    f = files([{"token": "Z890-mirror-on-st-maarten", "node": "st-maarten",
                "mirrored_from": "z890"}])
    name, form, _ = _name(f, "claude_b850", "st-maarten")
    assert (name, form) == ("B850-CLAUDE", "B850-CLAUDE (st-maarten)")


def test_the_mirror_token_is_keyed_on_the_identitys_home(files):
    name, form, _ = _name(files([MIRROR]), "claude_z890", "st-maarten")
    assert (name, form) == ("Z890-CLAUDE", "Z890-CLAUDE (st-maarten)")


def test_two_tokens_for_one_mirror_fall_back_to_the_node_and_say_why(files):
    f = files([MIRROR, {"token": "B850-on-st-maarten", "node": "st-maarten",
                        "mirrored_from": "knuckles"}])
    name, form, why = _name(f, "claude_b850", "st-maarten")
    assert (name, form) == ("B850-CLAUDE", "B850-CLAUDE (st-maarten)"), why
    assert TOKEN in why and "B850-on-st-maarten" in why, why


def test_concurrent_sessions_on_two_nodes_get_distinct_owner_strings(files):
    f = files(None)
    home = _name(f, "claude_b850", "knuckles")[1]
    worn = _name(f, "claude_b850", "st-maarten")[1]
    assert home != worn


def test_the_worn_forms_fold_back_to_the_worn_identity():
    """The parenthetical never changes WHO."""
    for form in (f"B850-CLAUDE ({TOKEN})", "B850-CLAUDE (5090)"):
        assert identity_lineage.canonical_identity(form) == "b850-claude"


def test_the_node_form_is_the_shape_wearing_already_parses():
    """Deterministic spelling, not an invented one: a node token in the
    parenthetical is what identity_lineage.wearing() reads as `node`."""
    worn = identity_lineage.wearing("B850-CLAUDE (5090)")
    assert (worn.identity, worn.node) == ("b850-claude", "5090")
    assert not worn.unclassified, worn.unclassified


# --- 3. the second-session override keeps its same-node rule -----------------

def test_the_override_still_requires_an_identity_declared_for_this_node(files):
    """PMOVES_REGISTER_IDENTITY renames ONLY the register owner string, so a
    foreign BASE would sign the register as one aggregate while cipher and the
    registry carry another. Wearing another identity is PMOVES_NODE_IDENTITY,
    which moves all three namespaces together."""
    name, form, why = _name(files([MIRROR]), "claude_st_maarten", "st-maarten",
                            PMOVES_REGISTER_IDENTITY="B850-CLAUDE")
    assert (name, form) == (None, None)
    assert "not 'st-maarten'" in why, why


def test_the_override_for_this_nodes_own_identity_still_works(files):
    name, form, _ = _name(files([MIRROR]), "claude_b850", "st-maarten",
                          PMOVES_REGISTER_IDENTITY="ST-MAARTEN-CLAUDE")
    assert (name, form) == ("ST-MAARTEN-CLAUDE", "ST-MAARTEN-CLAUDE")


# --- end to end through the CLI the launcher evals ---------------------------

def _run_main(files, monkeypatch, capsys, **env: str) -> dict[str, str]:
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
    out = _run_main(files(None), monkeypatch, capsys, PMOVES_NODE_ID="st-maarten")
    assert out["PMOVES_RESOLVED_IDENTITY"] == "claude_st_maarten"
    assert out["PMOVES_CIPHER_AGENT_ID"] == "st-maarten-claude"
    assert out["PMOVES_REGISTER_FORM"] == "ST-MAARTEN-CLAUDE"


def test_a_worn_identity_binds_all_three_namespaces_with_no_edits(files, monkeypatch, capsys):
    """No affinity edit, no node_relations row: the identity is the aggregate,
    and its card follows it. Memory written as st-maarten-claude by a session
    told it is B850-CLAUDE is the wrong-agent defect cipher's agentId exists to
    prevent."""
    out = _run_main(files(None), monkeypatch, capsys,
                    PMOVES_NODE_ID="st-maarten", PMOVES_NODE_IDENTITY="claude_b850")
    assert out["PMOVES_RESOLVED_IDENTITY"] == "claude_b850", out
    assert out["PMOVES_CIPHER_AGENT_ID"] == "b850-claude", out
    assert out["PMOVES_REGISTER_FORM"] == "B850-CLAUDE (st-maarten)", out


def test_a_worn_identity_uses_a_declared_token_when_there_is_one(files, monkeypatch, capsys):
    out = _run_main(files([MIRROR]), monkeypatch, capsys,
                    PMOVES_NODE_ID="st-maarten", PMOVES_NODE_IDENTITY="claude_b850")
    assert out["PMOVES_REGISTER_FORM"] == f"B850-CLAUDE ({TOKEN})", out


def test_an_identity_no_node_declares_gets_no_cipher_id_not_the_nodes(files, monkeypatch, capsys):
    out = _run_main(files(None), monkeypatch, capsys,
                    PMOVES_NODE_ID="st-maarten", PMOVES_NODE_IDENTITY="kimi_st_maarten")
    assert out["PMOVES_RESOLVED_IDENTITY"] == "kimi_st_maarten", out
    assert out["PMOVES_CIPHER_AGENT_ID"] == "", out
    assert "kimi_st_maarten" in out["PMOVES_CIPHER_AGENT_WHY"], out
