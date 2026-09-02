"""A service written against the MCP v1 SDK must exclude MCP v2 from its pin.

`mcp` 2.x renamed `FastMCP` to `MCPServer` and deleted the whole
`mcp.server.fastmcp` package. A requirement with no upper bound (`mcp>=1.2.0`)
therefore resolves a fresh image build straight onto 2.x, where a v1-style
module dies at import — before the server ever binds its port, so the container
crash-loops with no service ever reachable.

Nothing about the source changes when this happens; only the resolved wheel
does. That makes it invisible to review and to any test that runs against an
already-installed environment, which is why the guard is static: if a service
imports the v1-only `mcp.server.fastmcp` path, its requirements must say so.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SERVICES = Path(__file__).resolve().parents[1] / "services"

# The import path that exists ONLY in mcp 1.x.
V1_ONLY_IMPORT = "mcp.server.fastmcp"


def _services_importing_v1_api() -> list[Path]:
    hits = []
    for py in sorted(SERVICES.glob("*/*.py")):
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        if V1_ONLY_IMPORT in text:
            hits.append(py)
    return hits


def _mcp_requirement(req_file: Path) -> str | None:
    for raw in req_file.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[>=<\[!~]", line)[0].strip()
        if name.lower() == "mcp":
            return line
    return None


def test_the_v1_api_scan_is_not_vacuous():
    """If the glob stops matching, every assertion below silently passes."""
    assert _services_importing_v1_api(), (
        f"no service under {SERVICES} imports {V1_ONLY_IMPORT!r} — either the "
        "scan is broken or the last v1 consumer was migrated; delete this guard "
        "in the latter case rather than leaving it vacuous."
    )


@pytest.mark.parametrize(
    "module", _services_importing_v1_api(), ids=lambda p: p.parent.name
)
def test_v1_api_consumer_excludes_mcp_2x(module: Path):
    req_file = module.parent / "requirements.txt"
    assert req_file.exists(), (
        f"{module.parent.name} imports {V1_ONLY_IMPORT} but has no requirements.txt "
        "to pin the SDK with."
    )
    spec = _mcp_requirement(req_file)
    assert spec is not None, (
        f"{module.parent.name} imports {V1_ONLY_IMPORT} but does not declare `mcp` "
        f"in {req_file.name}."
    )

    packaging = pytest.importorskip("packaging.requirements")
    req = packaging.Requirement(spec)
    assert req.specifier.contains("1.29.1", prereleases=True), (
        f"{req_file.parent.name}: {spec!r} excludes the v1 SDK it is written against."
    )
    assert not req.specifier.contains("2.0.0", prereleases=True), (
        f"{req_file.parent.name}: {spec!r} still admits mcp 2.x, which removed "
        f"{V1_ONLY_IMPORT} — a fresh build resolves 2.x and the service dies at "
        "import. Add an upper bound (`mcp>=1.2.0,<2`) or migrate to the v2 "
        "`mcp.server.mcpserver.MCPServer` API."
    )
