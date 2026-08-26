"""The crush half of node identity: declared, resolvable, and delivered.

#2751 wired the resolver into claude-pmoves only; crush-pmoves had zero
references, which is how a registered lane owner (CRUSH-GLM52 on Knuckles)
could operate with the launcher unable to tell the session who it is. These
tests hold the crush side to the same bar the claude side already meets:

  * the vocabulary declares a crush identity for knuckles, and it exists in
    the registry with affinity for that node (declare-never-infer cuts both
    ways: the declaration must be wired, not just written down);
  * the launcher actually calls the resolver and writes the context file --
    Crush has no --append-system-prompt, so a context file that the
    configurator lists in context_paths is the delivery mechanism;
  * the configurator lists that file, so the file that gets written is the
    file that gets loaded.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = REPO_ROOT / "pmoves" / "configs" / "node-vocabulary.yaml"
REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "crush-pmoves"
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"

IDENTITY_FILE_REL = "pmoves/data/identity/node-identity.md"


def _module():
    path = REPO_ROOT / "pmoves" / "tools" / "node_identity.py"
    spec = importlib.util.spec_from_file_location("node_identity", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["node_identity"] = module
    spec.loader.exec_module(module)
    return module


ni = _module()


def _vocab_nodes() -> dict:
    doc = yaml.safe_load(VOCABULARY.read_text(encoding="utf-8"))
    return {entry["canonical"]: entry for entry in doc["nodes"]}


def _registry_agents() -> dict:
    doc = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return doc["agents"]


def test_knuckles_declares_a_crush_identity():
    entry = _vocab_nodes()["knuckles"]
    declared = entry.get("default_identity", {}).get("crush")
    assert declared, (
        "knuckles has no default_identity.crush — the resolver will report "
        "'no identity is declared for harness crush' and crush-pmoves "
        "launches unbound. Declare one (declare, never infer)."
    )


def test_the_declared_crush_identity_is_registered_and_bound_to_the_node():
    declared = _vocab_nodes()["knuckles"]["default_identity"]["crush"]
    agents = _registry_agents()
    assert declared in agents, (
        f"{declared!r} is declared in the vocabulary but absent from the "
        "registry: declared and not wired."
    )
    # The resolver's own view of who claims a node: registry spellings are
    # normalized through the vocabulary's alias map (pmoves-b850 == knuckles).
    vocab = ni.load_vocabulary()
    registry = ni.load_registry()
    claiming = ni.agents_claiming("knuckles", registry, vocab)
    assert declared in claiming, (
        f"{declared!r} is registered but does not claim knuckles "
        f"(claimants: {', '.join(claiming) or 'none'}); an identity that does "
        "not bind to the node it is declared for is a misbinding."
    )


def test_launcher_resolves_and_writes_the_context_file():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "--harness crush" in text, (
        "crush-pmoves must call node_identity.py with --harness crush; "
        "without it the resolver answers for claude-code or nothing."
    )
    assert "node-identity.md" in text, (
        "crush-pmoves must write the identity context file — Crush has no "
        "--append-system-prompt, so the file IS the delivery mechanism."
    )
    # The write must precede crush-bootstrap: the configurator's exists()
    # check decides whether the file lands in context_paths, and on a first
    # run there is nothing to exists() until the launcher writes it. Match the
    # make invocation, not comment text that merely mentions the target.
    write_pos = text.index("node-identity.md")
    bootstrap_pos = re.search(r"make -C [^\n]*crush-bootstrap", text).start()
    assert write_pos < bootstrap_pos, (
        "the identity file must be written BEFORE crush-bootstrap runs, or "
        "the first bootstrap omits it from context_paths entirely."
    )


def test_launcher_writes_even_on_failure():
    """Every branch writes the file — silence is the defect being fixed."""
    text = LAUNCHER.read_text(encoding="utf-8")
    writes = re.findall(r'> "\$IDENTITY_FILE"', text)
    assert len(writes) >= 3, (
        "resolver-ok, resolver-failed, and resolver-unavailable must each "
        "write the identity file; a branch that skips the write leaves stale "
        "identity content from a previous launch in front of the model."
    )


def test_configurator_lists_the_identity_file():
    text = CONFIGURATOR.read_text(encoding="utf-8")
    assert IDENTITY_FILE_REL in text, (
        "crush_configurator must include the identity context file in "
        "context_candidates, or the launcher writes a file nothing loads."
    )


def test_identity_file_is_gitignored():
    """Runtime per-node state; a committed copy would drift stale instantly."""
    ignored = REPO_ROOT / ".gitignore"
    lines = ignored.read_text(encoding="utf-8").splitlines()
    assert IDENTITY_FILE_REL in lines, (
        f"{IDENTITY_FILE_REL} must be listed in .gitignore verbatim."
    )
