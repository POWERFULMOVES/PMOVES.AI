"""claude-pmoves must be able to launch with NO agent.

An agent definition's `tools:` is an allowlist and `disallowedTools:` removes
whole MCP servers, so ANY agent subtracts from the roster the launcher just
assembled. A session that needs the full roster -- every cipher tool included --
must be able to start without one.

Today `PMOVES_DEFAULT_AGENT=none` fails the "does this agent file exist" check
and falls through to delivery-agent, so "neither steward nor delivery" is
unreachable, and the operator gets an EXECUTION body holding Write/Edit when
they asked for no body at all.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = REPO_ROOT / "pmoves" / "scripts" / "claude-pmoves.sh"


def _run_launcher(tmp_path, env_overrides):
    """Run the launcher with a stub `claude` that records its argv, not a real one."""
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    argv_log = tmp_path / "argv.txt"
    stub = stub_dir / "claude"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$@" > "{argv_log}"\n'
        "exit 0\n"
    )
    stub.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}:{env['PATH']}"
    env.update(env_overrides)
    # Keep the launcher from doing real work beyond arg assembly.
    env.setdefault("PMOVES_LAUNCHER_DRY_RUN", "1")

    subprocess.run(
        ["bash", str(LAUNCHER), "--print", "ping"],
        env=env, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    return argv_log.read_text().splitlines() if argv_log.exists() else []


def test_none_launches_with_no_agent_flag(tmp_path):
    """Production change that would make this fail: treating an explicit 'none'
    as a missing agent file and substituting delivery-agent."""
    argv = _run_launcher(tmp_path, {"PMOVES_DEFAULT_AGENT": "none"})
    if not argv:
        pytest.skip("launcher did not reach the claude invocation in this environment")
    assert "--agent" not in argv, (
        f"expected no --agent when PMOVES_DEFAULT_AGENT=none, got: {argv}"
    )


def test_none_does_not_silently_become_delivery_agent(tmp_path):
    """The specific regression: asking for no agent must never hand back the one
    body that holds Write/Edit."""
    argv = _run_launcher(tmp_path, {"PMOVES_DEFAULT_AGENT": "none"})
    if not argv:
        pytest.skip("launcher did not reach the claude invocation in this environment")
    assert "delivery-agent" not in argv, (
        f"'none' silently became delivery-agent: {argv}"
    )


def test_a_named_agent_is_still_honoured(tmp_path):
    """Control: the fix must not break ordinary agent selection."""
    argv = _run_launcher(tmp_path, {"PMOVES_DEFAULT_AGENT": "node-steward"})
    if not argv:
        pytest.skip("launcher did not reach the claude invocation in this environment")
    assert "--agent" in argv and "node-steward" in argv, argv
