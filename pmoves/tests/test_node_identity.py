"""Node identity resolution, and the gate on the node vocabulary itself."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh"


def _module():
    path = REPO_ROOT / "pmoves" / "tools" / "node_identity.py"
    spec = importlib.util.spec_from_file_location("node_identity", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["node_identity"] = module
    spec.loader.exec_module(module)
    return module


ni = _module()


# --------------------------------------------------------------------------
# The gate: no spelling may enter node_affinity without being declared.
# --------------------------------------------------------------------------

def test_every_registry_node_affinity_value_is_declared():
    """The whole point of a controlled vocabulary.

    Before this file, `node_affinity` accepted anything, and the 4090 alone
    accumulated three spellings inside one registry -- so any consumer matched
    a subset and silently missed the rest. An undeclared spelling must be a
    failure here, not a miss at runtime.
    """
    vocab = ni.load_vocabulary()
    registry = ni.load_registry()
    undeclared: dict[str, list[str]] = {}
    for key, entry in registry.items():
        for raw in (entry.get("topology") or {}).get("node_affinity") or []:
            if ni.canonical_node(raw, vocab) is None:
                undeclared.setdefault(str(raw), []).append(key)
    assert not undeclared, (
        "undeclared node_affinity spellings (add each as an alias in "
        f"pmoves/configs/node-vocabulary.yaml): { {k: sorted(v) for k, v in undeclared.items()} }"
    )


def _undeclared_in(registry, vocab):
    """The gate's own loop, so proving THIS says no proves the gate can."""
    found = {}
    for key, entry in registry.items():
        for raw in (entry.get("topology") or {}).get("node_affinity") or []:
            if ni.canonical_node(raw, vocab) is None:
                found.setdefault(str(raw), []).append(key)
    return found


def test_the_gate_can_fail():
    """A gate that has never said no is not known to be able to.

    Runs the gate's own detection over a registry carrying one undeclared
    spelling. Asserting `canonical_node(<nonsense>) is None` would NOT prove
    this -- it tests the lookup, not the loop that has to reach the lookup for
    every entry.
    """
    vocab = ni.load_vocabulary()
    registry = dict(ni.load_registry())
    registry["_injected"] = {
        "topology": {"node_affinity": ["pmoves-there-is-no-such-node"]}
    }
    found = _undeclared_in(registry, vocab)
    assert found == {"pmoves-there-is-no-such-node": ["_injected"]}
    # ...and the real registry, run through the same loop, is clean.
    assert _undeclared_in(ni.load_registry(), vocab) == {}


def test_operator_nodes_ids_all_resolve():
    """The scheduler's vocabulary and this one must not diverge.

    operator_nodes.yaml is the other place node names are written down. If a
    node is added there and not here, the gate above stops protecting it.
    """
    with open(REPO_ROOT / "pmoves" / "config" / "operator_nodes.yaml",
              encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    vocab = ni.load_vocabulary()
    unresolved = [
        n["node_id"] for n in doc.get("nodes") or []
        if ni.canonical_node(n["node_id"], vocab) is None
    ]
    assert not unresolved, f"operator_nodes.yaml ids not declared here: {unresolved}"


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

def test_yaml_integers_resolve():
    """38 registry entries spell the 5090 as the integer 5090.

    `5090 == "5090"` is False, so a consumer comparing raw values matches none
    of them and reports nothing wrong.
    """
    vocab = ni.load_vocabulary()
    assert ni.canonical_node(5090, vocab) == "5090"
    assert ni.canonical_node("5090", vocab) == "5090"


def test_the_4090s_several_spellings_all_land_on_one_node():
    vocab = ni.load_vocabulary()
    seen = {ni.canonical_node(s, vocab) for s in
            [4090, "4090", "laptop-4090", "pmoves-laptop", "pmoves-4090", "PMOVES-4090"]}
    assert seen == {"4090"}


def test_hostname_case_is_folded():
    vocab = ni.load_vocabulary()
    assert ni.canonical_node("PMOVES-Z890", vocab) == "z890"


def test_an_alias_may_name_only_one_node():
    """Two nodes claiming one alias would make resolution order-dependent."""
    doc = {"nodes": [
        {"canonical": "a", "aliases": ["shared"]},
        {"canonical": "b", "aliases": ["shared"]},
    ]}
    path = REPO_ROOT / "pmoves" / "tests" / "_tmp_vocab.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="claimed by both"):
            ni.load_vocabulary(path)
    finally:
        path.unlink()


# --------------------------------------------------------------------------
# this_node
# --------------------------------------------------------------------------

def test_env_wins_over_hostname():
    node, how = ni.this_node(env={"PMOVES_NODE_ID": "z890"}, hostname="PMOVES-4090")
    assert node == "z890"
    assert "PMOVES_NODE_ID" in how


def test_hostname_is_a_real_fallback():
    """PMOVES_NODE_ID is documented per node but is NOT set on every node --
    this machine's settings.local.json carries an empty env block."""
    node, how = ni.this_node(env={}, hostname="PMOVES-4090")
    assert node == "4090"
    assert "hostname" in how


def test_an_unknown_node_is_a_reason_not_a_silence():
    node, how = ni.this_node(env={}, hostname="some-laptop")
    assert node is None
    assert "some-laptop" in how and "alias" in how


def test_an_undeclared_env_id_does_not_fall_through_to_hostname():
    """Falling back would let a typo'd PMOVES_NODE_ID resolve to the right node
    by accident, hiding the typo until the day the hostname also changes."""
    node, how = ni.this_node(env={"PMOVES_NODE_ID": "4o9o"}, hostname="PMOVES-4090")
    assert node is None
    assert "4o9o" in how


# --------------------------------------------------------------------------
# resolve_identity -- the no-guessing rules
# --------------------------------------------------------------------------

REG_OK = {
    "claude_4090": {"topology": {"node_affinity": ["laptop-4090"]}},
    "kilocode_glm": {"topology": {"node_affinity": [5090, "laptop-4090"]}},
}


def test_declared_identity_binds_when_registered_and_claiming():
    node, identity, why = ni.resolve_identity(
        "claude-code", registry=REG_OK, env={}, hostname="PMOVES-4090")
    assert (node, identity) == ("4090", "claude_4090")
    assert "claude_4090" in why


def test_declared_but_unregistered_says_so_and_names_the_claimants():
    """The exact state of this repo until #2739 merges: the identity is
    declared and not wired. That must read as a finding, not as absence."""
    node, identity, why = ni.resolve_identity(
        "claude-code", registry={"kilocode_glm": REG_OK["kilocode_glm"]},
        env={}, hostname="PMOVES-4090")
    assert node == "4090" and identity is None
    assert "not wired" in why and "kilocode_glm" in why


def test_an_identity_that_does_not_claim_the_node_is_refused():
    registry = {"claude_4090": {"topology": {"node_affinity": ["z890"]}}}
    node, identity, why = ni.resolve_identity(
        "claude-code", registry=registry, env={}, hostname="PMOVES-4090")
    assert identity is None
    assert "does not claim" in why


def test_no_declaration_for_the_harness_never_guesses_from_affinity():
    """Eight registry agents claim the 4090. Picking one would be a guess."""
    node, identity, why = ni.resolve_identity(
        "some-other-harness", registry=REG_OK, env={}, hostname="PMOVES-4090")
    assert node == "4090" and identity is None
    assert "no identity is declared" in why


def test_env_override_beats_the_declaration():
    node, identity, why = ni.resolve_identity(
        "claude-code", registry=REG_OK,
        env={"PMOVES_NODE_IDENTITY": "kilocode_glm"}, hostname="PMOVES-4090")
    assert identity == "kilocode_glm"
    assert "PMOVES_NODE_IDENTITY" in why


def test_placeholders_never_bind():
    node, identity, why = ni.resolve_identity(
        "claude-code", registry=REG_OK,
        env={"PMOVES_NODE_ID": "cloud"}, hostname="PMOVES-4090")
    assert node == "cloud" and identity is None
    assert "not a machine" in why


def test_agents_claiming_folds_every_spelling():
    """kilocode_glm claims the 4090 as `laptop-4090`; a raw match on `4090`
    would miss it."""
    assert ni.agents_claiming("4090", REG_OK, ni.load_vocabulary()) == [
        "claude_4090", "kilocode_glm"]


# --------------------------------------------------------------------------
# The launcher must actually call this. A test of the resolver alone would
# still pass if the wiring were removed -- which is precisely how the registry
# came to have an unread node_affinity field in the first place.
# --------------------------------------------------------------------------

def test_the_launcher_invokes_the_resolver():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "node_identity.py" in text, "launcher no longer calls the resolver"
    assert "--append-system-prompt" in text, (
        "the identity must reach the session's context; an exported variable "
        "does not"
    )


def test_the_launcher_fails_open():
    """Losing the identity must never cost the launch."""
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'if [ -f "$IDENT_TOOL" ]' in text, "resolver call is not guarded"
    assert "launching without it" in text, "no audible fallback message"
