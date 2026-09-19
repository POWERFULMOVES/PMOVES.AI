"""The launcher's prompt must reach the harness's argv, not merely its array.

WHY THIS FILE IS NOT IN test_node_identity.py
---------------------------------------------
Those tests read launcher TEXT. This one runs the launcher.

`claude --append-system-prompt` does not accumulate: the LAST occurrence wins
and earlier ones are discarded with no warning, no log line, and a zero exit.
claude-pmoves.sh pushed three contributors -- node identity, cipher status, the
identity-carry verdict -- onto one array as separate flags, so only the last
ever reached the model, and the node identity (the FIRST contributor) was the
one that never arrived.

A test asserting "the identity string is present in IDENTITY_ARGS" would have
passed throughout that entire defect. The string was in the array on every path.
It was lost one layer further out, in the argv the harness parses. So these
tests assert on the COMPOSED ARGV, captured from a stub `claude` that writes
what it was actually given.

HERMETIC, EXCEPT WHERE IT MUST NOT BE
-------------------------------------
The launcher runs under a temporary PMOVES_LAUNCHER_ROOT holding symlinks to the
real resolvers and a STUB cipher_preflight.py, so the cipher branch is chosen by
the test rather than by whether a service happens to be up. `deploy/provision` is
deliberately absent, which takes the launcher's `exec claude` path -- the fast
path, and the one whose argv we can read directly.

The resolvers themselves are the REAL ones: node_identity.py resolves
`Path(__file__).resolve()`, so a symlinked copy still reads the repo's own
node-vocabulary.yaml and agent_registry.yaml. That is the point. The invariant
under test is "what the resolver answered reached argv", so the expected values
are taken from the resolver rather than hardcoded.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh"
FLAG = "--append-system-prompt"

# 5090, not this node: an identity test that only passes on the host that wrote
# it measures the host. PMOVES_NODE_ID is an explicit override the resolver
# honours over the hostname, so this is deterministic anywhere the vocabulary is.
TEST_NODE_ID = "pmoves-5090"

# A stub that exits 0 and prints the row shape claude-pmoves.sh parses with awk
# (`/^cipher OK/ {print $3}`), so the "memory is up" contributor fires without
# contacting anything.
CIPHER_STUB_UP = """#!/usr/bin/env python3
print("cipher OK stub-endpoint (test stub)")
raise SystemExit(0)
"""

ARGV_DUMPER = """#!/usr/bin/env bash
# Write argv NUL-separated: the prompt contains newlines, so a line-based dump
# could not tell one multi-line argument from several arguments.
for a in "$@"; do printf '%s\\0' "$a"; done > "$ARGV_OUT"
"""

TWO_FLAG_CANARY = """#!/usr/bin/env bash
# The pre-fix shape, preserved as a positive control for the harness below.
exec claude {flag} "FIRST BLOCK" {flag} "SECOND BLOCK"
"""


def _bash() -> str:
    found = shutil.which("bash")
    if not found:
        pytest.skip("bash not available")
    return found


def _fake_root(tmp_path: Path, *, tools: dict[str, str | Path]) -> Path:
    """A PMOVES_LAUNCHER_ROOT carrying only what the launcher must find.

    `tools` maps a filename under pmoves/tools to either a Path (symlinked to
    the real tool) or a str (written as an executable stub). A tool left out is
    a tool the launcher will find missing -- which is itself a tested path.
    """
    root = tmp_path / "root"
    (root / "pmoves").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / "pmoves" / "scripts").symlink_to(REPO_ROOT / "pmoves" / "scripts")
    (root / "pmoves" / "config").symlink_to(REPO_ROOT / "pmoves" / "config")
    (root / ".claude" / "agents").symlink_to(REPO_ROOT / ".claude" / "agents")

    tools_dir = root / "pmoves" / "tools"
    tools_dir.mkdir()
    for name, source in tools.items():
        target = tools_dir / name
        if isinstance(source, Path):
            target.symlink_to(source)
        else:
            target.write_text(source, encoding="utf-8")
            target.chmod(0o755)
    return root


def _run(tmp_path: Path, root: Path, args: list[str], *, launcher: Path | None = None,
         env_extra: dict[str, str] | None = None) -> tuple[list[str], str, int]:
    """Run a launcher against a stub `claude`; return (argv, stderr, rc)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "claude"
    stub.write_text(ARGV_DUMPER, encoding="utf-8")
    stub.chmod(0o755)

    argv_out = tmp_path / "argv.bin"
    env = dict(os.environ)
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        PMOVES_LAUNCHER_ROOT=str(root),
        PMOVES_NODE_ID=TEST_NODE_ID,
        ARGV_OUT=str(argv_out),
    )
    # The resolver reads the process env first. Inherited values from the
    # session that runs pytest would silently override the test's node.
    env.pop("PMOVES_NODE_IDENTITY", None)
    env.update(env_extra or {})

    proc = subprocess.run(
        [_bash(), str(launcher or LAUNCHER), *args],
        capture_output=True, text=True, env=env, timeout=180,
    )
    raw = argv_out.read_bytes() if argv_out.exists() else b""
    argv = [part.decode("utf-8") for part in raw.split(b"\0")[:-1]] if raw else []
    return argv, proc.stderr, proc.returncode


def _prompts(argv: list[str]) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == FLAG and i + 1 < len(argv)]


def _resolver_says(harness: str = "claude-code") -> tuple[str, str]:
    """(node, identity) straight from the real resolver, as the launcher gets it."""
    env = dict(os.environ, PMOVES_NODE_ID=TEST_NODE_ID)
    env.pop("PMOVES_NODE_IDENTITY", None)
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "pmoves" / "tools" / "node_identity.py"),
         "--harness", harness, "--shell"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    if proc.returncode != 0:
        pytest.skip(f"node_identity.py could not run here: {proc.stderr.strip()}")
    values = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        values[key] = value.strip("'\"")
    node, identity = values.get("PMOVES_NODE", ""), values.get("PMOVES_RESOLVED_IDENTITY", "")
    if not node or not identity:
        # Not a skip. TEST_NODE_ID is declared in node-vocabulary.yaml with a
        # claude-code default_identity; if it stops resolving, the invariant
        # these tests guard has no input and the suite must say so loudly.
        pytest.fail(
            f"{TEST_NODE_ID} no longer resolves to a node+identity "
            f"(node={node!r} identity={identity!r}); update TEST_NODE_ID or the vocabulary."
        )
    return node, identity


def _resolver_cipher_agent_id(harness: str = "claude-code") -> str:
    """The cipher agentId the resolver declares, as the launcher receives it."""
    env = dict(os.environ, PMOVES_NODE_ID=TEST_NODE_ID)
    env.pop("PMOVES_NODE_IDENTITY", None)
    env.pop("PMOVES_CIPHER_AGENT_ID", None)
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "pmoves" / "tools" / "node_identity.py"),
         "--harness", harness, "--shell"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        if key == "PMOVES_CIPHER_AGENT_ID":
            value = value.strip("'\"")
            if value:
                return value
    pytest.fail(
        f"no cipher agentId declared for {harness} on {TEST_NODE_ID}; "
        "node-vocabulary.yaml declares one for every claude-code node"
    )


@pytest.fixture()
def wired_root(tmp_path: Path) -> Path:
    """Every contributor able to fire: identity, cipher-up, carry."""
    return _fake_root(tmp_path, tools={
        "node_identity.py": REPO_ROOT / "pmoves" / "tools" / "node_identity.py",
        "cipher_identity.py": REPO_ROOT / "pmoves" / "tools" / "cipher_identity.py",
        "cipher_preflight.py": CIPHER_STUB_UP,
    })


def test_the_harness_can_see_more_than_one_flag(tmp_path: Path):
    """Positive control. Without this, 'exactly one' could mean 'we cannot count'.

    A canary launcher built in the pre-fix shape -- two separate flags -- must be
    reported as two. If this ever reads 1, every assertion below is vacuous.
    """
    canary = tmp_path / "canary.sh"
    canary.write_text(TWO_FLAG_CANARY.format(flag=FLAG), encoding="utf-8")
    canary.chmod(0o755)
    root = _fake_root(tmp_path, tools={})
    argv, _, _ = _run(tmp_path, root, [], launcher=canary)
    assert argv.count(FLAG) == 2, argv
    assert _prompts(argv) == ["FIRST BLOCK", "SECOND BLOCK"]


def test_the_composed_argv_carries_exactly_one_prompt_flag(tmp_path: Path, wired_root: Path):
    """THE regression. Three contributors fire; the harness must receive ONE flag.

    Pre-fix this was 3, and `claude` kept only the last -- so the node identity
    resolved a hundred lines earlier reached nothing.
    """
    argv, stderr, rc = _run(tmp_path, wired_root, ["delivery-agent", "--print", "hi"])
    assert rc == 0, stderr
    assert argv, f"stub claude was never reached; stderr:\n{stderr}"
    assert argv.count(FLAG) == 1, f"expected one {FLAG}, got {argv.count(FLAG)}:\n{argv}"


def test_the_one_prompt_carries_node_identity_and_role(tmp_path: Path, wired_root: Path):
    """Not array membership -- the text the harness was actually handed."""
    node, identity = _resolver_says()
    argv, stderr, _ = _run(tmp_path, wired_root, ["delivery-agent", "--print", "hi"])
    prompts = _prompts(argv)
    assert len(prompts) == 1, f"{prompts!r}\n{stderr}"
    prompt = prompts[0]
    assert node in prompt, f"node {node!r} never reached argv:\n{prompt}"
    assert identity in prompt, f"identity {identity!r} never reached argv:\n{prompt}"
    assert "delivery-agent" in prompt, f"role never reached argv:\n{prompt}"

    # The cipher agentId is a FOURTH contributor, added after the fix. Pre-fix it
    # would have been a fourth flag -- and, being last, the one that cancelled
    # the other three rather than the one that got cancelled.
    cipher_id = _resolver_cipher_agent_id()
    assert cipher_id in prompt, f"cipher agentId {cipher_id!r} never reached argv:\n{prompt}"
    # The spellings differ, and announcing the registry one is what cipher
    # refuses. Assert the prompt does not tell the agent to pass it as agentId.
    assert f"agentId '{identity}'" not in prompt, (
        f"the prompt offers the REGISTRY spelling {identity!r} as an agentId; "
        f"cipher wants {cipher_id!r}"
    )


def test_every_contributor_survives_into_the_same_prompt(tmp_path: Path, wired_root: Path):
    """The cancellation was per-contributor, so assert on all three at once.

    Identity was contributor one and carry was contributor three. Pre-fix, a
    test that looked only for the carry sentence would have passed.
    """
    node, identity = _resolver_says()
    argv, stderr, _ = _run(tmp_path, wired_root, ["delivery-agent"])
    prompts = _prompts(argv)
    assert len(prompts) == 1, f"{prompts!r}\n{stderr}"
    prompt = prompts[0]
    assert identity in prompt                       # contributor 1: node identity
    assert "Persistent memory IS available" in prompt   # contributor 2: cipher status
    # "memory writes" and not "agent_id": pm_cipher_identity has TWO prompts --
    # carry-intact ("attributed to agent_id '<id>'") and CARRY GAP ("cipher will
    # attribute your memory writes to ..."), and which one fires depends on the
    # node's token. Assert on the phrase both branches share, or the test passes
    # or fails on the credential rather than on the accumulation.
    assert "memory writes" in prompt                # contributor 3: the carry verdict
    assert "agentId" in prompt                      # contributor 4: the cipher agentId
    assert node in prompt


def test_an_empty_prompt_never_becomes_a_bare_flag(tmp_path: Path):
    """`--append-system-prompt` with nothing after it is an error, not a no-op.

    This used to be tested through the launcher, by making every contributor
    fail. It cannot be any more: a session with no declared Cipher agentId is
    now TOLD so, because cipher refuses every call without one -- so the
    launcher always has at least one thing to say. The guarantee did not move,
    only the layer that can still demonstrate it. pm_ident_prompt_args is where
    an empty prompt would turn into a bare flag, so it is tested directly.
    """
    fragment = REPO_ROOT / "pmoves" / "scripts" / "pm-node-identity.sh"
    script = f"""
      set -u
      . '{fragment}'
      pm_ident_prompt_args;              echo "empty=${{#PM_IDENT_PROMPT_ARGS[@]}}"
      pm_ident_append ""
      pm_ident_prompt_args;              echo "after_empty_append=${{#PM_IDENT_PROMPT_ARGS[@]}}"
      pm_ident_append "first"
      pm_ident_append "second"
      pm_ident_prompt_args;              echo "after_two=${{#PM_IDENT_PROMPT_ARGS[@]}}"
      echo "flag=${{PM_IDENT_PROMPT_ARGS[0]}}"
      echo "text<<<${{PM_IDENT_PROMPT_ARGS[1]}}>>>"
    """
    proc = subprocess.run([_bash(), "-c", script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = dict(
        line.split("=", 1) for line in proc.stdout.splitlines() if line.startswith(("empty=", "after_"))
    )
    assert out["empty"] == "0", "nothing to say must produce NO flag, not an empty one"
    assert out["after_empty_append"] == "0", "an empty contributor must not create a flag"
    assert out["after_two"] == "2", "two contributors must still produce exactly one flag"
    assert f"flag={FLAG}" in proc.stdout, proc.stdout
    # Blank-line separated, so the model reads distinct paragraphs rather than a
    # run-on sentence -- and so a later contributor cannot glue onto an earlier.
    assert "text<<<first\n\nsecond>>>" in proc.stdout, proc.stdout


def test_both_exec_paths_pass_the_same_composed_array(tmp_path: Path, wired_root: Path):
    """claude-pmoves.sh has two exec sites -- with and without the real launcher.

    The flag is composed once, above both. If a future edit reintroduces a
    per-site build, the two will drift and one of them will be the one nobody
    runs interactively.
    """
    text = LAUNCHER.read_text(encoding="utf-8")
    assert text.count("pm_ident_prompt_args") == 1, "composition must happen once"
    # Comments are stripped first: the flag's name is discussed at length in the
    # block explaining why it may only appear once, and a substring check over
    # the whole file would read its own documentation as a violation.
    code = "\n".join(
        ln for ln in text.splitlines() if not ln.lstrip().startswith("#")
    )
    assert FLAG not in code, (
        f"{FLAG} is built inside the launcher; contributors must call "
        f"pm_ident_append and let pm_ident_prompt_args compose the one flag:\n"
        + "\n".join(ln for ln in code.splitlines() if FLAG in ln)
    )
    # lstrip: the degraded `exec claude` path sits inside an `if`, so it is
    # indented. Anchoring on column zero found only one of the two exec sites --
    # and the one it missed is precisely the fallback nobody runs interactively.
    exec_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("exec ")]
    assert len(exec_lines) == 2, exec_lines
    for line in exec_lines:
        assert 'IDENTITY_ARGS[@]' in line, line
