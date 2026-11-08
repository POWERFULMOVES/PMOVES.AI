"""An agent session's per-agent Cipher bearer must never reach compose as CIPHER_API_TOKEN.

The launcher exports CIPHER_API_TOKEN as the session's OWN per-agent bearer
(cipher_<uuid>). Compose interpolation takes the shell over --env-file, so on
Knuckles (2026-09-26) an `up-cipher-nobuild` run from an agent session baked
that bearer into cipher-api as its deployment-wide bootstrap token: the
env-file bootstrap token then got 401. The same interpolation feeds Agent
Zero's cipher MCP header (docker-compose.yml A0_SET_mcp_servers), so an
`up-agents-stack` from a session would make A0 act as that agent.

Reproduction, read-only (`docker compose config`, fingerprints only) in the
shared checkout with a throwaway cipher_ value exported:
    pre-fix : cipher-api CIPHER_API_TOKEN = the exported value;
              agent-zero config contains it (1 hit)
    post-fix: cipher-api CIPHER_API_TOKEN = the env.shared value;
              agent-zero config contains it (0 hits)

The guard lives on $(DC), so every compose call is covered. Tested here with
`make -n` because rendering needs the node's gitignored env files; the dry run
shows exactly the command that would run.

`make -n` is not inert: every recipe line containing $(MAKE) still EXECUTES.
All four targets carry `@$(MAKE) --no-print-directory qdrant-provision-cipher`,
which runs a nested make (itself -n; its recipe has two `docker run` lines and
no $(MAKE), so it only prints). The test therefore runs under the
`stub_docker_path` fixture: the real make renders the recipes, but any
docker/docker-compose/supabase a line does reach resolves to a recorder, and
the test asserts the recorder saw NOTHING. The session guard refuses this make
spawn without that stub PATH.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
PER_AGENT = "cipher_0123456789abcdef0123456789abcdef"

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

# Every target that brings cipher-api up (and up-agents-stack also Agent Zero).
CIPHER_TARGETS = [
    ("up-cipher", "up -d --build cipher-api"),
    ("up-cipher-nobuild", "--force-recreate cipher-api"),
    ("up-cipher-full", "up -d --build cipher-api"),
    ("up-agents-stack", "agent-zero"),
]
# up-core-capable also recreates cipher-api through the same $(DC), but it is
# NOT dry-runnable: it recurses into up-core-hardened -> supa-start, whose
# nested compose call executes even under -n. Not run here on purpose.


def _compose_line(stub_env: dict, target: str, marker: str, token: str | None) -> str:
    env = dict(stub_env)
    env.pop("CIPHER_API_TOKEN", None)
    if token is not None:
        env["CIPHER_API_TOKEN"] = token
    proc = subprocess.run(
        # -o: the pin-check prerequisite runs even under -n and needs a populated
        # submodule; it is not what this test measures.
        ["make", "-s", "-n", "-o", "cipher-build-pin-check", "-C", str(PMOVES), target],
        capture_output=True, text=True, env=env, timeout=120,
    )
    lines = [
        ln.strip() for ln in proc.stdout.splitlines()
        if "docker compose" in ln and marker in ln and not ln.strip().startswith("#")
    ]
    assert lines, f"no compose line for {target} (rc={proc.returncode}): {proc.stderr[-400:]}"
    assert stub_env.calls() == [], f"a dry run reached docker/compose/supabase: {stub_env.calls()}"
    return lines[0]


@pytest.mark.parametrize("target,marker", CIPHER_TARGETS)
def test_an_exported_per_agent_bearer_is_dropped_for_compose(stub_docker_path, target, marker):
    line = _compose_line(stub_docker_path, target, marker, PER_AGENT)
    assert line.startswith("env -u CIPHER_API_TOKEN docker compose"), line
    assert PER_AGENT not in line


@pytest.mark.parametrize("target,marker", CIPHER_TARGETS)
def test_an_operator_bootstrap_override_is_left_alone(stub_docker_path, target, marker):
    """A non-cipher_ export is a deliberate override; the guard must not eat it."""
    line = _compose_line(stub_docker_path, target, marker, "operator-bootstrap-override")
    assert line.startswith("docker compose"), line


def test_nothing_exported_is_unchanged(stub_docker_path):
    line = _compose_line(stub_docker_path, "up-cipher-nobuild", "--force-recreate cipher-api", None)
    assert line.startswith("docker compose"), line
