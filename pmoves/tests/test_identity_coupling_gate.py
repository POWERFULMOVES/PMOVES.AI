"""Every declared node identity must be wired -- generically, for every node.

`node-vocabulary.yaml` declares who a session on a node IS:

    <node>.default_identity.<harness>: <agent_id>

That is a reference into `agent_registry.yaml`, and nothing verified it. The
registry/teams gate never opened the vocabulary; the only enforcement anywhere
was a hand-written assertion for the single pair `knuckles.crush`
(test_crush_node_identity.py). So `4090.claude-code` and `knuckles.claude-code`
were unguarded, and any identity added later inherited that.

The gap is reachable, not theoretical. PR #2766's registry conflict interleaves
mid-mapping, so an `--ours` resolution drops two agents from the registry AND
the teams file while the vocabulary -- which merges cleanly and conflicts with
nothing -- keeps declaring them. Registry and teams then agree with each other,
the coupling gate reports "no new drift", and two nodes launch every session
unbound. The opposite resolution deletes an agent the teams file still lists and
IS caught, which is what made the guard asymmetric.

These tests hold both halves:
  * the invariant itself, parametrised over EVERY declared pair rather than one
    hand-picked one, so a new declaration is covered the moment it is written;
  * that the gate which enforces it can actually go red -- run against a
    mutated registry, not merely inspected for the presence of the code.

Enforcement note: these run under the required `python-tests` merge check,
which discovers `test_*.py` repo-wide via pmoves/tools/pytest_ratchet.py. The
same assertions also run in `validate_agent_registry.py` (make -C pmoves
validate-agents; .github/workflows/validate-agents-config.yml).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = REPO_ROOT / "pmoves" / "configs" / "node-vocabulary.yaml"
REGISTRY = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"
TEAMS = REPO_ROOT / "pmoves" / "configs" / "agent-teams.yaml"
VALIDATOR = REPO_ROOT / "pmoves" / "scripts" / "validate_agent_registry.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ni = _load(REPO_ROOT / "pmoves" / "tools" / "node_identity.py", "node_identity")


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _declarations() -> list[tuple[str, str, str]]:
    """Every (node, harness, agent_id) the vocabulary declares."""
    out = []
    for entry in _yaml(VOCABULARY).get("nodes") or []:
        node = str(entry.get("canonical", ""))
        for harness, agent_id in sorted((entry.get("default_identity") or {}).items()):
            out.append((node, harness, agent_id))
    return out


DECLARATIONS = _declarations()


def test_the_vocabulary_declares_at_least_one_identity():
    """A guard on the parametrisation itself.

    Every test below is parametrised over DECLARATIONS. If the vocabulary were
    emptied, renamed, or restructured, that list would be empty, pytest would
    report zero tests, and the suite would go green having asserted nothing --
    the precise failure mode this whole lane exists to close.
    """
    assert DECLARATIONS, (
        f"no default_identity declarations found in {VOCABULARY.name}; either "
        "the file moved or its shape changed, and the checks below are "
        "silently vacuous")


@pytest.mark.parametrize("node,harness,agent_id", DECLARATIONS,
                         ids=[f"{n}.{h}" for n, h, _ in DECLARATIONS])
def test_declared_identity_is_registered(node, harness, agent_id):
    agents = _yaml(REGISTRY)["agents"]
    assert agent_id in agents, (
        f"{node}.default_identity.{harness} declares {agent_id!r}, which is in "
        f"no agent_registry.yaml entry: declared and not wired. Every "
        f"{harness} session on {node} launches unbound.")


@pytest.mark.parametrize("node,harness,agent_id", DECLARATIONS,
                         ids=[f"{n}.{h}" for n, h, _ in DECLARATIONS])
def test_declared_identity_claims_the_node_it_is_declared_for(node, harness, agent_id):
    # The resolver's own view: registry spellings are folded through the
    # vocabulary's alias map, so `pmoves-b850` and `knuckles` are one node and
    # the integer `5090` is not distinct from the string.
    vocab = ni.load_vocabulary(VOCABULARY)
    registry = ni.load_registry(REGISTRY)
    claiming = ni.agents_claiming(node, registry, vocab)
    assert agent_id in claiming, (
        f"{agent_id!r} is declared for {node} but its node_affinity does not "
        f"resolve there (claimants: {', '.join(claiming) or 'none'}). "
        "resolve_identity() refuses to bind an identity to a node it does not "
        "claim, so this is unbound too.")


@pytest.mark.parametrize("node,harness,agent_id", DECLARATIONS,
                         ids=[f"{n}.{h}" for n, h, _ in DECLARATIONS])
def test_declared_identity_belongs_to_a_team(node, harness, agent_id):
    teams = _yaml(TEAMS).get("teams") or {}
    owning = [t for t, spec in teams.items()
              if agent_id in ((spec or {}).get("agents") or [])]
    assert owning, (
        f"{agent_id!r} is declared for {node}.{harness} and registered, but is "
        "in no agent-teams.yaml team -- the coupling #2754/#2763 established.")
    assert len(owning) == 1, f"{agent_id!r} is in more than one team: {owning}"


@pytest.mark.parametrize("node,harness,agent_id", DECLARATIONS,
                         ids=[f"{n}.{h}" for n, h, _ in DECLARATIONS])
def test_the_declared_identity_actually_resolves(node, harness, agent_id):
    """End-to-end through the resolver, for a node this test is not running on.

    The three checks above assert the data. This asserts the thing the data
    exists for: that `resolve_identity()` returns the identity rather than one
    of its four refusal reasons. Hostname and env are injected, which is what
    makes it possible to verify the 5090's and z890's bindings from here --
    with the limit stated plainly: this proves the CONFIGURATION resolves, not
    that the machine is reachable or that anyone has run a session on it.
    """
    got_node, identity, why = ni.resolve_identity(
        harness,
        vocab=ni.load_vocabulary(VOCABULARY),
        registry=ni.load_registry(REGISTRY),
        env={"PMOVES_NODE_ID": node},
        hostname="unused-when-PMOVES_NODE_ID-is-set",
    )
    assert (got_node, identity) == (node, agent_id), why


# --- The gate that enforces the above must be able to go red ----------------
# Asserting the invariant holds is not the same as asserting something would
# catch it if it stopped holding. These run the real validator against mutated
# copies of the three files and require a non-zero exit -- the difference
# between a gate that is present and a gate that is wired.

def _run_gate_against(tmp_path, monkeypatch, registry, vocabulary, teams) -> tuple[int, str]:
    gate = _load(VALIDATOR, "validate_agent_registry")
    written = {}
    for name, doc, filename in (
        ("REGISTRY", registry, "agent_registry.yaml"),
        ("VOCABULARY", vocabulary, "node-vocabulary.yaml"),
        ("TEAMS", teams, "agent-teams.yaml"),
    ):
        path = tmp_path / filename
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        written[name] = path
        # raising=False on purpose. Reverting the validator to its pre-gate
        # state removes VOCABULARY entirely, and a setup AttributeError would
        # make the negative control below prove only that the constant is
        # missing. Tolerating it lets the old validator actually RUN against
        # the mutated files, so the control demonstrates the real defect: it
        # reads a registry and a teams file that agree with each other and
        # exits 0 while the vocabulary declares an agent neither contains.
        monkeypatch.setattr(gate, name, path, raising=False)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = gate.main([])
    return code, buf.getvalue()


def test_gate_is_green_on_the_real_files(tmp_path, monkeypatch):
    """The control. Without it, a red below proves nothing -- a gate that fails
    on everything is as useless as one that fails on nothing."""
    code, out = _run_gate_against(
        tmp_path, monkeypatch, _yaml(REGISTRY), _yaml(VOCABULARY), _yaml(TEAMS))
    assert code == 0, out


def test_gate_goes_red_when_a_declared_identity_is_dropped_from_the_registry(
        tmp_path, monkeypatch):
    """Reconstructs PR #2766's `--ours` resolution: the registry loses the
    agent, the vocabulary keeps declaring it."""
    node, harness, agent_id = DECLARATIONS[0]
    registry = _yaml(REGISTRY)
    registry["agents"].pop(agent_id)
    teams = _yaml(TEAMS)
    for spec in (teams.get("teams") or {}).values():
        if agent_id in ((spec or {}).get("agents") or []):
            spec["agents"].remove(agent_id)

    code, out = _run_gate_against(
        tmp_path, monkeypatch, registry, _yaml(VOCABULARY), teams)
    assert code == 1, f"gate stayed green with {agent_id!r} declared-not-wired:\n{out}"
    assert "DECLARED AND NOT WIRED" in out, out
    assert f"{node}.default_identity.{harness}" in out, out


def test_gate_goes_red_when_a_declared_identity_does_not_claim_its_node(
        tmp_path, monkeypatch):
    """The second way to be unbound: registered, teamed, wrong machine."""
    node, harness, agent_id = DECLARATIONS[0]
    registry = _yaml(REGISTRY)
    registry["agents"][agent_id]["topology"]["node_affinity"] = ["nano-1"]
    code, out = _run_gate_against(
        tmp_path, monkeypatch, registry, _yaml(VOCABULARY), _yaml(TEAMS))
    assert code == 1, out
    assert "does not resolve to" in out, out


def test_gate_reports_every_violation_not_only_the_first(tmp_path, monkeypatch):
    """A gate that stops at the first error hides the rest -- and #2766's own
    `--ours` resolution produces exactly two at once."""
    if len(DECLARATIONS) < 2:
        pytest.skip("needs two declarations to distinguish first-only reporting")
    registry = _yaml(REGISTRY)
    teams = _yaml(TEAMS)
    dropped = []
    for node, harness, agent_id in DECLARATIONS:
        if agent_id in registry["agents"] and agent_id not in dropped:
            registry["agents"].pop(agent_id)
            for spec in (teams.get("teams") or {}).values():
                if agent_id in ((spec or {}).get("agents") or []):
                    spec["agents"].remove(agent_id)
            dropped.append(agent_id)

    code, out = _run_gate_against(
        tmp_path, monkeypatch, registry, _yaml(VOCABULARY), teams)
    assert code == 1, out
    missing = [a for a in dropped if a not in out]
    assert not missing, (
        f"gate reported only some violations; {missing} absent from:\n{out}")


def test_gate_reports_a_duplicate_alias_instead_of_crashing(tmp_path, monkeypatch):
    """load_vocabulary() raises GLOBALLY on a duplicate alias, so it breaks
    identity resolution on every node at once. It must surface as a gate error
    naming the file, never as a traceback that aborts the run and suppresses
    the report for everything else."""
    vocabulary = _yaml(VOCABULARY)
    nodes = vocabulary["nodes"]
    stolen = str(nodes[0]["canonical"])
    nodes[1].setdefault("aliases", []).append(stolen)

    code, out = _run_gate_against(
        tmp_path, monkeypatch, _yaml(REGISTRY), vocabulary, _yaml(TEAMS))
    assert code == 1, out
    assert "must name exactly one node" in out, out
    # The rest of the report still ran.
    assert "registry agents:" in out, out


def test_gate_goes_red_when_a_node_affinity_token_is_unknown(
        tmp_path, monkeypatch):
    """The registry -> vocabulary direction: a node_affinity token the
    vocabulary does not know is the name-bound-in-one-context-consumed-in-
    another defect class (4090-open-findings-2026-08-31). It must fail the
    gate naming the agent and the token."""
    registry = _yaml(REGISTRY)
    first = next(iter(registry["agents"]))
    registry["agents"][first].setdefault("topology", {})["node_affinity"] = [
        "kvm4-1", "not-a-node-anywhere",
    ]

    code, out = _run_gate_against(
        tmp_path, monkeypatch, registry, _yaml(VOCABULARY), _yaml(TEAMS))
    assert code == 1, out
    assert "does not resolve in node-vocabulary.yaml" in out, out
    assert "not-a-node-anywhere" in out, out
    assert first in out, out


def test_gate_accepts_declared_non_node_kinds(tmp_path, monkeypatch):
    """placeholder / runner-label / class kinds are declared concepts, not
    unknown spellings -- [any], [cloud] and [ai-lab] are live registry values.
    They pass: the gate rejects unknown spellings, not declared concepts."""
    registry = _yaml(REGISTRY)
    first = next(iter(registry["agents"]))
    registry["agents"][first].setdefault("topology", {})["node_affinity"] = [
        "any", "cloud", "ai-lab",
    ]

    code, out = _run_gate_against(
        tmp_path, monkeypatch, registry, _yaml(VOCABULARY), _yaml(TEAMS))
    assert code == 0, out
