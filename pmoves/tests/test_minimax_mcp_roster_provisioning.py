"""The MiniMax client's MCP roster must be MATERIALIZED, not hoped for.

Slice: the three review findings raised by `chatgpt-codex-connector` on
PR #3418 (the MiniMax client parity lane). Each finding was verified
against the source before it was accepted as valid.

  P1  deploy/provision/minimax-pmoves.sh -- neither the launcher nor the
      installer ever invoked `mcp_config_generator.py`. A fresh host (or any
      host whose ~/.minimax/mcp.json still carried only the `composio`
      entry) therefore started the client with NO PMOVES MCP servers at all.
      The failure was SILENT: no error, no non-zero exit, just a client that
      could not reach the fleet.

  P2  pmoves/configs/mavis_collection/clients/minimax-code.yaml -- the
      `pmoves-nats-fleet` entry carried the repo-relative
      `--directory ./pmoves-nats-mcp`. The MiniMax launcher resolves ROOT but
      neither cd's to it nor absolutizes anything, so `uv --directory` was
      resolved against the CALLER's working directory. Launched from anywhere
      but the repo root, the NATS MCP server silently did not start.

  P2  pmoves/tools/mcp_config_generator.py -- `render_minimax` always supplied
      `configured: True` / `builtin: False`, and `_deep_merge` lets the
      overlay win on scalars. A regeneration therefore silently reset the
      values the MiniMax RUNTIME owns, and the file disagreed with the
      runtime's own state.

WHAT THESE TESTS DO. Each one names the failure it prevents, not the
function it calls. The end-to-end test runs the REAL generated launcher,
from a directory that is NOT the repo root, with a stub binary, and asserts
that the roster landed on disk with the right shape -- because every one of
the three defects was invisible to a unit test of the renderer's output
alone.

Run:
    python -m pytest pmoves/tests/test_minimax_mcp_roster_provisioning.py -v
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from pmoves.tools import mcp_config_generator as gen
from pmoves.tools import pmoves_launcher_generator as launcher_gen

REPO_ROOT = Path(__file__).resolve().parents[2]

# The seven servers the MiniMax bootstrap profile declares.
# pmoves/configs/mavis_collection/clients/minimax-code.yaml :: super_nodes.tools
PROFILE_SERVER_KEYS = (
    "pmoves-cipher-local",
    "agent-zero",
    "pmoves-nats-fleet",
    "flute-voice",
    "tailscale",
    "hostinger",
    "composio",
)


# ---------------------------------------------------------------------------
# P1 -- the launcher must generate the roster
# ---------------------------------------------------------------------------

def _emitted(relpath: str) -> str:
    """Return the body the launcher generator would emit for *relpath*."""
    plan = launcher_gen.build_plan(REPO_ROOT)
    found = plan.by_relpath(relpath)
    assert found is not None, f"{relpath} is not in the launcher generator plan"
    return found.body


def test_minimax_launcher_invokes_the_roster_generator():
    """P1: the launcher must call the generator, not just source env.shared.

    Before the fix the launcher sourced env.shared and exec'd the binary.
    Nothing in the launch path rendered ~/.minimax/mcp.json, so the client
    started with whatever the file happened to contain -- on a fresh host,
    nothing at all.
    """
    body = _emitted("deploy/provision/minimax-pmoves.sh")
    assert "mcp_config_generator.py" in body
    assert "--client minimax" in body
    # The endpoint mode is part of the contract: "fleet" would point the
    # node-local services at ${TS_Z890} instead of this host's loopback.
    assert "--endpoint local" in body


def test_minimax_launcher_generates_the_roster_after_env_shared_and_before_handoff():
    """P1: the ORDER is load-bearing, and this test is what pins it.

    * AFTER env.shared -- the roster expands ${VAR} from the env.shared
      values. Rendered earlier, it would carry literal ${VAR} text.
    * BEFORE the handoff -- the client reads ~/.minimax/mcp.json at startup.
    """
    body = _emitted("deploy/provision/minimax-pmoves.sh")
    env_idx = body.index("ENVF=")
    roster_idx = body.index("mcp_config_generator.py")
    exec_idx = body.index("exec minimax")
    assert env_idx < roster_idx < exec_idx, (
        "the roster must be generated after env.shared loads and before the "
        "binary is exec'd"
    )


def test_minimax_launcher_fails_closed_when_the_roster_cannot_be_generated():
    """P1: a generator failure must be an ERROR, not a silent degradation.

    The whole point of the block is to remove a silent failure. If the
    generator cannot run, the client would start with a stale or missing
    roster and no error at all -- so the block exits non-zero instead.
    """
    body = _emitted("deploy/provision/minimax-pmoves.sh")
    assert "exit 1" in body
    # ...and the operator still has a way out, which is explicit rather
    # than a default.
    assert "PMOVES_ALLOW_MISSING_ROSTER" in body
    # The failure has to name the cause, not just "something went wrong".
    assert "ERROR: could not generate the MCP roster" in body


def test_powershell_twin_carries_the_same_roster_contract():
    """P1: the Windows twin must not be the half that was left broken.

    The operator runs the desktop client on Windows; fixing only the .sh
    would leave the platform they actually use unfixed.
    """
    body = _emitted("deploy/provision/minimax-pmoves.ps1")
    assert "mcp_config_generator.py" in body
    assert "--client minimax" in body
    assert "--endpoint local" in body
    assert "exit 1" in body
    assert "PMOVES_ALLOW_MISSING_ROSTER" in body
    # The Windows python discovery is the .ps1 sibling of pm-python.sh --
    # not a third inline convention.
    assert "pm-python.ps1" in body
    # Ordering, same as the bash twin.
    env_idx = body.index("$envf")
    roster_idx = body.index("mcp_config_generator.py")
    launch_idx = body.index("& minimax @args")
    assert env_idx < roster_idx < launch_idx


def test_no_other_launcher_grows_a_roster_block():
    """P1 blast radius: only the MiniMax family changes.

    Every other family reads a TRACKED, repo-rooted roster that needs no
    generation. If this test ever fails for another launcher, the block is
    rewriting a roster that client already reads correctly.
    """
    plan = launcher_gen.build_plan(REPO_ROOT)
    touched = [
        f.relpath for f in plan.files
        if "mcp_config_generator.py" in f.body
    ]
    assert sorted(touched) == [
        "deploy/provision/minimax-pmoves.ps1",
        "deploy/provision/minimax-pmoves.sh",
    ]


def test_launcher_materializes_the_roster_end_to_end(tmp_path: Path):
    """P1 + P2-2 together, end to end, from OUTSIDE the repo root.

    This is the test that would have caught both defects. It runs the REAL
    emitted launcher with a stub binary, from a working directory that is
    NOT the repo, and asserts that:

      1. the roster landed on disk with all seven profile servers;
      2. the node-local services address THIS host's loopback (the
         --endpoint local contract);
      3. the NATS `--directory` is ABSOLUTE -- which is the P2 finding: a
         relative one resolves against the caller's cwd, so the server
         would not start from anywhere but the repo root.
    """
    pytest.importorskip("yaml")

    try:
        bash = shutil.which("bash")
        from pmoves.tools.bash_resolver import resolve_bash
        bash = resolve_bash()
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"no usable bash on this host: {exc}")

    # A stub `minimax` binary: the launcher `exec`s it, so it must exist.
    # A stub `python3` so the pm-python.sh ladder has a rung that carries
    # PyYAML regardless of what this host happens to have on PATH.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    real_python = sys.executable
    (bin_dir / "python3").write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{real_python}" "$@"\n',
        encoding="utf-8",
    )
    (bin_dir / "minimax").write_text(
        "#!/usr/bin/env bash\n"
        'echo "STUB_MINIMAX_REACHED args=$*"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    for stub in (bin_dir / "python3", bin_dir / "minimax"):
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    launcher = REPO_ROOT / "deploy" / "provision" / "minimax-pmoves.sh"
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    # Path.home() on Windows reads USERPROFILE; on POSIX it reads HOME.
    # The generator resolves ~/.minimax/mcp.json at IMPORT time, so these
    # must be set before the child starts.
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)

    # cwd is tmp_path on purpose: the P2 defect only shows up when the
    # client is NOT launched from the repo root.
    proc = subprocess.run(
        [bash, str(launcher), "--probe-flag"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"launcher failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    # The launcher reached the binary -- the roster block did not swallow
    # the handoff.
    assert "STUB_MINIMAX_REACHED" in proc.stdout

    roster_path = home / ".minimax" / "mcp.json"
    assert roster_path.exists(), (
        "the launcher did not materialize ~/.minimax/mcp.json\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    servers = roster["mcpServers"]

    # 1. the whole profile roster is there
    missing = [k for k in PROFILE_SERVER_KEYS if k not in servers]
    assert not missing, f"roster is missing profile servers: {missing}"

    # 2. the node-local services address THIS host
    for key in ("pmoves-cipher-local", "agent-zero", "flute-voice"):
        url = servers[key].get("url", "")
        assert "localhost" in url, (
            f"{key} does not address this host -- the launcher rendered the "
            f"wrong endpoint mode (got {url!r})"
        )

    # 3. the NATS directory is ABSOLUTE and points into the repo
    nats_args = servers["pmoves-nats-fleet"]["args"]
    directory = nats_args[nats_args.index("--directory") + 1]
    assert not directory.startswith("./"), (
        "the NATS --directory is still repo-relative; it resolves against "
        "the caller's cwd, so the server cannot start from outside the repo"
    )
    assert Path(directory).is_absolute()
    assert (Path(directory) / "pyproject.toml").exists(), (
        f"the absolutized NATS directory does not exist: {directory}"
    )


# ---------------------------------------------------------------------------
# P2 -- repo-relative stdio paths are absolutized for MiniMax only
# ---------------------------------------------------------------------------

def _nats_spec() -> gen.ServerSpec:
    return gen.ServerSpec(
        key="pmoves-nats-fleet",
        description="NATS fleet messaging bridge",
        transport="stdio",
        command="uv",
        args=["--directory", "./pmoves-nats-mcp", "run", "python", "-m", "nats_mcp.server"],
        env={"NATS_URL": "${NATS_URL}"},
    )


def test_minimax_roster_absolutizes_repo_relative_stdio_paths(tmp_path: Path):
    """P2: the MiniMax renderer resolves `./` paths against the repo root.

    MiniMax Code reads its roster from ~/.minimax/mcp.json -- OUTSIDE the
    repo -- so nothing about it is repo-rooted. A relative path in it is
    resolved against whatever directory the client happened to start in.
    """
    root = tmp_path / "repo"
    (root / "pmoves-nats-mcp").mkdir(parents=True)
    rendered = gen.render_minimax([_nats_spec()], {}, root=root)
    args = rendered["mcpServers"]["pmoves-nats-fleet"]["args"]
    directory = args[args.index("--directory") + 1]
    assert directory == str(root / "pmoves-nats-mcp")
    assert not directory.startswith("./")


def test_minimax_roster_leaves_non_relative_commands_alone(tmp_path: Path):
    """P2: only `./`-prefixed values are rewritten.

    `uv` is a PATH lookup, not a path. Rewriting it would break the server
    in a way that is much harder to read than the bug it would fix.
    """
    root = tmp_path / "repo"
    rendered = gen.render_minimax([_nats_spec()], {}, root=root)
    entry = rendered["mcpServers"]["pmoves-nats-fleet"]
    assert entry["command"] == "uv"
    assert "run" in entry["args"]


def test_minimax_roster_absolutizes_a_repo_relative_command(tmp_path: Path):
    """P2: the rule covers `command` as well as `args`.

    No inventory entry uses a `./`-prefixed command today, so this is the
    only thing that pins the command half of the rule. Without it, the
    command half could be dropped without any test noticing.
    """
    root = tmp_path / "repo"
    spec = gen.ServerSpec(
        key="local-runner",
        description="",
        transport="stdio",
        command="./scripts/run.sh",
        args=[],
    )
    rendered = gen.render_minimax([spec], {}, root=root)
    # The rule is `os.path.join(root, value[2:])` -- byte-for-byte the one in
    # mcp_roster_normalize.py :: _abs_path. That join keeps the value's own
    # separators, so on Windows the result is `C:\repo\scripts/run.sh`. The
    # assertion pins the RULE, not a prettified path.
    assert rendered["mcpServers"]["local-runner"]["command"] == os.path.join(
        str(root), "scripts/run.sh"
    )
    assert not rendered["mcpServers"]["local-runner"]["command"].startswith("./")


def test_other_clients_keep_repo_relative_paths_relative(tmp_path: Path):
    """P2 blast radius: the tracked clients must keep their relative paths.

    The tracked `.claude/mcp.json` deliberately carries `./pmoves-hirag-mcp`.
    It is a REPO-rooted roster handed to the binary with --mcp-config, so
    absolutizing it would break the contract that roster already has.
    """
    root = tmp_path / "repo"
    spec = gen.ServerSpec(
        key="pmoves-hirag-mcp",
        description="HiRAG",
        transport="stdio",
        command="python",
        args=["./pmoves-hirag-mcp/run.py"],
    )
    rendered = gen.render_claude_kimi([spec], {})
    args = rendered["mcpServers"]["pmoves-hirag-mcp"]["args"]
    assert args == ["./pmoves-hirag-mcp/run.py"]


def test_tracked_claude_roster_still_carries_a_relative_path():
    """P2 regression guard on the real tracked file.

    The repo's own `.claude/mcp.json` is version-controlled and its
    relative path is load-bearing. If a future change absolutizes it, the
    tracked roster stops matching the inventory -- and this asserts it
    before that happens.
    """
    tracked = REPO_ROOT / ".claude" / "mcp.json"
    if not tracked.exists():
        pytest.skip("tracked .claude/mcp.json is not present in this checkout")
    data = json.loads(tracked.read_text(encoding="utf-8"))
    relative = [
        name for name, cfg in (data.get("mcpServers") or {}).items()
        if isinstance(cfg, dict)
        and any(isinstance(a, str) and a.startswith("./") for a in (cfg.get("args") or []))
    ]
    assert relative, "the tracked roster no longer carries any relative path"


# ---------------------------------------------------------------------------
# P2 -- the runtime's own flags survive a regeneration
# ---------------------------------------------------------------------------

def test_merge_preserves_the_runtime_managed_flags(tmp_path: Path):
    """P2: `configured` / `builtin` belong to the runtime, not the renderer.

    The renderer always supplies `configured: True` / `builtin: False`, and
    `_deep_merge` lets the overlay win on scalars. Without the restore
    step, a regeneration marked an unfinished server as configured and
    stripped a runtime-owned builtin marker -- so the file disagreed with
    the runtime's own state.
    """
    existing = {
        "mcpServers": {
            "pmoves-cipher-local": {
                "type": "sse", "enabled": True,
                "configured": False, "builtin": False,
            },
            "agent-zero": {
                "type": "sse", "enabled": True,
                "configured": True, "builtin": True,
            },
        }
    }
    rendered = {
        "mcpServers": {
            "pmoves-cipher-local": {
                "type": "sse", "enabled": True,
                "configured": True, "builtin": False,
            },
            "agent-zero": {
                "type": "sse", "enabled": True,
                "configured": True, "builtin": False,
            },
        }
    }
    merged = gen._deep_merge(existing, rendered)
    # The merge is what clobbers them -- that is why the restore runs after.
    assert merged["mcpServers"]["pmoves-cipher-local"]["configured"] is True

    restored = gen._restore_minimax_runtime_managed(existing, merged)
    assert restored["mcpServers"]["pmoves-cipher-local"]["configured"] is False
    assert restored["mcpServers"]["agent-zero"]["builtin"] is True


def test_write_client_config_preserves_the_runtime_flags(tmp_path: Path):
    """P2: the restore must be WIRED into the write path, not merely exist.

    The unit test above proves the helper works. It does not prove anything
    CALLS it. This one goes through the real `write_client_config` -- the
    function the CLI actually runs -- and reads the file back off disk.

    A restore that is implemented but never called is the exact shape of the
    defect this finding named: the file silently disagreed with the runtime.
    """
    output = tmp_path / "mcp.json"
    output.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "agent-zero": {
                        "type": "sse", "enabled": True,
                        "configured": False, "builtin": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    gen.write_client_config(
        "minimax",
        output,
        merge=True,
        inventory=gen.load_inventory(),
        endpoint="local",
        context={},
        allow_os_environ=False,
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    entry = data["mcpServers"]["agent-zero"]
    assert entry["configured"] is False, "the runtime's `configured` was reset"
    assert entry["builtin"] is True, "the runtime's `builtin` marker was stripped"


def test_restore_does_not_mutate_its_inputs():
    """P2: the restore must not write back into the render it was given.

    A shallow copy of the per-server map still shares the server dicts, so
    an in-place assignment silently mutated the caller's render. The
    function's own docstring promises it does not.
    """
    existing = {
        "mcpServers": {
            "agent-zero": {"type": "sse", "configured": False, "builtin": True}
        }
    }
    rendered = {
        "mcpServers": {
            "agent-zero": {"type": "sse", "configured": True, "builtin": False}
        }
    }
    rendered_snapshot = json.dumps(rendered, sort_keys=True)

    gen._restore_minimax_runtime_managed(existing, rendered)

    assert json.dumps(rendered, sort_keys=True) == rendered_snapshot, (
        "_restore_minimax_runtime_managed mutated its input"
    )


def test_new_servers_keep_the_renderer_defaults(tmp_path: Path):
    """P2: a server the runtime has never seen keeps the renderer's values.

    There is no runtime state for a server the runtime has never seen, so
    inventing one would be a guess.
    """
    existing = {"mcpServers": {}}
    rendered = {
        "mcpServers": {
            "brand-new": {"type": "sse", "configured": True, "builtin": False}
        }
    }
    restored = gen._restore_minimax_runtime_managed(existing, rendered)
    entry = restored["mcpServers"]["brand-new"]
    assert entry["configured"] is True
    assert entry["builtin"] is False


def test_dropped_servers_are_not_resurrected():
    """P2: a server dropped from the roster stays dropped.

    The restore reads the ON-DISK config to recover runtime values. It must
    not use that file to add servers back -- the roster's membership is the
    generator's decision, not the runtime's.
    """
    existing = {
        "mcpServers": {
            "dropped-server": {"type": "sse", "configured": True, "builtin": False}
        }
    }
    rendered = {"mcpServers": {"kept-server": {"type": "sse", "configured": True}}}
    restored = gen._restore_minimax_runtime_managed(existing, rendered)
    assert "dropped-server" not in restored["mcpServers"]
    assert "kept-server" in restored["mcpServers"]


# ---------------------------------------------------------------------------
# Round 2 -- the seven findings the second review round raised on #3418
# ---------------------------------------------------------------------------

def test_the_powershell_sdk_strip_runs_outside_the_env_shared_branch():
    """Round-2: the PowerShell twin must strip the Mavis SDK env UNCONDITIONALLY.

    The bash twin runs the strip before the env.shared branch. Nesting it in
    the PS1's `if (Test-Path $envf)` meant the one scenario where the strip
    matters most -- env.shared missing, launcher still launching -- was
    exactly the scenario where it never ran, letting ANTHROPIC_BASE_URL /
    ANTHROPIC_AUTH_TOKEN from the operator's parent process point the
    launched binary at an Anthropic endpoint.
    """
    ps1 = _emitted("deploy/provision/minimax-pmoves.ps1")
    # Match the STATEMENT, not the prose that mentions it: the explanatory
    # comment quotes `if (Test-Path $envf)` in backticks, and a naive
    # substring search finds that comment first.
    strip_idx = ps1.index("Strip-MavisSdkEnvFor -CliName")
    branch_match = re.search(r"^if \(Test-Path \$envf\)", ps1, re.M)
    assert branch_match, "the env.shared branch is missing from the PS1 launcher"
    assert strip_idx < branch_match.start(), (
        "the Mavis SDK env strip must run BEFORE the env.shared branch, so "
        "a missing env.shared cannot disable it"
    )

    # The bash twin is the reference: its strip is also before the branch.
    sh = _emitted("deploy/provision/minimax-pmoves.sh")
    assert sh.index("mavis_sdk_strip_env_for") < sh.index('if [ -f "$ENVF" ]')


def test_every_launcher_names_an_installer_that_actually_exists():
    """Round-2: the usage line must name a file that exists.

    The template composed `install-{name}-pmoves-command` from a name that
    ALREADY ended in `-pmoves`, so every emitted launcher told the operator
    to run `install-kilo-pmoves-pmoves-command.sh` -- a file that has never
    existed. Copy the documented command, get "No such file or directory",
    blame the repo.
    """
    plan = launcher_gen.build_plan(REPO_ROOT)
    checked = 0
    for generated in plan.files:
        if not generated.relpath.startswith("deploy/provision/"):
            continue
        for match in re.finditer(r"install-[A-Za-z0-9._-]+\.(?:sh|ps1)", generated.body):
            named = match.group(0)
            assert not named.startswith("install-") or "pmoves-pmoves-command" not in named, (
                f"{generated.relpath} names the doubled installer '{named}'"
            )
            assert (REPO_ROOT / "deploy" / "provision" / named).exists(), (
                f"{generated.relpath} names installer '{named}', which does not exist"
            )
            checked += 1
    assert checked, "no installer references were found to check -- the matcher went blind"


def test_every_registered_wrapper_script_exists():
    """Round-2: the registry must not name a file that was never created.

    `minimax-pmoves` pointed at pmoves/scripts/minimax-pmoves.sh and
    pmoves/scripts/windows/minimax-pmoves.bat -- neither exists. Every
    sibling entry resolved to a real file.
    """
    yaml = pytest.importorskip("yaml")
    registry = yaml.safe_load(
        (REPO_ROOT / "pmoves" / "configs" / "cli_tools.yaml").read_text(encoding="utf-8")
    )
    wrappers = registry.get("pmoves_wrappers") or {}
    assert wrappers, "the wrapper registry is empty -- the matcher went blind"
    for name, entry in wrappers.items():
        for field in ("script", "windows_shim"):
            declared = entry.get(field)
            assert declared, f"{name} declares no {field}"
            assert (REPO_ROOT / declared).exists(), (
                f"{name}.{field} names '{declared}', which does not exist"
            )


def test_minimax_renderer_refuses_an_unsupported_transport():
    """Round-2: an unrenderable transport must FAIL, not vanish.

    The old `else: continue` quietly DELETED the server from the render --
    the profile filter had already waved it through by key -- so the
    generated roster silently stopped being the declared roster.
    """
    spec = gen.ServerSpec(
        key="weird-transport",
        description="",
        transport="websocket",
        url="ws://localhost:9999/ws",
    )
    with pytest.raises(gen.MCPConfigError) as excinfo:
        gen.render_minimax([spec], {})
    assert "weird-transport" in str(excinfo.value)
    assert "websocket" in str(excinfo.value)


def test_an_explicit_client_profile_is_honoured_for_any_client(tmp_path: Path):
    """Round-2: `--client-profile` must always mean something.

    The old shape short-circuited on `client not in CLIENT_PROFILES` and
    returned None, so `--client claude --client-profile some.yaml` never
    read the file: the flag silently no-op'd and the operator got a
    full-inventory render with a clean exit 0.
    """
    yaml = pytest.importorskip("yaml")
    profile = tmp_path / "custom-profile.yaml"
    profile.write_text(
        yaml.safe_dump({"super_nodes": {"tools": [{"key": "only-this-one"}]}}),
        encoding="utf-8",
    )
    keys = gen._profile_tool_keys("claude", profile_path=profile)
    assert keys == ["only-this-one"], (
        "an explicitly supplied client profile was ignored for a client "
        "that has no registered profile of its own"
    )


def test_the_rendered_roster_is_created_owner_only(tmp_path: Path, monkeypatch):
    """Round-2: the secret-grade mode must be a BIRTHRIGHT, not an afterthought.

    `write_text()` opens with the default umask and only got 0o600
    afterwards, so every freshly rendered roster spent a brief window
    world-readable while carrying expanded tokens.

    WHY THE UMASK IS SET EXPLICITLY. The verdict here must be about the
    CODE, not about the host. `write_text()` creates the file with
    `0o666 & ~umask`, so on a host whose umask is 0o077 the defective path
    would produce 0o600 -- the same mode the fixed path produces -- and
    this test would PASS against the defect it exists to catch. That is
    not hypothetical: the mutation-kill case M9 (which reintroduces
    `write_text()`) SURVIVED on the CI merge gate, whose container umask
    is 0o077, while it died on a developer machine with the usual 0o022.
    A ratchet whose kill depends on the host's umask is not load-bearing.

    So the umask is pinned to a permissive, well-known 0o022 for the
    duration of the write, and restored immediately afterwards (it is
    process-global). The fixed path passes because it asks for 0o600
    EXPLICITLY; the defective path then produces 0o644 and the assertion
    fails, in every environment.

    WHY THE BIRTH MODE IS ASSERTED, NOT ONLY THE FINAL MODE. The generator
    ALSO runs `os.chmod(output_path, 0o600)` after the write, so the FINAL
    mode is 0o600 on BOTH the fixed and the defective path -- an assertion
    on the final mode alone is structurally blind to the world-readable
    WINDOW between creation and that chmod. It is exactly why M9 was
    UNKILLABLE: the suite agreed with the defect.

    So the mode the file was BORN with is observed directly, through a
    wrapper around `os.chmod`: the wrapper records the mode the file has
    at the moment the generator asks to tighten it -- which is the last
    instant of the window -- and then delegates to the real `os.chmod`.
    The recorded mode must be 0o600, and a birth mode must have been
    observed at all: a generator that never chmods would leave the
    assertion vacuous, and "no observation" is a FAILURE, not a pass.
    """
    output = tmp_path / "mcp.json"
    if os.name == "nt":
        # Windows has no POSIX mode bits -- S_IMODE reports 0o666 for every
        # file -- so the mode cannot be asserted here. The creation path is
        # still exercised: the file exists and parses.
        gen.write_client_config(
            "minimax",
            output,
            merge=False,
            inventory=gen.load_inventory(),
            endpoint="local",
            context={},
            allow_os_environ=False,
        )
        assert output.exists()
        json.loads(output.read_text(encoding="utf-8"))
        return

    import stat

    # The mode the roster has RIGHT BEFORE the generator tightens it.
    observed: list[tuple[str, int]] = []
    real_chmod = os.chmod

    def recording_chmod(path, mode, *args, **kwargs):
        """Record the mode the file has NOW, then tighten it for real."""
        try:
            current = stat.S_IMODE(os.stat(path).st_mode)
        except OSError:
            current = -1  # the file was not there to be tightened
        observed.append((os.fspath(path), current))
        return real_chmod(path, mode, *args, **kwargs)

    previous_umask = os.umask(0o022)
    monkeypatch.setattr(os, "chmod", recording_chmod)
    try:
        gen.write_client_config(
            "minimax",
            output,
            merge=False,
            inventory=gen.load_inventory(),
            endpoint="local",
            context={},
            allow_os_environ=False,
        )
    finally:
        os.umask(previous_umask)
        monkeypatch.undo()

    assert output.exists()

    target = os.path.normcase(str(output))
    births = [mode for path, mode in observed if os.path.normcase(path) == target]
    assert births, (
        "the generator never chmod'ed the roster, so the mode it was BORN "
        "with was never observed -- the assertion below would be vacuous"
    )
    assert births[0] == 0o600, (
        "the roster was born "
        f"{oct(births[0])} instead of owner-only (0o600): it was "
        "world-readable for the window between creation and the chmod that "
        "follows it"
    )

    # And it is still owner-only once the generator is done with it.
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_the_composio_note_names_every_client_it_lists():
    """Round-2: the fail-closed checklist's memory must not describe a fleet
    that no longer exists.

    The composio entry's `_note` said "clients = claude + crush" while the
    entry itself listed minimax too -- the note was left remembering the
    fleet as it was BEFORE the hunk that changed it.
    """
    inventory = json.loads(
        (REPO_ROOT / "pmoves" / "config" / "mcp_inventory.json").read_text(encoding="utf-8")
    )
    checked = 0
    for group in (inventory.get("groups") or {}).values():
        for server in group.get("servers") or []:
            note = server.get("_note")
            clients = server.get("clients")
            if not note or not clients:
                continue
            # Only a note that ENUMERATES its clients is held to naming
            # them all. A note that describes the mechanism generically
            # ("spawned per client with E2B_API_KEY") is not claiming a
            # roster, so it is not a stale roster -- asserting on it would
            # be a rule the inventory never agreed to.
            if "clients =" not in note:
                continue
            for client in clients:
                assert client in note, (
                    f"server '{server['key']}' lists client '{client}' but its "
                    f"_note enumerates a different client set -- the note is stale"
                )
            checked += 1
    assert checked, "no server carried both a client-enumerating _note and a clients list"
