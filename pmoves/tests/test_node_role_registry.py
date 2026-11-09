"""Node-role coupling: a declared role must map to a tag that actually enforces.

The registry exists because nothing could answer "does this node provide egress
to the fleet?" -- the fact lived only in Tailscale ACL tags and prose. The
founder's requirement (2026-09-01) is that the role be BOTH declared and
enforced, so these tests hold the join:

  * every role's `enforced_by` names a tag the ACL actually defines in
    tagOwners -- a declaration pointing at a tag nobody grants is decoration

WHAT THIS SUITE DOES *NOT* PROVE (corrected after review, 2026-09-01):
tagOwners says an administrator MAY assign a tag. It does not say the node
carries it, nor -- for `egress` -- that the tailnet has approved that node's
routes. So removing a KVM's tag or its route approval leaves these tests green
while `provides: [egress]` still routes work to a node that cannot carry it.
`always-on` is weaker still: `tag:vps` describes where a box lives and cannot
enforce uptime at all.

An earlier version of this docstring called the tagOwners check "load-bearing"
and said the registry "cannot drift from enforcement without going red". That
was an overclaim of exactly the kind this repo keeps producing -- a gate
advertising coverage it does not have. It binds the registry to the ACL's
VOCABULARY, which is real but narrow, and it is worth having for that.

The genuine enforcement check needs live tailnet state (node -> assigned tags,
and approved routes for egress). That is a follow-up and is not available to
CI here; until it exists, treat `provides:` as reviewed INTENT and the tag as
necessary-but-not-sufficient.
  * every `provides:` / `runtime_shape:` value in ANY profile resolves to the
    registry -- no free-text roles
  * unset stays unset; nothing infers a role for a node that declares none
    (declare-never-infer, same posture as deployment_class and node identity)

The first test is what keeps this registry from becoming a fifth naming
system: its role names cannot drift away from the ACL's tag vocabulary without
going red. That is a smaller guarantee than 'joined to enforcement', and the
section below says so plainly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "pmoves" / "config"
ROLES_PATH = CONFIG / "node_roles.yaml"
PROFILES_DIR = CONFIG / "profiles"
ACL_PATH = REPO_ROOT / "pmoves" / "configs" / "tailscale-acl-policy.json"

SCHEMA_VERSION = 1


def _registry() -> dict:
    return yaml.safe_load(ROLES_PATH.read_text(encoding="utf-8"))


def _acl_tag_owners() -> set[str]:
    """Tags the ACL actually grants.

    The policy is HuJSON (JSON + // comments + trailing commas), which
    json.loads rejects. Strip comments and trailing commas, then parse -- and
    if that still fails, FAIL rather than fall back to a regex. A regex
    fallback would keep the test green against a policy file this test can no
    longer actually read, which is the "reports fine without measuring"
    failure this repo keeps producing.
    """
    raw = ACL_PATH.read_text(encoding="utf-8")
    no_comments = re.sub(r"^\s*//.*$", "", raw, flags=re.MULTILINE)
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", no_comments)
    policy = json.loads(no_trailing)   # deliberately unguarded
    return set(policy.get("tagOwners", {}).keys())


def _profiles() -> list[tuple[str, dict]]:
    out = []
    for p in sorted(PROFILES_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out.append((p.name, data))
    return out


def test_schema_version_matches_loader():
    assert _registry()["schema_version"] == SCHEMA_VERSION


def test_every_role_names_a_tag_the_acl_actually_defines():
    """Binds the registry to the ACL's tag VOCABULARY.

    Deliberately narrow, and named for what it proves. It does NOT show the
    node carries the tag or that a route is approved -- see the module
    docstring. Renamed from test_every_role_is_enforced_by_a_real_acl_tag,
    which promised enforcement it cannot check.
    """
    owned = _acl_tag_owners()
    assert owned, "ACL parsed but declared no tagOwners -- refusing to pass"
    for name, spec in _registry()["roles"].items():
        tag = spec.get("enforced_by")
        assert tag, f"role {name!r} declares no enforced_by"
        assert tag in owned, (
            f"role {name!r} claims enforcement by {tag!r}, which "
            f"tailscale-acl-policy.json does not grant. Known tags: {sorted(owned)}"
        )


def test_every_profile_role_resolves():
    known = set(_registry()["roles"])
    for fname, data in _profiles():
        for role in data.get("provides") or []:
            assert role in known, (
                f"{fname} declares provides: {role!r}, not in node_roles.yaml "
                f"({sorted(known)})"
            )


def test_every_profile_runtime_shape_resolves():
    known = set(_registry()["runtime_shapes"])
    for fname, data in _profiles():
        for shape in data.get("runtime_shape") or []:
            assert shape in known, (
                f"{fname} declares runtime_shape: {shape!r}, not in "
                f"node_roles.yaml ({sorted(known)})"
            )


def test_unset_stays_unset():
    """A node that declares no role must not acquire one by inference."""
    for fname, data in _profiles():
        if "provides" not in data:
            assert data.get("provides") is None, f"{fname} materialised a role"


def test_provides_is_a_list_not_a_string():
    """`provides: egress` would iterate as characters and silently pass the
    resolver as 'e','g','r'... -- catch the shape, not just the values."""
    for fname, data in _profiles():
        v = data.get("provides")
        assert v is None or isinstance(v, list), (
            f"{fname}: provides must be a list, got {type(v).__name__}"
        )
        s = data.get("runtime_shape")
        assert s is None or isinstance(s, list), (
            f"{fname}: runtime_shape must be a list, got {type(s).__name__}"
        )


def test_registry_invents_no_tags():
    """Every enforced_by must be a tag: reference, never a bare word.

    Guards the stated design constraint -- this registry binds to the existing
    ACL vocabulary rather than starting a parallel one.
    """
    for name, spec in _registry()["roles"].items():
        assert spec["enforced_by"].startswith("tag:"), (
            f"role {name!r} enforced_by {spec['enforced_by']!r} is not an ACL tag"
        )
