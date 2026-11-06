"""Which env.shared keys may cross into a launched agent session.

`claude-pmoves.{sh,ps1}` used to export EVERY env.shared key into the session
(`set -a; . "$tmpf"` in bash, a `SetEnvironmentVariable` per parsed key in
PowerShell). The session env then shadows the tier files for every child
process, and docker compose gives shell env precedence over `--env-file`
values -- so a STALE env.shared value silently beat the fresh one the funnel
wrote into env.tier-*. Measured on Z890 2026-09-09: kong ran on a demo-era JWT
from exactly this path while postgrest enforced the fresh secret.

The first fix (ef8ef5e46, never merged) derived the allowlist from the roster's
``${VAR}`` references alone. That misses servers that read the environment
WITHOUT naming the variable in the roster -- pmoves-hirag-mcp reads HIRAG_URL /
OPEN_NOTEBOOK_API_* implicitly, and the roster normalizer reads NATS_PORT to
rewrite in-stack hosts. Those live in IMPLICIT_READS below, each with its
reader, so the list stays auditable instead of growing by guesswork.

Output: one variable NAME per line, sorted. Never values -- this module does
not open env.shared at all; the launchers intersect its output with what they
parsed.

    python pmoves/tools/launcher_env_allowlist.py --root <repo> [--ref origin/main]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

# Rosters the launcher can hand to claude. `.mcp.json` is the per-node gateway
# entry `make -C pmoves mcp-toolkit-connect` writes (untracked).
ROSTER_FILES = (".claude/mcp.json", ".mcp.json")

# Variables a roster server or the launcher pipeline reads from the process env
# without the roster naming them. Every entry names its reader; an entry whose
# reader is gone should be deleted, not kept "to be safe".
IMPLICIT_READS: dict[str, str] = {
    "HIRAG_URL": "pmoves-hirag-mcp (hirag_mcp/tools.py)",
    "HIRAG_GPU_URL": "pmoves-hirag-mcp (hirag_mcp/tools.py)",
    "OPEN_NOTEBOOK_API_URL": "pmoves-hirag-mcp (hirag_mcp/tools.py)",
    "OPEN_NOTEBOOK_API_TOKEN": "pmoves-hirag-mcp (hirag_mcp/tools.py)",
    "NATS_PORT": "mcp_roster_normalize.py _IN_STACK_HOSTS (nats -> 127.0.0.1:<port>)",
    "PMOVES_NODE_ID": "claude-pmoves.ps1 identity resolution + damage-control/known_roads.py",
}

# Claude SDK/session controls. Mirrors the launchers' blocklist: these never
# cross even if a roster were to reference one.
_BLOCKED = re.compile(
    r"^(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_BASE_URL|CLAUDECODE"
    r"|CLAUDE_CODE_.+|CLAUDE_SESSION_.+)$"
)
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)")


def _strings(node: Any) -> Iterator[str]:
    """Every string value under *node*, skipping `_`-prefixed keys (notes)."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def roster_refs(data: Any) -> set[str]:
    """``${VAR}`` names an ACTIVE server references, nested defaults included.

    `_`-prefixed servers are skipped exactly as mcp_roster_normalize.py skips
    them (P2), so a disabled entry cannot pull its secret into the session.
    """
    names: set[str] = set()
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    for name, cfg in (servers or {}).items():
        if name.startswith("_"):
            continue
        for s in _strings(cfg):
            names.update(_REF.findall(s))
    return names


def _load(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return {}


def _roster_texts(root: Path, ref: str | None) -> Iterable[str]:
    for rel in ROSTER_FILES:
        p = root / rel
        if p.is_file():
            yield p.read_text(encoding="utf-8")
    if ref:
        # The launcher hands claude the origin/main roster by default, chosen
        # AFTER env.shared loads -- so a var only main's roster names must be
        # on the list too, or that server starts without it.
        r = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:.claude/mcp.json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode == 0:
            yield r.stdout


def allowlist(root: Path, ref: str | None = None) -> list[str]:
    names = set(IMPLICIT_READS)
    for text in _roster_texts(root, ref):
        names |= roster_refs(_load(text))
    return sorted(n for n in names if not _BLOCKED.match(n))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--ref", default=None, help="also read .claude/mcp.json at this git ref")
    args = ap.parse_args(argv)
    for name in allowlist(args.root, args.ref):
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
