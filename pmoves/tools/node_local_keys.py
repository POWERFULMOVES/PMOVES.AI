"""Node-local topology labels: which ones, and how to render them for THIS node.

Declarations live in ``pmoves/config/node_local_keys.yaml`` (see its header for
why they are not a manifest attribute). This module is the one reader.

``${TS_SELF}`` resolution reuses what already exists and adds no second
``tailscale status`` parser:

  1. ``node_identity.this_node()`` -> the canonical node (PMOVES_NODE_ID, else
     the hostname, validated against node-vocabulary.yaml). PMOVES_NODE is not
     used: ``chit_provenance_check`` defaults it to "5090", which would render
     the 5090's address on every other node.
  2. that node's ``reach`` (its tailnet hostname) -> ``TS_<NODE>`` via the case
     table in ``pmoves/scripts/tailscale-node-ips.sh``. The table is READ from
     that file, not copied; ``test_node_local_keys`` pins the Windows twin
     (``deploy/provision/claude-pmoves.ps1``) to the same table.
  3. the value of ``TS_<NODE>``: an already-set, non-empty environment value
     wins (the helper's own rule), else the helper is sourced via
     ``crush_configurator._resolve_ts_vars`` -- the existing Python route into
     the same helper (#2769, #2938, #3087).

Every step fails CLOSED: an unresolved step returns ``None`` with a reason, and
callers must not write the key. A rendered ``nats://:4222`` looks configured and
is broken; an untouched key is visibly whatever the node already had.
"""

from __future__ import annotations

import os
import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "pmoves" / "config" / "node_local_keys.yaml"
TS_HELPER = REPO_ROOT / "pmoves" / "scripts" / "tailscale-node-ips.sh"

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
# `      pmoves-b850-*)   _pm_ts_set TS_B850   "$ip" ;;`
_CASE_ROW = re.compile(r"^\s*([A-Za-z0-9*?._-]+)\)\s+_pm_ts_set\s+(TS_[A-Z0-9_]+)\b", re.M)
# A host token safe to splice into a URL authority. Rejects whitespace, '/',
# '@' and anything else that would change the URL's meaning.
_HOST_TOKEN = re.compile(r"^[A-Za-z0-9.:\-]+$")

Resolver = Callable[[], Tuple[Optional[str], str]]


def load_node_local(path: Path = CONFIG_PATH) -> Dict[str, Optional[str]]:
    """Return ``{label: template_or_None}``. Raises on an unreadable file.

    Raising (rather than returning ``{}``) is deliberate: an empty result would
    silently put every address label back into the funnel's write/delete path.
    """
    import yaml  # lazy: callers that only need the constants stay stdlib-only

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    keys = (doc or {}).get("keys")
    if not isinstance(keys, dict) or not keys:
        raise ValueError(f"{path}: 'keys' must be a non-empty mapping")
    out: Dict[str, Optional[str]] = {}
    for label, spec in keys.items():
        template = (spec or {}).get("template") if isinstance(spec, dict) else None
        if template is not None and not isinstance(template, str):
            raise ValueError(f"{path}: {label}.template must be a string or null")
        out[str(label)] = template
    return out


def hostname_table(helper: Path = TS_HELPER) -> List[Tuple[str, str]]:
    """``[(hostname_glob, TS_VAR), ...]`` read from tailscale-node-ips.sh."""
    rows = _CASE_ROW.findall(helper.read_text(encoding="utf-8"))
    if not rows:
        raise ValueError(f"no case rows found in {helper}")
    return rows


def ts_var_for_hostname(host: str, table: Iterable[Tuple[str, str]]) -> Optional[str]:
    """First matching row, with bash `case` glob semantics (case-sensitive)."""
    for pattern, var in table:
        if fnmatchcase(host, pattern):
            return var
    return None


def self_ts_var(
    env: Optional[Mapping[str, str]] = None, hostname: Optional[str] = None
) -> Tuple[Optional[str], str]:
    """Which ``TS_<NODE>`` names THIS node. ``(None, why)`` when unknown."""
    from pmoves.tools import node_identity

    vocab = node_identity.load_vocabulary()
    canonical, why = node_identity.this_node(
        vocab, dict(os.environ) if env is None else dict(env), hostname
    )
    if not canonical:
        return None, f"node identity unresolved: {why}"
    node = next((n for n in vocab.values() if n.canonical == canonical), None)
    reach = getattr(node, "reach", None)
    if not reach:
        return None, f"node {canonical!r} declares no tailnet hostname (reach)"
    var = ts_var_for_hostname(reach, hostname_table())
    if not var:
        return None, (
            f"node {canonical!r} reach {reach!r} matches no row in "
            f"{TS_HELPER.name}"
        )
    return var, f"{canonical} ({why}) -> {reach} -> {var}"


def _helper_resolve(names: List[str], env: Mapping[str, str]) -> Dict[str, str]:
    from pmoves.tools.crush_configurator import _resolve_ts_vars

    return _resolve_ts_vars(names, env)


def resolve_ts_self(
    env: Optional[Mapping[str, str]] = None,
    hostname: Optional[str] = None,
    resolve_vars: Callable[[List[str], Mapping[str, str]], Dict[str, str]] = _helper_resolve,
) -> Tuple[Optional[str], str]:
    """This node's tailnet address as a URL host token, or ``(None, why)``."""
    env = dict(os.environ) if env is None else dict(env)
    var, why = self_ts_var(env, hostname)
    if not var:
        return None, why
    value = (resolve_vars([var], env).get(var) or "").strip()
    if not value:
        return None, (
            f"{var} is empty: not set in the environment and "
            f"{TS_HELPER.name} resolved nothing (no tailscale CLI, logged out, "
            f"or this node's hostname is absent from `tailscale status`)"
        )
    if not _HOST_TOKEN.match(value):
        return None, f"{var} is not a bare host/address token; refusing to splice it into a URL"
    if ":" in value:  # IPv6 literal -> URL authority form
        value = f"[{value}]"
    return value, why


def render(
    template: str,
    values: Mapping[str, str],
    ts_self: Resolver,
    env: Optional[Mapping[str, str]] = None,
) -> Tuple[Optional[str], str]:
    """Substitute every ``${VAR}``; ``(None, why)`` if ANY is unresolved.

    ``TS_SELF`` comes from ``ts_self()``; other names from ``values`` (the
    decoded bundle), then ``env``. Blank counts as unresolved. The reason names
    variables only, never a value.
    """
    env = os.environ if env is None else env
    resolved: Dict[str, str] = {}
    unresolved: List[str] = []
    for name in dict.fromkeys(_PLACEHOLDER.findall(template)):
        if name == "TS_SELF":
            value, why = ts_self()
            if not value:
                unresolved.append(f"TS_SELF ({why})")
                continue
        else:
            value = (values.get(name) or "").strip() or (env.get(name) or "").strip()
            if not value:
                unresolved.append(name)
                continue
        resolved[name] = value
    if unresolved:
        return None, "unresolved: " + "; ".join(unresolved)
    return _PLACEHOLDER.sub(lambda m: resolved[m.group(1)], template), "rendered"


def cached(resolver: Resolver) -> Resolver:
    """Call ``resolver`` at most once (sourcing the helper runs tailscale)."""
    memo: List[Tuple[Optional[str], str]] = []

    def _once() -> Tuple[Optional[str], str]:
        if not memo:
            memo.append(resolver())
        return memo[0]

    return _once
