"""claude-pmoves must wake the session up AS the node identity, not as a role.

Operator direction 2026-09-27: "I need to be talking with B850-CLAUDE when I run
claude-pmoves ... ensure that B850-CLAUDE is what claude-pmoves wakes up."

WHAT WAS WRONG
--------------
The launcher's appended prompt said "You are running on PMOVES node 'knuckles'.
Your registered identity in pmoves/config/agent_registry.yaml is 'claude_b850'.
... Your selected role for this session is the 'node-steward' agent." It named
only the registry key -- never `B850-CLAUDE`, the name the fleet uses, nor
`B850-CLAUDE (Knuckles)`, the owner string the register carries -- and put the
role last. node-steward.md then described "this node's CLI identity" as the
party directing it. The session woke up as the role and spoke of B850-CLAUDE in
the third person.

WHAT THESE TESTS HOLD
---------------------
1. The resolver names all four claude-code nodes, from DECLARED data
   (identity_vocabulary.yaml `register_form`), and every name folds back to its
   own identity under the collision gate's fold -- so what the launcher tells a
   session to sign with is attributed to that session's identity.
2. The COMPOSED ARGV the harness receives (stub `claude` on PATH, as in
   test_launcher_prompt_accumulation.py) carries exactly one prompt flag and the
   prompt BEGINS with "You are <name>," for each node.
3. The second-session rule survives: PMOVES_REGISTER_IDENTITY names a distinct
   base identity, and one declared for another node is refused with a loud
   fallback, never answered with the primary's name.

Expected names are taken from the resolver, not hardcoded, except where a second
declared source exists to cross-check against (NODE_PROFILES/*.md).
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "pmoves" / "tools"
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh"
PS1 = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"
STEWARD = REPO_ROOT / ".claude" / "agents" / "node-steward.md"
IDENTITY_VOCAB = REPO_ROOT / "pmoves" / "config" / "identity_vocabulary.yaml"
NODE_PROFILES = REPO_ROOT / "pmoves" / "docs" / "NODE_PROFILES"
FLAG = "--append-system-prompt"

sys.path.insert(0, str(TOOLS))
import identity_lineage  # noqa: E402
import node_identity  # noqa: E402

# The four claude-code nodes, by an alias each resolves from. Every one is forced
# through PMOVES_NODE_ID, so the result does not depend on which host runs this.
CLAUDE_NODES = ["pmoves-4090", "pmoves-5090", "z890", "knuckles"]

CIPHER_STUB_UP = """#!/usr/bin/env python3
print("cipher OK stub-endpoint (test stub)")
raise SystemExit(0)
"""

ARGV_DUMPER = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\0' "$a"; done > "$ARGV_OUT"
"""

# Env a developer's own session may carry, any of which would silently steer
# the resolver away from the node the test forces.
_STEERING = ("PMOVES_NODE_IDENTITY", "PMOVES_REGISTER_IDENTITY", "PMOVES_CIPHER_AGENT_ID",
             "PMOVES_IDENTITY_NAME", "PMOVES_REGISTER_FORM", "PMOVES_REGISTER_WHY")


def _clean_env(node_id: str, **extra: str) -> dict[str, str]:
    env = dict(os.environ)
    for key in _STEERING:
        env.pop(key, None)
    env["PMOVES_NODE_ID"] = node_id
    env.update(extra)
    return env


def _resolve(node_id: str, **extra: str) -> dict[str, str]:
    proc = subprocess.run(
        [sys.executable, str(TOOLS / "node_identity.py"), "--harness", "claude-code", "--shell"],
        capture_output=True, text=True, env=_clean_env(node_id, **extra), timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        # POSIX-quoted by the resolver (reasons carry embedded quotes), so
        # parse it the way the shell's eval would.
        parts = shlex.split(value) if value else []
        out[key] = parts[0] if parts else ""
    return out


def _bash() -> str:
    found = shutil.which("bash")
    if not found:
        pytest.skip("bash not available")
    return found


def _fake_root(tmp_path: Path) -> Path:
    """A PMOVES_LAUNCHER_ROOT with the real resolvers and a cipher-up stub.

    `deploy/provision` is absent, which takes the launcher's direct
    `exec claude` path -- the one whose argv the stub can read.
    """
    root = tmp_path / "root"
    (root / "pmoves").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / "pmoves" / "scripts").symlink_to(REPO_ROOT / "pmoves" / "scripts")
    (root / "pmoves" / "config").symlink_to(REPO_ROOT / "pmoves" / "config")
    (root / ".claude" / "agents").symlink_to(REPO_ROOT / ".claude" / "agents")
    tools = root / "pmoves" / "tools"
    tools.mkdir()
    for name in ("node_identity.py", "cipher_identity.py"):
        (tools / name).symlink_to(TOOLS / name)
    stub = tools / "cipher_preflight.py"
    stub.write_text(CIPHER_STUB_UP, encoding="utf-8")
    stub.chmod(0o755)
    return root


def _launch(tmp_path: Path, node_id: str, *, launcher: Path = LAUNCHER,
            **extra: str) -> tuple[list[str], str]:
    root = _fake_root(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "claude"
    shim.write_text(ARGV_DUMPER, encoding="utf-8")
    shim.chmod(0o755)
    argv_out = tmp_path / "argv.bin"
    env = _clean_env(node_id, **extra)
    env.update(PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
               PMOVES_LAUNCHER_ROOT=str(root), ARGV_OUT=str(argv_out))
    proc = subprocess.run([_bash(), str(launcher), "--print", "hi"],
                          capture_output=True, text=True, env=env, timeout=180)
    assert proc.returncode == 0, proc.stderr
    assert argv_out.exists(), f"the claude shim was never reached; stderr:\n{proc.stderr}"
    raw = argv_out.read_bytes()
    return [p.decode("utf-8") for p in raw.split(b"\0")[:-1]], proc.stderr


def _one_prompt(argv: list[str]) -> str:
    assert argv.count(FLAG) == 1, f"expected exactly one {FLAG}: {argv!r}"
    return argv[argv.index(FLAG) + 1]


# ---------------------------------------------------------------------------
# 1. The resolver names every claude node, from declared data.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", CLAUDE_NODES)
def test_every_claude_node_resolves_a_name_and_register_form(node_id: str):
    out = _resolve(node_id)
    registry_key = out["PMOVES_RESOLVED_IDENTITY"]
    name, form = out["PMOVES_IDENTITY_NAME"], out["PMOVES_REGISTER_FORM"]
    assert registry_key, out
    assert name and form, f"{node_id}: no register name -- {out.get('PMOVES_REGISTER_WHY')}"
    assert form.split("(", 1)[0].strip() == name
    # The fold the collision gate applies: what the session is told to sign
    # with must attribute to the SAME identity its registry key names. If these
    # diverge, the launcher hands out an owner string the gate files elsewhere.
    vocab = identity_lineage.load_vocabulary()
    assert identity_lineage.canonical_identity(form, vocab) == \
        identity_lineage.canonical_identity(registry_key, vocab), (node_id, form, registry_key)


def test_the_four_names_are_distinct():
    names = {n: _resolve(n)["PMOVES_IDENTITY_NAME"] for n in CLAUDE_NODES}
    assert len(set(names.values())) == len(CLAUDE_NODES), names


def test_node_profiles_agree_with_the_declared_register_form():
    """A second declared source exists for two nodes; they must not disagree."""
    vocab = identity_lineage.load_vocabulary()
    forms = {str(e["canonical"]): e.get("register_form")
             for e in yaml.safe_load(IDENTITY_VOCAB.read_text(encoding="utf-8"))["identities"]}
    checked = 0
    for profile in sorted(NODE_PROFILES.glob("*.md")):
        match = re.search(r"Canonical[^\n`]*?name[^\n`]*?`([^`]+)`", profile.read_text(encoding="utf-8"))
        if not match:
            continue
        declared = match.group(1)
        canonical = identity_lineage.canonical_identity(declared, vocab)
        assert canonical, f"{profile.name}: {declared!r} does not resolve"
        assert forms.get(canonical) == declared, (profile.name, declared, forms.get(canonical))
        checked += 1
    assert checked >= 2, f"expected the 4090 and B850 profiles to declare a name; checked {checked}"


def test_every_declared_register_form_folds_back_to_its_own_identity():
    vocab = identity_lineage.load_vocabulary()
    doc = yaml.safe_load(IDENTITY_VOCAB.read_text(encoding="utf-8"))
    declared = [(str(e["canonical"]), e["register_form"]) for e in doc["identities"]
                if e.get("register_form")]
    assert len(declared) >= 5, declared
    for canonical, form in declared:
        assert identity_lineage.canonical_identity(form, vocab) == canonical, (canonical, form)


def test_an_undeclared_register_form_is_a_reason_not_a_guess(tmp_path: Path):
    vocab_file = tmp_path / "identity_vocabulary.yaml"
    vocab_file.write_text(yaml.safe_dump({"version": 1, "identities": [
        {"canonical": "b850-claude", "aliases": ["B850-CLAUDE", "claude_b850"], "node": "knuckles"},
    ]}), encoding="utf-8")
    name, form, why = node_identity.resolve_register_name(
        "claude_b850", "knuckles", env={}, path=vocab_file)
    assert (name, form) == (None, None)
    assert "no register_form" in why


# ---------------------------------------------------------------------------
# 2. The composed argv: the prompt BEGINS with the name, for every node.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", CLAUDE_NODES)
def test_the_prompt_begins_with_the_resolved_name(tmp_path: Path, node_id: str):
    out = _resolve(node_id)
    name, form = out["PMOVES_IDENTITY_NAME"], out["PMOVES_REGISTER_FORM"]
    argv, stderr = _launch(tmp_path, node_id)
    prompt = _one_prompt(argv)
    assert prompt.startswith(f"You are {name},"), (
        f"{node_id}: the session is not told it IS {name!r}; prompt opens with:\n"
        f"{prompt[:240]!r}\nstderr:\n{stderr}"
    )
    assert f"'{form}'" in prompt, f"register form {form!r} missing:\n{prompt}"
    assert out["PMOVES_RESOLVED_IDENTITY"] in prompt        # registry key still carried
    assert "'node-steward' role" in prompt                   # role stated as the job
    # The third-person framing must not reach the session on the bound path.
    assert "Your selected role for this session" not in prompt


def test_the_role_follows_the_name_not_the_other_way_round(tmp_path: Path):
    argv, _ = _launch(tmp_path, "knuckles")
    prompt = _one_prompt(argv)
    name = _resolve("knuckles")["PMOVES_IDENTITY_NAME"]
    assert prompt.index(name) < prompt.index("node-steward")


# ---------------------------------------------------------------------------
# 3. The second-session rule, and fail-open loudly.
# ---------------------------------------------------------------------------

def test_a_second_session_wakes_as_its_own_base_identity(tmp_path: Path):
    out = _resolve("knuckles", PMOVES_REGISTER_IDENTITY="B850-CLAUDE-FUNNEL")
    assert out["PMOVES_IDENTITY_NAME"] == "B850-CLAUDE-FUNNEL", out
    argv, _ = _launch(tmp_path, "knuckles", PMOVES_REGISTER_IDENTITY="B850-CLAUDE-FUNNEL")
    prompt = _one_prompt(argv)
    assert prompt.startswith("You are B850-CLAUDE-FUNNEL,"), prompt[:200]
    assert "'B850-CLAUDE-FUNNEL (Knuckles)'" in prompt
    # Never the primary's owner string: that is the collision the rule prevents.
    assert "'B850-CLAUDE (Knuckles)'" not in prompt


def test_an_identity_from_another_node_is_refused_loudly(tmp_path: Path):
    out = _resolve("knuckles", PMOVES_REGISTER_IDENTITY="Z890-CLAUDE")
    assert out["PMOVES_IDENTITY_NAME"] == "", out
    assert "not 'knuckles'" in out["PMOVES_REGISTER_WHY"], out
    argv, stderr = _launch(tmp_path, "knuckles", PMOVES_REGISTER_IDENTITY="Z890-CLAUDE")
    prompt = _one_prompt(argv)
    assert not prompt.startswith("You are Z890-CLAUDE")
    assert not prompt.startswith("You are B850-CLAUDE"), "fell back to the primary's name"
    assert prompt.startswith("You are running on PMOVES node 'knuckles'"), prompt[:200]
    assert "identity name unresolved" in stderr, stderr


def test_an_unknown_override_falls_back_with_the_reason_on_stderr(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "knuckles", PMOVES_REGISTER_IDENTITY="NO-SUCH-IDENTITY")
    prompt = _one_prompt(argv)
    assert prompt.startswith("You are running on PMOVES node 'knuckles'"), prompt[:200]
    assert "identity name unresolved" in stderr and "NO-SUCH-IDENTITY" in stderr, stderr


# ---------------------------------------------------------------------------
# 4. The Windows twin and the role definition say the same thing.
# ---------------------------------------------------------------------------

def test_the_windows_twin_reads_the_same_outputs_and_leads_with_the_name():
    """Text-level: pwsh is not assumed on a POSIX CI host, so this cannot run it."""
    text = PS1.read_text(encoding="utf-8")
    for key in ("PMOVES_IDENTITY_NAME", "PMOVES_REGISTER_FORM", "PMOVES_REGISTER_WHY"):
        assert key in text, f"claude-pmoves.ps1 never reads {key}"
    assert '"You are $identName, the Claude Code agent for PMOVES node' in text
    # The old line told a Windows session to file register rows under the
    # REGISTRY key; the register form is what the gate folds.
    assert "file claim-register rows under it" not in text


def test_the_steward_is_the_identity_not_its_subordinate():
    body = STEWARD.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    assert "it is admin over this role" not in body
    assert "You are directed by **this node's CLI identity**" not in body
    assert "You are this node's Claude identity" in body
