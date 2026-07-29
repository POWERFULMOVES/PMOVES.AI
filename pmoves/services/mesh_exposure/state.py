"""mesh_exposure state: registry loader + 3 reconcile planners.

The state module is the pure-functional core. It does:
1. Load the registry from disk (curated/*.yaml) — no I/O for the
   live headscale/cloudflared/DNS state; that comes from injected
   callables so tests can mock.
2. Compute desired state per app (3 outputs):
   - headscale_acl_port_rules — list of {port, src, dst} tuples to
     add to pmoves/config/headscale/acl.yaml
   - cloudflared_ingress_entries — list of {hostname, service} to
     add to kvm2's /etc/cloudflared/config.yml
   - dns_records — list of {name, type, content, ttl} to upsert via
     the Cloudflare + Hostinger DNS APIs
3. Diff against current state (also injected as callables) and
   return a ReconcilePlan (added/removed/changed/unchanged per target).
"""
from __future__ import annotations

import logging
import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("mesh_exposure.state")


DEFAULT_REGISTRY_DIR = "pmoves/configs/pinokio-apps/curated"
DEFAULT_HEADSCALE_ACL = "pmoves/config/headscale/acl.yaml"


# ---------------------------------------------------------------------------
# Registry loader
# ---------------------------------------------------------------------------

class Registry:
    """In-memory snapshot of the curated registry.

    Entries are loaded from curated/<slug>.yaml once at construction.
    Updates to disk require a re-load. The class is intentionally simple:
    the heavy lifting is the planner, not the loader."""

    def __init__(self, entries: Optional[Dict[str, Dict[str, Any]]] = None):
        self._entries: Dict[str, Dict[str, Any]] = entries or {}

    @classmethod
    def load_from_dir(cls, registry_dir: str = DEFAULT_REGISTRY_DIR) -> "Registry":
        path = Path(registry_dir)
        entries: Dict[str, Dict[str, Any]] = {}
        if not path.exists():
            return cls(entries={})
        for f in sorted(path.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text())
            except yaml.YAMLError as e:
                logger.warning("failed to parse %s: %s", f, e)
                continue
            if not isinstance(data, dict) or "slug" not in data:
                logger.warning("skipping %s: missing slug", f)
                continue
            entries[data["slug"]] = data
        return cls(entries=entries)

    @property
    def slugs(self) -> List[str]:
        return sorted(self._entries.keys())

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, slug: str) -> Optional[Dict[str, Any]]:
        return self._entries.get(slug)

    def all(self) -> List[Dict[str, Any]]:
        return [self._entries[s] for s in self.slugs]

    def filter_l4_public(self) -> List[Dict[str, Any]]:
        return [
            e for e in self.all()
            if e.get("network_exposure", {}).get("l4_public", {}).get("reachable")
        ]


# ---------------------------------------------------------------------------
# Reconcile plan
# ---------------------------------------------------------------------------

@dataclass
class ReconcilePlan:
    """The diff between desired and current state across 3 targets."""
    headscale_added: List[Dict[str, Any]] = field(default_factory=list)
    headscale_removed: List[Dict[str, Any]] = field(default_factory=list)
    headscale_unchanged_count: int = 0
    cloudflared_added: List[Dict[str, Any]] = field(default_factory=list)
    cloudflared_removed: List[Dict[str, Any]] = field(default_factory=list)
    cloudflared_unchanged_count: int = 0
    dns_added: List[Dict[str, Any]] = field(default_factory=list)
    dns_removed: List[Dict[str, Any]] = field(default_factory=list)
    dns_unchanged_count: int = 0
    apps_considered: int = 0
    apps_skipped: List[str] = field(default_factory=list)

    def is_noop(self) -> bool:
        return not (
            self.headscale_added or self.headscale_removed
            or self.cloudflared_added or self.cloudflared_removed
            or self.dns_added or self.dns_removed
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apps_considered": self.apps_considered,
            "apps_skipped": self.apps_skipped,
            "headscale": {
                "added": self.headscale_added,
                "removed": self.headscale_removed,
                "unchanged_count": self.headscale_unchanged_count,
            },
            "cloudflared": {
                "added": self.cloudflared_added,
                "removed": self.cloudflared_removed,
                "unchanged_count": self.cloudflared_unchanged_count,
            },
            "dns": {
                "added": self.dns_added,
                "removed": self.dns_removed,
                "unchanged_count": self.dns_unchanged_count,
            },
            "is_noop": self.is_noop(),
        }


# ---------------------------------------------------------------------------
# Current-state readers (injected so tests can mock)
# ---------------------------------------------------------------------------

HeadscaleReader = Callable[[], List[Dict[str, Any]]]
"""Returns the current headscale ACL rules as a list of dicts with
{port, src, dst} keys. The default reader parses
pmoves/config/headscale/acl.yaml; tests inject an in-memory list."""

CloudflaredReader = Callable[[], List[Dict[str, Any]]]
"""Returns the current cloudflared tunnel ingress entries as a list of
{hostname, service} dicts. The default reader SSHes to kvm2 + cats
/etc/cloudflared/config.yml; tests inject an in-memory list."""

DnsReader = Callable[[], List[Dict[str, Any]]]
"""Returns the current DNS records as a list of {name, type, content, ttl}
dicts. The default reader calls the Cloudflare + Hostinger APIs; tests
inject an in-memory list."""


def default_headscale_reader(path: str = DEFAULT_HEADSCALE_ACL) -> HeadscaleReader:
    """Read the live ACL from disk. Returns one dict per port-scoped rule."""
    def reader() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not Path(path).exists():
            return out
        text = Path(path).read_text()
        for doc in yaml.safe_load_all(text):
            if not isinstance(doc, dict):
                continue
            for rule in doc.get("acls", []) or []:
                ports = rule.get("ports") or []
                src = rule.get("src", [])
                dst = rule.get("dst", [])
                if not isinstance(ports, list):
                    ports = [ports]
                for p in ports:
                    out.append({
                        "port": int(p),
                        "src": src,
                        "dst": dst,
                    })
        return out
    return reader


# ---------------------------------------------------------------------------
# Planner: registry -> desired state
# ---------------------------------------------------------------------------

def desired_headscale_rules(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """What headscale ACL rules does this entry need?

    Per the slice-4 contract: l3_mesh.headscale_acl_ports (only when
    l3_mesh.reachable=true). Each port becomes one rule with
    src=group:users and dst=<tailscale_host> (the headscale ACL needs a
    concrete dst, not a tag, because pinokio apps run on a specific
    host)."""
    l3 = entry.get("network_exposure", {}).get("l3_mesh", {})
    if not l3.get("reachable"):
        return []
    ports = l3.get("headscale_acl_ports") or []
    if not ports:
        return []
    return [
        {
            "port": int(p),
            "src": ["group:users"],
            "dst": [entry.get("network_exposure", {}).get("l3_mesh", {}).get("address") or ""],
            "rule": f"allow users -> {entry['slug']} on port {p}",
        }
        for p in ports
    ]


def desired_cloudflared_entries(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """What cloudflared tunnel ingress entries does this entry need?

    Per the slice-4 contract: l4_public.reachable=true, l4_public.tunnel,
    l4_public.public_url. The service is the L3 mesh FQDN + port
    (resolved from pinokio_bridge when port=0)."""
    l4 = entry.get("network_exposure", {}).get("l4_public", {})
    if not l4.get("reachable"):
        return []
    tunnel = l4.get("tunnel")
    hostname = l4.get("dns_record")
    if not (tunnel and hostname):
        return []
    # L3 service target: the mesh FQDN + port
    l3_addr = entry.get("network_exposure", {}).get("l3_mesh", {}).get("address")
    return [{
        "tunnel": tunnel,
        "hostname": hostname,
        "service": l3_addr or "http_status:404",
    }]


def desired_dns_records(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """What DNS records does this entry need?

    Per the slice-4 contract: l4_public.reachable=true, l4_public.dns_record.
    Returns a CNAME pointing at the tunnel (the canonical pattern for
    Cloudflare-Tunnel-backed public hostnames)."""
    l4 = entry.get("network_exposure", {}).get("l4_public", {})
    if not l4.get("reachable"):
        return []
    hostname = l4.get("dns_record")
    if not hostname:
        return []
    tunnel = l4.get("tunnel") or "pmoves-edge"
    return [{
        "name": hostname,
        "type": "CNAME",
        "content": f"{tunnel}.cfargotunnel.com",
        "ttl": 1,  # auto
        "proxied": True,
    }]


# ---------------------------------------------------------------------------
# Diff: desired vs current
# ---------------------------------------------------------------------------

def _key(d: Dict[str, Any], fields: Tuple[str, ...]) -> Tuple:
    return tuple(d.get(f) for f in fields)


def _value_dict(d: Dict[str, Any], exclude: Tuple[str, ...] = ()) -> Dict[str, Any]:
    """Return a value-comparable view of `d` excluding the key fields.
    Two records with the same key but different value_dicts are a
    value-changed pair (the writer replaces)."""
    return {k: v for k, v in d.items() if k not in exclude}


def diff_headscale(
    desired: List[Dict[str, Any]], current: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    added, removed, unchanged = [], [], 0
    cur_by_key = {_key(c, ("port",)): c for c in current}
    des_by_key = {_key(d, ("port",)): d for d in desired}
    for k, d in des_by_key.items():
        if k not in cur_by_key:
            added.append(d)
        else:
            # Same key; compare the rest of the fields. A change in
            # src or dst means the rule logically changed and must
            # be replaced (removed-then-added via the writer).
            if _value_dict(d, ("port",)) == _value_dict(cur_by_key[k], ("port",)):
                unchanged += 1
            else:
                added.append(d)
                removed.append(cur_by_key[k])
    for k, c in cur_by_key.items():
        if k not in des_by_key:
            removed.append(c)
    return added, removed, unchanged


def diff_cloudflared(
    desired: List[Dict[str, Any]], current: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    added, removed, unchanged = [], [], 0
    cur_by_key = {_key(c, ("tunnel", "hostname")): c for c in current}
    des_by_key = {_key(d, ("tunnel", "hostname")): d for d in desired}
    for k, d in des_by_key.items():
        if k not in cur_by_key:
            added.append(d)
        else:
            # Same (tunnel, hostname); compare the rest of the fields.
            # A change in `service` means the tunnel target moved.
            if _value_dict(d, ("tunnel", "hostname")) == _value_dict(cur_by_key[k], ("tunnel", "hostname")):
                unchanged += 1
            else:
                added.append(d)
                removed.append(cur_by_key[k])
    for k, c in cur_by_key.items():
        if k not in des_by_key:
            removed.append(c)
    return added, removed, unchanged


def diff_dns(
    desired: List[Dict[str, Any]], current: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    added, removed, unchanged = [], [], 0
    cur_by_key = {_key(c, ("name", "type")): c for c in current}
    des_by_key = {_key(d, ("name", "type")): d for d in desired}
    for k, d in des_by_key.items():
        if k not in cur_by_key:
            added.append(d)
        else:
            # Same (name, type); compare content/ttl/proxied. The
            # previous contract incremented `unchanged` on any
            # key match, leaving stale records live when the tunnel
            # target or TTL changed. Now a value mismatch is a
            # replace (removed-then-added via the writer).
            if _value_dict(d, ("name", "type")) == _value_dict(cur_by_key[k], ("name", "type")):
                unchanged += 1
            else:
                added.append(d)
                removed.append(cur_by_key[k])
    for k, c in cur_by_key.items():
        if k not in des_by_key:
            removed.append(c)
    return added, removed, unchanged


def plan(
    registry: Registry,
    headscale_reader: HeadscaleReader,
    cloudflared_reader: CloudflaredReader,
    dns_reader: DnsReader,
) -> ReconcilePlan:
    """Compute the full ReconcilePlan.

    Iterates the registry, computes desired state per app, reads
    current state via the injected readers, and diffs."""
    out = ReconcilePlan()
    out.apps_considered = len(registry)

    all_desired_headscale: List[Dict[str, Any]] = []
    all_desired_cloudflared: List[Dict[str, Any]] = []
    all_desired_dns: List[Dict[str, Any]] = []
    for entry in registry.all():
        # Apps with port=0 are L3-reachable but cannot be added to the
        # headscale ACL until pinokio_bridge resolves the port. The
        # mesh_exposure service runs the resolve at apply time.
        all_desired_headscale.extend(desired_headscale_rules(entry))
        all_desired_cloudflared.extend(desired_cloudflared_entries(entry))
        all_desired_dns.extend(desired_dns_records(entry))

    out.headscale_added, out.headscale_removed, out.headscale_unchanged_count = diff_headscale(
        all_desired_headscale, headscale_reader()
    )
    out.cloudflared_added, out.cloudflared_removed, out.cloudflared_unchanged_count = diff_cloudflared(
        all_desired_cloudflared, cloudflared_reader()
    )
    out.dns_added, out.dns_removed, out.dns_unchanged_count = diff_dns(
        all_desired_dns, dns_reader()
    )
    return out


# ---------------------------------------------------------------------------
# Apply: write the plan
# ---------------------------------------------------------------------------

class ApplyResult:
    """The result of an apply. Each section reports what changed."""
    def __init__(self):
        self.headscale_written: List[Dict[str, Any]] = []
        self.headscale_removed: List[Dict[str, Any]] = []
        self.cloudflared_written: List[Dict[str, Any]] = []
        self.cloudflared_removed: List[Dict[str, Any]] = []
        self.dns_written: List[Dict[str, Any]] = []
        self.dns_removed: List[Dict[str, Any]] = []
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headscale_written": self.headscale_written,
            "headscale_removed": self.headscale_removed,
            "cloudflared_written": self.cloudflared_written,
            "cloudflared_removed": self.cloudflared_removed,
            "dns_written": self.dns_written,
            "dns_removed": self.dns_removed,
            "errors": self.errors,
        }


# These callables do the actual writes. Default no-ops in the service
# (the writer is the operator's runbook); tests inject mocks that
# record the writes. Each writer receives (added, removed) so a
# retraction actually removes the live record — the previous contract
# that only took `added` left stale entries live on retraction.
HeadscaleWriter = Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], None]
CloudflaredWriter = Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], None]
"""Writer for cloudflared tunnel ingress. Receives (added, removed) lists
so a retraction actually removes the tunnel entry; the previous contract
that only took `added` left stale entries live on retraction."""

DnsWriter = Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], None]
"""Writer for DNS records. Receives (added, removed) lists; same
retraction rationale as CloudflaredWriter."""


def apply(
    plan_obj: ReconcilePlan,
    headscale_writer: HeadscaleWriter,
    cloudflared_writer: CloudflaredWriter,
    dns_writer: DnsWriter,
) -> ApplyResult:
    result = ApplyResult()
    try:
        headscale_writer(plan_obj.headscale_added, plan_obj.headscale_removed)
        result.headscale_written = plan_obj.headscale_added
        result.headscale_removed = plan_obj.headscale_removed
    except Exception as e:  # noqa: BLE001
        # Sanitize: the writer may be a real production implementation
        # that connects to Headscale / Cloudflare / Hostinger APIs over
        # SSH or HTTPS — exception messages can include URLs,
        # hostnames, tokens, or stack traces. Log the full exception
        # server-side and surface a stable error code to the client
        # (CodeQL thread 3657849876 — information exposure through
        # exception).
        logger.exception("headscale writer failed: %s", e)
        result.errors.append(f"headscale: write failed ({type(e).__name__})")
    try:
        cloudflared_writer(plan_obj.cloudflared_added, plan_obj.cloudflared_removed)
        result.cloudflared_written = plan_obj.cloudflared_added
        result.cloudflared_removed = plan_obj.cloudflared_removed
    except Exception as e:  # noqa: BLE001
        logger.exception("cloudflared writer failed: %s", e)
        result.errors.append(f"cloudflared: write failed ({type(e).__name__})")
    try:
        dns_writer(plan_obj.dns_added, plan_obj.dns_removed)
        result.dns_written = plan_obj.dns_added
        result.dns_removed = plan_obj.dns_removed
    except Exception as e:  # noqa: BLE001
        logger.exception("dns writer failed: %s", e)
        result.errors.append(f"dns: write failed ({type(e).__name__})")
    return result
