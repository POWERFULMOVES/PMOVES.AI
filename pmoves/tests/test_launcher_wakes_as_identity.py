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

THE HALF #3205 DID NOT DELIVER (section 7)
------------------------------------------
#3205 reworded the prompt but left `DEFAULT_AGENT=...:-node-steward`, so every
launch still ran `claude --agent node-steward`. `--agent` makes the main thread
take on that agent's tool restrictions (Claude Code docs, sub-agents, "Run the
whole session as a subagent"), and node-steward denies Write/Edit/NotebookEdit:
the identity woke up unable to edit, and on 2026-10-01 its teammates reported
"No such tool available: Edit". Operator direction, reaffirmed 2026-10-01: the
main session IS the node identity, full tools; node-steward is a role it
delegates to. Section 7 holds the default argv to that, and keeps the
PMOVES_DEFAULT_AGENT and positional overrides working.
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
    for key in (*_STEERING, "PMOVES_DEFAULT_AGENT"):
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


def _symlinks_supported(tmp_path: Path) -> bool:
    probe = tmp_path / ".symlink-probe"
    try:
        probe.symlink_to(tmp_path)
    except (OSError, NotImplementedError):
        return False
    probe.unlink()
    return True


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
    if not _symlinks_supported(tmp_path):
        pytest.skip("symlinks unsupported here (e.g. Windows without developer mode)")
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
            args: tuple[str, ...] = ("--print", "hi"),
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
    proc = subprocess.run([_bash(), str(launcher), *args],
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


def test_the_initial_prompt_does_not_frame_the_session_as_a_role_apart():
    """The frontmatter initialPrompt is the first instruction the session reads."""
    front = STEWARD.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    meta = yaml.safe_load(front.lstrip("-\n"))
    prompt = " ".join(meta["initialPrompt"].split())
    assert "You are the steward for THIS node" not in prompt
    assert prompt.index("You are this node's Claude identity") < prompt.index("steward")



# ---------------------------------------------------------------------------
# 5. Undeclared values through each Windows twin's OWN parser.
#
# Review concern (#3205): an undeclared name is emitted as `''` in --shell form.
# If a twin kept that literal two-character string, `$identName -and ...` (.ps1)
# or `if not defined` (.bat) would be TRUE and the session would be told
# "You are ''" -- a silent fail-open. pwsh is absent on the POSIX hosts this runs
# on, so each parser is re-implemented here from the text it actually contains,
# and the text is asserted, so a change to either parser breaks this test.
# ---------------------------------------------------------------------------

PS1_PARSE_RE = "^([A-Z_]+)='(.*)'$"


def _resolver_raw(fmt: str, **extra: str) -> list[str]:
    proc = subprocess.run(
        [sys.executable, str(TOOLS / "node_identity.py"), "--harness", "claude-code",
         "--format", fmt],
        capture_output=True, text=True, env=_clean_env("knuckles", **extra), timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.splitlines()


def _ps1_parse(lines: list[str]) -> dict[str, str]:
    # PowerShell -match is case-INSENSITIVE by default; `.` excludes newline in .NET.
    rx = re.compile(PS1_PARSE_RE, re.IGNORECASE)
    out: dict[str, str] = {}
    for line in lines:
        m = rx.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _bat_parse(lines: list[str]) -> dict[str, str]:
    # for /f "tokens=1,* delims==" then set "%%A=%%B": token 1 is the text before
    # the first '=', token 2 the remainder after it; `set "X="` UNDEFINES X, so an
    # empty remainder leaves the variable not defined.
    out: dict[str, str] = {}
    for line in lines:
        if not line or line.startswith(";"):
            continue
        key, _, rest = line.lstrip("=").partition("=")
        if rest.lstrip("="):
            out[key] = rest.lstrip("=")
    return out


def test_the_twins_parsers_are_the_ones_simulated():
    ps1 = PS1.read_text(encoding="utf-8")
    assert f'$line -match "{PS1_PARSE_RE}"' in ps1
    assert "$identOut = & $identPy[0] @identArgv" in ps1 and "'--shell')" in ps1
    bat = (REPO_ROOT / "pmoves" / "scripts" / "windows" / "claude-pmoves.bat").read_text(encoding="utf-8")
    assert '"usebackq tokens=1,* delims=="' in bat and "--format cmd" in bat
    assert 'do set "%%A=%%B"' in bat
    assert "if not defined PMOVES_IDENTITY_NAME goto ident_noname" in bat
    assert "if ($identName -and $identForm)" in ps1


def test_an_undeclared_name_takes_the_fallback_in_the_ps1_parser():
    parsed = _ps1_parse(_resolver_raw("shell", PMOVES_REGISTER_IDENTITY="NO-SUCH-IDENTITY"))
    assert parsed["PMOVES_RESOLVED_IDENTITY"] == "claude_b850"     # the parse worked
    assert parsed["PMOVES_IDENTITY_NAME"] == ""                     # not the literal ''
    assert parsed["PMOVES_REGISTER_FORM"] == ""
    assert not (parsed["PMOVES_IDENTITY_NAME"] and parsed["PMOVES_REGISTER_FORM"])
    # The WHY: outer quotes stripped by the regex, embedded '\'' restored by the
    # .ps1's Replace -- so the warning reads as prose.
    why = parsed["PMOVES_REGISTER_WHY"].replace("'\\''", "'")
    assert not why.startswith("'") and "'NO-SUCH-IDENTITY'" in why, why


def test_an_undeclared_name_takes_the_fallback_in_the_bat_parser():
    parsed = _bat_parse(_resolver_raw("cmd", PMOVES_REGISTER_IDENTITY="NO-SUCH-IDENTITY"))
    assert parsed.get("PMOVES_RESOLVED_IDENTITY") == "claude_b850"
    assert "PMOVES_IDENTITY_NAME" not in parsed      # `if not defined` -> ident_noname
    assert "PMOVES_REGISTER_FORM" not in parsed


def test_a_declared_name_takes_the_bound_branch_in_both_parsers():
    ps1 = _ps1_parse(_resolver_raw("shell"))
    bat = _bat_parse(_resolver_raw("cmd"))
    for parsed in (ps1, bat):
        assert parsed["PMOVES_IDENTITY_NAME"] == "B850-CLAUDE"
        assert parsed["PMOVES_REGISTER_FORM"] == "B850-CLAUDE (Knuckles)"
        assert parsed["PMOVES_CIPHER_AGENT_ID"] == "b850-claude"


def test_every_prompt_twin_carries_the_signing_card():
    bat = (REPO_ROOT / "pmoves" / "scripts" / "windows" / "claude-pmoves.bat").read_text(encoding="utf-8")
    assert "signing card %PMOVES_CIPHER_AGENT_ID%" in bat and "%CARD_PART%" in bat
    assert "signing card $identCard" in PS1.read_text(encoding="utf-8")
    assert "signing card ${PM_IDENT_CIPHER_ID}" in LAUNCHER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 6. node_identity's fold must agree with the collision gate's.
#
# Not imported: identity_lineage already loads node_identity by path
# (identity_lineage.py ~L692), so the reverse import would make the pair
# circular. Pinned here over every alias instead, plus the shapes the fold exists
# for (case, inner whitespace, the unicode arrow).
# ---------------------------------------------------------------------------

def test_the_register_fold_agrees_with_identity_lineage_over_every_alias():
    doc = yaml.safe_load(IDENTITY_VOCAB.read_text(encoding="utf-8"))
    samples = []
    for entry in doc["identities"]:
        for alias in (*(entry.get("aliases") or []), entry["canonical"], entry.get("register_form")):
            if alias:
                samples += [str(alias), f"  {str(alias).lower()}  ", str(alias).replace("-", " -  ")]
    samples += ["Z890->5090-CLAUDE (opus 4.7 1M)", "Z890→5090-CLAUDE (opus 4.7 1M)"]
    assert len(samples) > 100, len(samples)
    for sample in samples:
        assert node_identity._fold_identity(sample) == identity_lineage._norm(sample), sample


# ---------------------------------------------------------------------------
# 7. The main session IS the identity: no restrictive agent by default.
# ---------------------------------------------------------------------------

def _agent_of(argv: list[str]) -> str | None:
    if "--agent" not in argv:
        return None
    return argv[argv.index("--agent") + 1]


def test_the_default_launch_carries_no_agent(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "knuckles")
    assert "--agent" not in argv, f"default launch still selects a role agent: {argv!r}"
    assert argv[-2:] == ["--print", "hi"], argv          # caller's args untouched
    assert "agent=none" in stderr, stderr


def test_the_default_prompt_states_the_identity_job(tmp_path: Path):
    argv, _ = _launch(tmp_path, "knuckles")
    prompt = _one_prompt(argv)
    name = _resolve("knuckles")["PMOVES_IDENTITY_NAME"]
    assert prompt.startswith(f"You are {name},"), prompt[:200]
    assert "no role agent and your full tools" in prompt, prompt
    assert "BEFORE any edit" in prompt and "delegate" in prompt, prompt
    # Steward named as a delegate, never as the session's own role.
    assert "'node-steward' role" in prompt
    assert "doing the job of the 'node-steward' role" not in prompt
    assert "doing the job of the '' role" not in prompt


def test_the_env_override_still_gives_the_restricted_coordinator(tmp_path: Path):
    argv, _ = _launch(tmp_path, "knuckles", PMOVES_DEFAULT_AGENT="node-steward")
    assert _agent_of(argv) == "node-steward", argv
    prompt = _one_prompt(argv)
    assert "doing the job of the 'node-steward' role" in prompt, prompt
    assert "no role agent" not in prompt


def test_a_positional_agent_still_wins(tmp_path: Path):
    argv, _ = _launch(tmp_path, "knuckles", args=("delivery-agent", "--print", "hi"))
    assert _agent_of(argv) == "delivery-agent", argv
    assert argv.count("--agent") == 1, argv
    assert "doing the job of the 'delivery-agent' role" in _one_prompt(argv)


def test_an_override_naming_no_definition_launches_with_no_agent_loudly(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "knuckles", PMOVES_DEFAULT_AGENT="no-such-agent")
    assert "--agent" not in argv, argv
    assert "no-such-agent" in stderr and "no --agent" in stderr, stderr


def test_the_second_session_rule_survives_the_default_change(tmp_path: Path):
    argv, _ = _launch(tmp_path, "knuckles", PMOVES_REGISTER_IDENTITY="B850-CLAUDE-FUNNEL")
    assert "--agent" not in argv, argv
    prompt = _one_prompt(argv)
    assert prompt.startswith("You are B850-CLAUDE-FUNNEL,"), prompt[:200]
    assert "distinct BASE identity" in prompt


def test_the_windows_twins_default_to_no_agent():
    """Text-level: neither cmd.exe nor pwsh is assumed on a POSIX CI host."""
    bat = (REPO_ROOT / "pmoves" / "scripts" / "windows" / "claude-pmoves.bat").read_text(encoding="utf-8")
    assert 'set "DEFAULT_AGENT=node-steward"' not in bat
    assert 'set "DEFAULT_AGENT="' in bat
    assert 'if defined PMOVES_DEFAULT_AGENT set "DEFAULT_AGENT=%PMOVES_DEFAULT_AGENT%"' in bat
    assert 'if defined DEFAULT_AGENT set "AGENT_ARGS=--agent %DEFAULT_AGENT%"' in bat
    assert '--agent %DEFAULT_AGENT% %*' not in bat           # the flag path used to force it
    assert "no role agent and your full tools" in bat
    ps1 = PS1.read_text(encoding="utf-8")
    assert "no role agent and your full tools" in ps1
    assert "'the role this session was launched with'" not in ps1


def test_the_steward_definition_is_a_delegate_not_the_default():
    front, body = STEWARD.read_text(encoding="utf-8").split("\n---\n", 1)
    meta = yaml.safe_load(front.lstrip("-\n"))
    assert "The default agent claude-pmoves loads" not in meta["description"]
    assert "DELEGATES" in meta["description"]
    assert "it is the default job on every node" not in body
    # Its own denies are kept: as a subagent they narrow only its pool.
    for tool in ("Write", "Edit", "NotebookEdit", "mcp__docker", "mcp__supabase-db",
                 "mcp__cloudflare-api", "mcp__tailscale"):
        assert tool in meta["disallowedTools"], tool


# ---------------------------------------------------------------------------
# 8. The no-agent session keeps its claim discipline on every fallback path.
#
# Review of #3243 (5385561980). With no default agent the session holds full
# tools, and the only claim discipline it gets is the sentence in its prompt.
# Under the old node-steward default the denies held whether or not the
# identity resolved, so every path that can reach a no-agent session must say
# "claim before any edit": the unresolved identity (P2), the Windows
# registry-key fallbacks (P2), and a positional name with no definition (P3),
# which used to become `--agent <name>`.
# ---------------------------------------------------------------------------

UNKNOWN_NODE = "no-such-node-3243"
BAT = REPO_ROOT / "pmoves" / "scripts" / "windows" / "claude-pmoves.bat"
NO_AGENT_CLAIM = "This session runs with no role agent and your full tools: claim before any edit, then delegate."


def test_an_unresolved_identity_still_carries_the_claim_sentence(tmp_path: Path):
    assert _resolve(UNKNOWN_NODE)["PMOVES_RESOLVED_IDENTITY"] == ""   # the premise
    argv, stderr = _launch(tmp_path, UNKNOWN_NODE)
    assert "--agent" not in argv, argv
    prompt = _one_prompt(argv)
    assert "UNRESOLVED" in prompt, prompt
    assert "BEFORE any edit" in prompt and "AGNOTE4482PHI.t1.md" in prompt, prompt
    # Never a guessed owner string: the session is told to ask, not to pick one.
    assert "guessed name" in prompt and "ask the operator" in prompt, prompt
    assert "You are B850-CLAUDE" not in prompt and "sign the claim register as" not in prompt
    assert "unresolved" in stderr, stderr


def test_an_unresolved_identity_with_a_role_adds_no_identity_job(tmp_path: Path):
    """The role agent's own body governs; the fallback sentence is for no agent."""
    argv, _ = _launch(tmp_path, UNKNOWN_NODE, args=("delivery-agent", "--print", "hi"))
    assert _agent_of(argv) == "delivery-agent", argv
    assert "UNRESOLVED" not in _one_prompt(argv)


def test_a_positional_name_with_no_definition_launches_with_no_agent(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "knuckles", args=("no-such-agent", "--print", "hi"))
    assert "--agent" not in argv, argv
    assert "no-such-agent" not in argv, argv             # dropped, not forwarded
    assert argv[-2:] == ["--print", "hi"], argv           # the rest reach claude
    assert "no-such-agent" in stderr and "no --agent" in stderr, stderr
    assert "no role agent and your full tools" in _one_prompt(argv)


def test_a_bare_positional_prompt_is_not_passed_as_an_agent(tmp_path: Path):
    argv, stderr = _launch(tmp_path, "knuckles", args=("fix X",))
    assert "--agent" not in argv, argv
    assert "fix X" in stderr, stderr


def test_the_windows_registry_key_fallbacks_carry_the_no_agent_claim():
    """Text-level, as section 7: neither cmd.exe nor pwsh is assumed here."""
    ps1 = PS1.read_text(encoding="utf-8")
    assert f'if (-not $roleName) {{ $identText += " {NO_AGENT_CLAIM}" }}' in ps1
    bat = BAT.read_text(encoding="utf-8")
    assert f'if not defined ROLE set "NOAGENT_PART= {NO_AGENT_CLAIM}"' in bat
    assert "rather than rediscovering it.%NOAGENT_PART%" in bat
    # The parity holds in the .sh, which the bash tests above execute.
    assert NO_AGENT_CLAIM in LAUNCHER.read_text(encoding="utf-8")


def test_the_bat_drops_a_positional_name_with_no_definition():
    bat = BAT.read_text(encoding="utf-8")
    assert 'if not exist "%REPO_ROOT%\\.claude\\agents\\%first%.md" set "DROP_FIRST=1"' in bat
    assert 'if defined DROP_FIRST set "ROLE="' in bat
    assert "if defined DROP_FIRST goto dropped" in bat
    assert 'call "%LAUNCHER%" %AGENT_ARGS% %REST% %IDENT_ARGS%' in bat
    # The drop is routed BEFORE the `--agent %*` call that would forward it.
    assert bat.index("goto dropped") < bat.index('call "%LAUNCHER%" --agent %*')


def test_the_bat_override_echo_is_quoted():
    """An unquoted &, | or > in the value would be run or redirected by cmd."""
    bat = BAT.read_text(encoding="utf-8")
    assert 'echo "[claude-pmoves] PMOVES_DEFAULT_AGENT=%DEFAULT_AGENT% has no' in bat
    assert "echo [claude-pmoves] PMOVES_DEFAULT_AGENT=" not in bat


def test_the_initial_prompt_names_where_a_delegate_finds_its_identity():
    """As a subagent the steward never receives the appended prompt (review P3)."""
    front = STEWARD.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    prompt = " ".join(yaml.safe_load(front.lstrip("-\n"))["initialPrompt"].split())
    assert "named in your appended prompt, and this session you are its steward" not in prompt
    assert "in the delegation that spawned you" in prompt, prompt
