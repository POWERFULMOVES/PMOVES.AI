"""Node identity resolution, and the gate on the node vocabulary itself."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh"
WIN_LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "windows" / "claude-pmoves.bat"
# The launchers no longer carry identity resolution inline: #3094 extracted it
# into the shared fragment pm-node-identity.sh (the same shape pm-python.sh and
# pm-cipher-identity.sh set). These tests grep launcher TEXT for the invariants
# -- "resolves", "fails open audibly", "reads the resolver's output variable"
# -- so the text they read must be the SOURCE CHAIN, launcher plus every file
# it sources, or extraction hollows the invariant while the test stays green.
_SOURCE_RE = re.compile(r'^\s*(?:source|\.)\s+("?)([^"\'\s]+)\1')

def _sourced_files(text: str) -> list[Path]:
    files: list[Path] = []
    for line in text.splitlines():
        match = _SOURCE_RE.match(line)
        if not match:
            continue
        source = match.group(2)
        # $ROOT is the repo root the launchers resolve at runtime; the fragment
        # lives beside them, so $ROOT/pmoves/scripts/x.sh == LAUNCHER.parent/x.sh.
        source = source.replace("$ROOT", str(LAUNCHER.parent))
        source = source.replace("${ROOT}", str(LAUNCHER.parent))
        if "$" in source or not source.endswith(".sh"):
            continue
        candidate = Path(source)
        if not candidate.is_file():
            candidate = LAUNCHER.parent / Path(source).name
        if candidate.is_file():
            files.append(candidate)
    return files

def _launcher_text(launcher: Path) -> str:
    """The launcher plus, recursively, everything it sources."""
    text = launcher.read_text(encoding="utf-8")
    seen = {launcher}
    for frag in _sourced_files(text):
        if frag not in seen:
            seen.add(frag)
            text += "\n" + frag.read_text(encoding="utf-8")
    return text


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

@pytest.mark.parametrize("launcher", [LAUNCHER, WIN_LAUNCHER],
                         ids=["posix", "windows"])
def test_both_launchers_invoke_the_resolver(launcher):
    """BOTH, not either.

    The .bat carries its own copy of DEFAULT_AGENT precisely because "Windows
    never executes" the .sh -- and the 4090, the node this work exists for, is
    Windows. An identity wired only into the .sh would have been correct,
    tested, and unreachable on the one machine that needed it. This test is
    parameterised so adding the call to one launcher cannot satisfy it.
    """
    text = launcher.read_text(encoding="utf-8")
    assert "node_identity.py" in text, f"{launcher.name} does not call the resolver"
    assert "--append-system-prompt" in text, (
        f"{launcher.name}: the identity must reach the session's context; an "
        "exported variable does not"
    )


@pytest.mark.parametrize("launcher", [LAUNCHER, WIN_LAUNCHER],
                         ids=["posix", "windows"])
def test_both_launchers_fail_open_audibly(launcher):
    """Losing the identity must never cost the launch, or be silent."""
    text = _launcher_text(launcher)
    assert "launching without it" in text, f"{launcher.name}: no audible fallback"


def test_no_launcher_clears_the_operator_override_before_resolving():
    """PMOVES_NODE_IDENTITY is an INPUT the resolver reads from the environment.

    The Windows launcher cleared it alongside its output variables, destroying
    the override before the tool could honour it -- the documented escape hatch
    silently did nothing. Running the launcher caught it; reading it had not.
    The resolver now answers under PMOVES_RESOLVED_IDENTITY so the two cannot
    collide again.
    """
    for launcher in (LAUNCHER, WIN_LAUNCHER):
        text = _launcher_text(launcher)
        assert 'PMOVES_NODE_IDENTITY=""' not in text, launcher.name
        assert 'set "PMOVES_NODE_IDENTITY="' not in text, launcher.name
        assert "PMOVES_RESOLVED_IDENTITY" in text, (
            f"{launcher.name} does not read the resolver's output variable"
        )


def test_the_windows_launcher_uses_a_cmd_safe_format():
    """cmd.exe has no `eval`: --shell's POSIX quotes would be taken literally,
    setting PMOVES_NODE to the five characters '4090'."""
    # Match the CALL, not the IDENT_TOOL assignment and not the comments:
    # `--harness` appears only on the line that actually runs the tool.
    invocation = [line for line in WIN_LAUNCHER.read_text(encoding="utf-8").splitlines()
                  if "--harness" in line and not line.strip().startswith("rem")]
    assert invocation, "no non-comment line invokes the resolver"
    assert all("--format cmd" in line for line in invocation), invocation
    assert not any("--shell" in line for line in invocation), invocation


def test_the_windows_launcher_has_no_parenthesised_block_around_the_reason():
    """The reason strings contain literal parentheses, and cmd.exe expands
    %VAR% while PARSING a block -- the first `)` closes the block early. The
    first draft died with "but was unexpected at this time." Guarding on the
    goto label rather than the absence of `(`, which appears in comments."""
    text = WIN_LAUNCHER.read_text(encoding="utf-8")
    assert ":ident_why" in text and "goto ident_why" in text, (
        "the reason path must be reached by goto, not an if/else block"
    )
    assert 'echo "[claude-pmoves] identity unresolved: %PMOVES_IDENTITY_WHY%"' in text, (
        "the reason must be echoed quoted -- its parentheses are load-bearing "
        "text, not syntax"
    )


# ---------------------------------------------------------------------------
# CIPHER AGENT IDS — the second namespace.
#
# `default_identity` answers "which registered agent am I". Cipher answers to a
# DIFFERENT spelling, from signing_identity_cards.yaml, and refuses the registry
# one under token enforcement. The two differ on every node (claude_b850 vs
# b850-claude), and because cipher_identity.py tests whatever id it is handed
# against the active card set, feeding it the registry spelling produced a false
# `signing card: no` on every node — a wrong answer that read as a finding.
# ---------------------------------------------------------------------------
CARDS_PATH = REPO_ROOT / "pmoves" / "config" / "signing_identity_cards.yaml"


def _active_card_ids() -> set[str]:
    doc = yaml.safe_load(CARDS_PATH.read_text(encoding="utf-8"))
    cards = doc["cards"] if isinstance(doc, dict) and "cards" in doc else doc
    return {
        (card.get("h") or {}).get("agent_id", "").strip()
        for card in cards
        if isinstance(card, dict) and card.get("active")
    } - {""}


def _vocabulary() -> list[dict]:
    doc = yaml.safe_load((REPO_ROOT / "pmoves" / "configs" / "node-vocabulary.yaml").read_text(encoding="utf-8"))
    return doc.get("nodes") or []


def test_every_declared_cipher_agent_id_names_an_active_card():
    """A declared id that names no active card is a runtime 403 waiting to happen.

    This is the whole reason the mapping is declared rather than derived: a
    declaration can be checked. Revoke a card and CI says so; derive the id from
    a string transform and the first anyone hears is a refused cipher call.
    """
    active = _active_card_ids()
    assert active, f"no active cards parsed from {CARDS_PATH}"
    declared = {
        (node["canonical"], harness): agent_id
        for node in _vocabulary()
        for harness, agent_id in (node.get("cipher_agent_id") or {}).items()
    }
    assert declared, "node-vocabulary.yaml declares no cipher_agent_id at all"
    orphans = {k: v for k, v in declared.items() if v not in active}
    assert not orphans, f"declared cipher agent ids with no active signing card: {orphans}"


def test_a_cipher_agent_id_is_never_the_registry_identity():
    """If the two ever coincide, someone has copied the wrong column."""
    for node in _vocabulary():
        registry = node.get("default_identity") or {}
        for harness, agent_id in (node.get("cipher_agent_id") or {}).items():
            assert agent_id != registry.get(harness), (
                f"{node['canonical']}/{harness}: cipher_agent_id equals the registry "
                f"identity {agent_id!r}; cipher refuses the registry spelling"
            )


def test_an_undeclared_harness_gets_a_reason_not_a_guess():
    """crush's registry identity is crush_glm52 and its card is plain `crush`.

    The `claude_<x>` -> `<x>-claude` transform that fits all four claude-code
    nodes yields `glm52-crush` here, which is no card at all. So the resolver
    must return nothing and SAY SO, not derive.
    """
    module = _module()
    vocab = module.load_vocabulary()
    agent_id, why = module.resolve_cipher_agent_id("crush", "knuckles", vocab=vocab, env={})
    assert agent_id is None, f"invented a cipher agentId for crush: {agent_id!r}"
    assert "crush" in why and "declare" in why, why
    assert "glm52" not in why


def test_an_unknown_node_yields_no_cipher_agent_id():
    module = _module()
    vocab = module.load_vocabulary()
    for node in (None, "", "a-node-that-is-not-declared"):
        agent_id, why = module.resolve_cipher_agent_id("claude-code", node, vocab=vocab, env={})
        assert agent_id is None, (node, agent_id)
        assert why, node


def test_the_operator_may_override_the_cipher_agent_id():
    """Same contract as PMOVES_NODE_IDENTITY: the operator is allowed to know better."""
    module = _module()
    vocab = module.load_vocabulary()
    agent_id, why = module.resolve_cipher_agent_id(
        "claude-code", "knuckles", vocab=vocab, env={"PMOVES_CIPHER_AGENT_ID": "someone-else"},
    )
    assert agent_id == "someone-else"
    assert "PMOVES_CIPHER_AGENT_ID" in why


def test_every_claude_code_node_declares_a_cipher_agent_id():
    """Partial coverage here is the failure mode: a node with a registry identity
    but no agentId gets a session that cannot call cipher at all."""
    missing = [
        node["canonical"]
        for node in _vocabulary()
        if (node.get("default_identity") or {}).get("claude-code")
        and not (node.get("cipher_agent_id") or {}).get("claude-code")
    ]
    assert not missing, f"claude-code nodes with an identity but no cipher agentId: {missing}"


def test_the_shell_output_always_carries_the_cipher_fields():
    """Empty-with-a-reason, never absent: a launcher that greps for the variable
    must not read a stale value from its parent environment."""
    import os
    import subprocess

    env = dict(os.environ, PMOVES_NODE_ID="pmoves-5090")
    env.pop("PMOVES_NODE_IDENTITY", None)
    env.pop("PMOVES_CIPHER_AGENT_ID", None)
    for harness in ("claude-code", "crush", "a-harness-that-does-not-exist"):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "pmoves" / "tools" / "node_identity.py"),
             "--harness", harness, "--shell"],
            capture_output=True, text=True, env=env, timeout=60,
        )
        assert proc.returncode == 0, (harness, proc.stderr)
        keys = {line.split("=", 1)[0] for line in proc.stdout.splitlines()}
        assert "PMOVES_CIPHER_AGENT_ID" in keys, (harness, proc.stdout)
        assert "PMOVES_CIPHER_AGENT_WHY" in keys, (harness, proc.stdout)
