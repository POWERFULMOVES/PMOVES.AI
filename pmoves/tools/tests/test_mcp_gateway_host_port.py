"""Guard: host-side clients reach the MCP gateway on 8189, never 8091.

The gateway listens on 8091 INSIDE its container. Its host port moved to 8189
because 8091 is Archon's ``ARCHON_API_PORT`` legacy-alias default
(``${ARCHON_API_PORT:-8091}:3090``), and a node running both could not bind
the gateway (docker-compose.mcp-gateway.yml:129-132).

A sweep on 2026-09-28 classified all 369 tracked ``\\b8091\\b`` hits (206
files, register + *.jsonl trails excluded): 0 gateway-host, 274 Archon
alias, 10 container-internal, 62 historical, 2 ambiguous, 21 unrelated. So
this module does not fix drift; it keeps the zero at zero.

Limit, stated beside the check: test (2) catches a line that NAMES the
gateway (``mcp-gateway`` / ``MCP_GATEWAY`` / "MCP Gateway") together with a
host-reachable ``:8091``. A bare ``curl localhost:8091/mcp`` that does not
name the gateway is not caught; Archon owns host 8091, so such a line is
Archon's by default and a human classifies it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "pmoves" / "docker-compose.mcp-gateway.yml"

GW_WORD = re.compile(r"mcp[-_ ]?gateway", re.I)
HOST_8091 = re.compile(
    r"(localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal|\$\{?TS_\w+\}?):8091\b"
)
# Dated records of past state: they describe what WAS bound, and must not be
# rewritten to look as though 8189 had always been the answer.
HISTORICAL = re.compile(
    r"^\.claude/learnings/|/evidence/|/audit/|/archive/|/reviews/|/validation/"
    r"|^research/|/handoffs/|/PR_EVIDENCE/|agnotes2\.md$|^pmoves/docs/context/"
    r"|/repoingest/|^docs/superpowers/specs/"
)
EXCLUDES = [":!pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md", ":!*.jsonl"]


def _git_grep(pattern: str) -> list[tuple[str, int, str]]:
    try:
        proc = subprocess.run(
            ["git", "grep", "-nIE", pattern, "--", ".", *EXCLUDES],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        pytest.skip("git not available")
    if proc.returncode not in (0, 1):  # 1 = no match, anything else = error
        pytest.skip(f"not a git checkout: {proc.stderr.strip()}")
    rows = []
    for line in proc.stdout.splitlines():
        path, rest = line.split(":", 1)
        ln, text = rest.split(":", 1)
        rows.append((path, int(ln), text))
    return rows


def test_compose_publishes_host_8189_onto_container_8091():
    text = COMPOSE.read_text(encoding="utf-8")
    maps = re.findall(r'"\$\{MCP_GATEWAY_BIND:-[^}]+\}:\$\{MCP_GATEWAY_PORT:-(\d+)\}:(\d+)"', text)
    assert maps == [("8189", "8091")], maps
    # Container side is unchanged: the listener and the healthcheck.
    assert "--port=8091" in text
    assert "http://127.0.0.1:8091/health" in text


def test_no_current_doc_points_host_clients_at_gateway_on_8091():
    rows = _git_grep(r"\b8091\b")
    assert rows, "grep returned nothing: input is empty, cannot conclude"
    named = [r for r in rows if GW_WORD.search(r[2]) and HOST_8091.search(r[2])]
    offenders = [f"{p}:{n}: {t.strip()[:120]}" for p, n, t in named if not HISTORICAL.search(p)]
    # Print both input sizes beside the result: an empty offender list means
    # nothing only if the corpus was non-empty.
    print(f"8091 hit lines scanned={len(rows)} gateway-named host hits={len(named)} "
          f"non-historical offenders={len(offenders)}")
    assert offenders == [], "\n".join(offenders)


def test_host_side_gateway_defaults_are_8189():
    for rel, needle in [
        ("pmoves/mk/infra.mk", "MCP_GATEWAY_PORT:-8189"),
        ("pmoves/tools/mcp_gateway_verify.py", "'MCP_GATEWAY_PORT', '8189'"),
        ("pmoves/scripts/port_allocator.py", '"mcp-gateway": 8189'),
    ]:
        assert needle in (REPO / rel).read_text(encoding="utf-8"), rel


# pmoves-yt listens on 8077 (Dockerfile CMD/EXPOSE, compose
# ${PMOVES_YT_PORT:-8077}:8077, CATALOG). Four defaults pointed at 8091, which
# on a node publishing Archon's alias reaches Archon instead.
YT_WORD = re.compile(r"pmoves[-_ .]?yt|YT_BASE_URL|/yt/", re.I)


def test_no_pmoves_yt_default_points_at_8091():
    rows = _git_grep(r"\b8091\b")
    assert rows, "grep returned nothing: input is empty, cannot conclude"
    named = [r for r in rows if YT_WORD.search(r[2]) and HOST_8091.search(r[2])]
    offenders = [f"{p}:{n}: {t.strip()[:120]}" for p, n, t in named if not HISTORICAL.search(p)]
    print(f"8091 hit lines scanned={len(rows)} yt-named host hits={len(named)} "
          f"non-historical offenders={len(offenders)}")
    assert offenders == [], "\n".join(offenders)


def test_duplicate_default_ports_are_exactly_the_known_set():
    """Any NEW duplicate in DEFAULT_PORTS fails; resolving 8189 must edit this."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "port_allocator", REPO / "pmoves" / "scripts" / "port_allocator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    by_port: dict[int, set[str]] = {}
    for svc, port in mod.DEFAULT_PORTS.items():
        if port:
            by_port.setdefault(port, set()).add(svc)
    dups = {p: s for p, s in by_port.items() if len(s) > 1}
    assert dups == {
        5432: {"postgres", "supabase-db"},       # same service, two names
        6333: {"qdrant", "qdrant-dashboard"},    # same service, two names
        8189: {"mcp-gateway", "comfyui"},        # OPEN fleet decision (GB10)
    }, dups
