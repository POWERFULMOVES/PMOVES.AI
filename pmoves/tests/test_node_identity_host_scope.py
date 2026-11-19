"""Host scope: the node identity holds the node; the agents it creates do not.

`scope.host_access: node` + `scope.host_roots` on a registry identity become
`--add-dir=<root>` on the MAIN session only. A session launched with
`--agent <role>` is a role, not the node identity, and stays repo-scoped.

Three layers, each measured rather than read:
1. the resolver (`node_identity.resolve_host_roots`) on synthetic and real
   registry data;
2. the composed argv a stub `claude` receives from pmoves/scripts/claude-pmoves.sh;
3. the Windows twin's wiring (static: the ps1 needs a Windows runner to execute).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from pmoves.tests.test_launcher_wakes_as_identity import (
    PS1,
    _launch,
    _resolve,
    node_identity,
)

Z890_ROOTS = ["C:/", "D:/", "I:/", "N:/"]


# ---------------------------------------------------------------------------
# 1. The resolver.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "entry, expected_roots, why_fragment",
    [
        ({}, [], "declares no scope.host_access: node"),
        ({"scope": {"host_access": "repo", "host_roots": ["C:/"]}}, [], "declares no scope.host_access: node"),
        ({"scope": {"host_access": "node"}}, [], "no scope.host_roots"),
        ({"scope": {"host_access": "node", "host_roots": "C:/"}}, [], "no scope.host_roots"),
        ({"scope": {"host_access": "node", "host_roots": ["C:/a|b"]}}, [], "contains '|'"),
        ({"scope": {"host_access": "node", "host_roots": ["C:/", "", 3, "D:/"]}}, ["C:/", "D:/"], "host_access: node"),
    ],
)
def test_resolver_grants_roots_only_for_a_declared_node_scope(entry, expected_roots, why_fragment):
    roots, why = node_identity.resolve_host_roots("x", {"x": entry})
    assert roots == expected_roots
    assert why_fragment in why


def test_an_unresolved_identity_gets_no_roots():
    roots, why = node_identity.resolve_host_roots(None, {})
    assert roots == [] and "identity unresolved" in why


def test_the_real_registry_grants_z890_and_no_other_claude_node():
    assert _resolve("z890")["PMOVES_HOST_ROOTS"] == "|".join(Z890_ROOTS)
    for node in ("pmoves-4090", "pmoves-5090", "knuckles"):
        out = _resolve(node)
        assert out["PMOVES_HOST_ROOTS"] == "", f"{node} unexpectedly has host roots"
        assert out["PMOVES_HOST_WHY"], f"{node}: empty roots carry no reason"


def test_max_subagent_scope_is_repo_wherever_host_access_is_node():
    registry = node_identity.load_registry()
    for key, entry in registry.items():
        scope = entry.get("scope") or {}
        if scope.get("host_access") == "node":
            assert scope.get("max_subagent_scope") == "repo", (
                f"{key}: a node-scoped identity must cap what it creates at repo")


# ---------------------------------------------------------------------------
# 2. The composed argv (bash launcher, stub claude).
# ---------------------------------------------------------------------------

def _add_dirs(argv: list[str]) -> list[str]:
    return [a.split("=", 1)[1] for a in argv if a.startswith("--add-dir=")]


def test_the_z890_main_session_gets_every_host_root(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "z890")
    assert _add_dirs(argv) == Z890_ROOTS, f"argv={argv!r}\nstderr:\n{stderr}"
    # `=` form only: the space form would let the variadic option swallow a prompt.
    assert "--add-dir" not in argv
    # The trailing positional prompt still reaches claude as the last word.
    assert argv[-2:] == ["--print", "hi"]
    assert "host scope: C:/, D:/, I:/, N:/ (main session only)" in stderr


def test_a_role_session_on_z890_stays_repo_scoped(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "z890", PMOVES_DEFAULT_AGENT="node-steward")
    assert "--agent" in argv, f"the role was not selected; argv={argv!r}"
    assert _add_dirs(argv) == [], f"a role session got host roots: {argv!r}"
    assert "host scope: repo (--agent node-steward" in stderr


def test_a_node_without_a_scope_gets_no_host_roots(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "knuckles")
    assert _add_dirs(argv) == []
    assert "host scope: repo (" in stderr


# ---------------------------------------------------------------------------
# 3. The Windows twin.
# ---------------------------------------------------------------------------

def test_the_ps1_passes_host_args_on_both_claude_calls_and_gates_on_the_role():
    text = PS1.read_text(encoding="utf-8")
    calls = re.findall(r"^\s*& claude .*$", text, flags=re.M)
    assert calls and all("@hostArgs @identityArgs" in c for c in calls), calls
    assert "$ident['PMOVES_HOST_ROOTS']" in text
    assert re.search(r"if \(-not \$hostRole -and \$ident\['PMOVES_RESOLVED_IDENTITY'\] -and \$hostRoots\)", text)
    assert '"--add-dir=$__r"' in text
