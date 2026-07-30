"""Agent Zero MCP server map seeding.

Writes the MCP server map to `pmoves/data/agent-zero/runtime/mcp/servers.env`.
The value can be supplied directly through `A0_MCP_SERVERS`, or generated from
discrete PMOVES env keys when `A0_MCP_ENABLE_DEFAULTS=true`.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = (PROJECT_ROOT / "data/agent-zero/runtime/mcp").resolve()
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _q(value: str) -> str:
    # Preserve common URL punctuation and encode everything else safely.
    return quote(value, safe=":/@?&=,+-._~")


def _resolve_neo4j_password() -> str:
    explicit = _strip_wrapping_quotes(os.environ.get("A0_MCP_NEO4J_PASSWORD", ""))
    if explicit:
        return explicit

    plain = _strip_wrapping_quotes(os.environ.get("NEO4J_PASSWORD", ""))
    if plain:
        return plain

    auth = _strip_wrapping_quotes(os.environ.get("NEO4J_AUTH", ""))
    if "/" in auth:
        return auth.split("/", 1)[1]

    return "neo4j"


def _resolve_supabase_url() -> str:
    for key in (
        "A0_MCP_SUPABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLIC_URL",
        "API_EXTERNAL_URL",
    ):
        value = _strip_wrapping_quotes(os.environ.get(key, ""))
        if value:
            return value
    return "http://kong:8000"


def _resolve_supabase_key() -> str:
    for key in (
        "SUPABASE_SERVICE_ROLE_KEY",
        "SERVICE_ROLE_KEY",
    ):
        value = _strip_wrapping_quotes(os.environ.get(key, ""))
        if value:
            return value
    return "service-role-required"


def _build_default_entries() -> list[tuple[str, str]]:
    fs_roots = os.environ.get("A0_MCP_FILESYSTEM_ROOTS", "/data").strip() or "/data"
    # Archon 0.6.0 serves API/UI/MCP on the unified port 3090 (the :8051 Python
    # MCP bridge was removed in the TS rewrite — #2217).
    archon_endpoint = (
        os.environ.get("A0_MCP_ARCHON_ENDPOINT", "http://archon-server:3090").strip()
        or "http://archon-server:3090"
    )
    neo4j_url = os.environ.get("A0_MCP_NEO4J_URL", "bolt://neo4j:7687").strip() or "bolt://neo4j:7687"
    neo4j_user = os.environ.get("A0_MCP_NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j")).strip() or "neo4j"
    neo4j_password = _resolve_neo4j_password()
    supabase_url = _resolve_supabase_url()
    supabase_key = _resolve_supabase_key()
    gateway_endpoint = (
        os.environ.get("A0_MCP_GATEWAY_ENDPOINT", "http://gateway:8086").strip()
        or "http://gateway:8086"
    )

    return [
        ("fs", f"mcp://filesystem?roots={_q(fs_roots)}"),
        ("archon", f"mcp://http?endpoint={_q(archon_endpoint)}"),
        ("neo4j", f"mcp://neo4j?url={_q(neo4j_url)}&user={_q(neo4j_user)}&password={_q(neo4j_password)}"),
        ("supabase", f"mcp://supabase?url={_q(supabase_url)}&key={_q(supabase_key)}"),
        ("gateway", f"mcp://http?endpoint={_q(gateway_endpoint)}"),
    ]


def _format_entries(entries: list[tuple[str, str]]) -> str:
    return " ".join(f'{name}: "{uri}";' for name, uri in entries if name and uri).strip()


def _resolve_config() -> str:
    manual = os.environ.get("A0_MCP_SERVERS", "").strip()
    extra = os.environ.get("A0_MCP_SERVERS_EXTRA", "").strip()
    include_defaults = _truthy(os.environ.get("A0_MCP_ENABLE_DEFAULTS"), default=True)

    parts: list[str] = []
    if manual:
        parts.append(manual)
    elif include_defaults:
        parts.append(_format_entries(_build_default_entries()))

    if extra:
        parts.append(extra)

    return " ".join(part for part in parts if part).strip()


def main() -> None:
    config = _resolve_config()
    outfile = RUNTIME_DIR / "servers.env"
    with outfile.open("w", encoding="utf-8") as handle:
        handle.write(config + "\n")

    print(f"OK Wrote Agent Zero MCP server map to {outfile}")
    if not config:
        print("WARN MCP server map is empty. Set A0_MCP_SERVERS or enable defaults.")


if __name__ == "__main__":
    main()
