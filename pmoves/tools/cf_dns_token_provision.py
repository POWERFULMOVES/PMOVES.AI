#!/usr/bin/env python3
"""Mint a pmoves.ai-scoped Cloudflare DNS-Edit token and funnel it as CLOUDFLARE_DNS_API_TOKEN.

Traefik's ACME resolver (lego) does a DNS-01 challenge for the PMOVES edge hosts
(wealth/health/auth/notebook.pmoves.ai) and needs a **static bearer token** in
``CLOUDFLARE_DNS_API_TOKEN``. It runs headless, so a Cloudflare OAuth client cannot
serve it — only an API token fits. This tool creates a **least-privilege** token
(``Zone:DNS:Edit`` + ``Zone:Zone:Read``, scoped to the single ``pmoves.ai`` zone)
via ``POST /user/tokens``, then hands the secret straight to the secrets pipeline:
``make secrets-rotate`` reads it from ``PMOVES_ROTATE_VALUE`` (env, never argv), so
the value never touches this tool's stdout, argv, or any chat surface.

Admin credential — read from ``CF_ADMIN_API_TOKEN`` (env only; never argv). It needs:
  - ``API Tokens Write``  — to create the new token
  - ``Zone Read``         — to resolve the pmoves.ai zone id
(and ``API Tokens Read`` optionally, for the duplicate-name warning).

SAFETY: the default is a **dry run** — it resolves the zone + permission groups and
prints the exact policy it WOULD create, but mints nothing. Pass ``--apply`` to
actually create the token and funnel it. Only NON-secret material is ever printed
(zone id, account id, permission-group ids/names, the new token's id) — never the
token value.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Sequence

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import force_utf8_stdio

CF_API_BASE = "https://api.cloudflare.com/client/v4"
FUNNEL_KEY = "CLOUDFLARE_DNS_API_TOKEN"
DEFAULT_ZONE = "pmoves.ai"

# Cloudflare's permission-group NAMES for the DNS-01 use case. The EDIT capability
# on DNS records is the group Cloudflare labels "DNS Write" (create/delete the
# _acme-challenge TXT record); "Zone Read" lets lego discover the zone. Names are
# cosmetic per CF docs, so we resolve them to ids at runtime via the API rather
# than hardcoding ids that can change.
DNS_EDIT_GROUP_NAME = "DNS Write"
ZONE_READ_GROUP_NAME = "Zone Read"

# A Cloudflare API error body carries no secret (it echoes request metadata, not the
# token value we send), but we still surface only a short, structured reason.
CFError = "Cloudflare API error"


class CFApiError(RuntimeError):
    """A non-2xx / unsuccessful Cloudflare API response. Message carries status +
    CF error messages (never any secret material)."""


Transport = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, dict]]


def _urllib_transport(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed https host)
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        # CF returns JSON errors with a 4xx/5xx status; parse for the reason.
        try:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            return exc.code, {}


@dataclass
class CFClient:
    """Thin Cloudflare API client. `transport` is injectable for tests."""

    admin_token: str
    transport: Transport = _urllib_transport

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json",
        }
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        status, data = self.transport(method, f"{CF_API_BASE}{path}", headers, raw)
        if status < 200 or status >= 300 or not data.get("success", False):
            errs = "; ".join(
                str(e.get("message", e)) for e in (data.get("errors") or [])
            ) or f"HTTP {status}"
            raise CFApiError(f"{CFError} on {method} {path}: {errs}")
        return data


@dataclass
class Zone:
    id: str
    account_id: str
    name: str


@dataclass
class Plan:
    zone: Zone
    dns_edit_group_id: str
    zone_read_group_id: str
    token_name: str

    def policy(self) -> List[dict]:
        """One allow policy: the two permission groups, scoped to ONLY this zone."""
        return [{
            "effect": "allow",
            "resources": {f"com.cloudflare.api.account.zone.{self.zone.id}": "*"},
            "permission_groups": [
                {"id": self.dns_edit_group_id},
                {"id": self.zone_read_group_id},
            ],
        }]


def resolve_zone(client: CFClient, zone_name: str) -> Zone:
    data = client._call("GET", f"/zones?name={urllib.parse.quote(zone_name)}")
    result = data.get("result") or []
    if not result:
        raise CFApiError(
            f"zone {zone_name!r} not found (admin token lacks Zone Read, or the "
            "zone is on a different account)"
        )
    z = result[0]
    return Zone(id=z["id"], account_id=(z.get("account") or {}).get("id", ""), name=z["name"])


def select_permission_groups(client: CFClient) -> tuple[str, str]:
    """Resolve the DNS-Edit and Zone-Read permission-group ids by name (case-insensitive)."""
    data = client._call("GET", "/user/tokens/permission_groups")
    groups = data.get("result") or []
    by_name = {(g.get("name") or "").strip().lower(): g.get("id") for g in groups}
    dns_edit = by_name.get(DNS_EDIT_GROUP_NAME.lower())
    zone_read = by_name.get(ZONE_READ_GROUP_NAME.lower())
    if not dns_edit or not zone_read:
        # List only zone-scoped group NAMES (never secret) to aid diagnosis.
        zone_names = sorted(
            (g.get("name") or "") for g in groups
            if any("zone" in s for s in (g.get("scopes") or []))
        )
        raise CFApiError(
            f"could not resolve permission groups {DNS_EDIT_GROUP_NAME!r}/"
            f"{ZONE_READ_GROUP_NAME!r}; zone-scoped groups available: {zone_names}"
        )
    return dns_edit, zone_read


def existing_token_names(client: CFClient) -> List[str] | None:
    """Names of the admin user's existing tokens, or None if not readable (the admin
    token lacks API Tokens Read — a warning we degrade past, not a hard failure)."""
    try:
        data = client._call("GET", "/user/tokens")
    except CFApiError:
        return None
    return [(t.get("name") or "") for t in (data.get("result") or [])]


def build_plan(client: CFClient, zone_name: str, token_name: str) -> Plan:
    zone = resolve_zone(client, zone_name)
    dns_edit, zone_read = select_permission_groups(client)
    return Plan(zone=zone, dns_edit_group_id=dns_edit, zone_read_group_id=zone_read, token_name=token_name)


def create_token(client: CFClient, plan: Plan) -> tuple[str, str]:
    """POST the token. Returns (token_id, secret_value). Secret is handled by the
    caller and never logged."""
    data = client._call("POST", "/user/tokens", {"name": plan.token_name, "policies": plan.policy()})
    result = data.get("result") or {}
    value = result.get("value")
    if not value:
        raise CFApiError("token created but response carried no value (cannot funnel)")
    return result.get("id", ""), value


def _make_rotate_runner(pmoves_dir: Path) -> Callable[[str], None]:
    """Default funnel runner: `make secrets-rotate KEY=... ` with the secret injected
    into the CHILD ENV as PMOVES_ROTATE_VALUE (never argv). Raises on non-zero exit."""
    def _run(secret: str) -> None:
        env = {**os.environ, "PMOVES_ROTATE_VALUE": secret}
        proc = subprocess.run(
            ["make", "-C", str(pmoves_dir), "secrets-rotate", f"KEY={FUNNEL_KEY}"],
            env=env, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            raise RuntimeError("secrets-rotate failed: " + " / ".join(tail))
    return _run


def funnel(secret: str, runner: Callable[[str], None]) -> None:
    """Hand the secret to the pipeline. The secret lives only in memory and the
    runner's child-process env — never argv, stdout, or a return value."""
    runner(secret)


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: Transport | None = None,
    rotate_runner: Callable[[str], None] | None = None,
) -> int:
    # transport / rotate_runner are injection seams for tests; production uses the
    # real urllib transport and the `make secrets-rotate` runner.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", default=DEFAULT_ZONE, help="Zone to scope the token to (default: pmoves.ai)")
    parser.add_argument("--token-name", default=None, help="Name for the new CF token (default: pmoves-traefik-dns01-<zone>)")
    parser.add_argument("--apply", action="store_true",
                        help="Actually create + funnel the token. Without this, dry-run (resolve + print plan only).")
    args = parser.parse_args(argv)
    force_utf8_stdio()

    admin = os.environ.get("CF_ADMIN_API_TOKEN", "").strip()
    if not admin:
        print("✖ CF_ADMIN_API_TOKEN is not set. Export a Cloudflare admin token with "
              "'API Tokens Write' + 'Zone Read' (env only — never on the command line), "
              "then re-run.", file=sys.stderr)
        return 2

    token_name = args.token_name or f"pmoves-traefik-dns01-{args.zone}"
    client = CFClient(admin_token=admin, transport=transport or _urllib_transport)

    try:
        plan = build_plan(client, args.zone, token_name)
    except CFApiError as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 1

    print(f"Plan — least-privilege Cloudflare token for Traefik ACME (DNS-01):")
    print(f"  zone         : {plan.zone.name}  (id {plan.zone.id})")
    print(f"  account      : {plan.zone.account_id}")
    print(f"  permissions  : {DNS_EDIT_GROUP_NAME} ({plan.dns_edit_group_id}), "
          f"{ZONE_READ_GROUP_NAME} ({plan.zone_read_group_id})")
    print(f"  token name   : {plan.token_name}")
    print(f"  funnels to   : {FUNNEL_KEY} (via make secrets-rotate)")

    dupes = existing_token_names(client)
    if dupes is None:
        print("  ⓘ (could not list existing tokens — admin token lacks API Tokens Read; skipping dup check)")
    elif plan.token_name in dupes:
        print(f"  ⚠ a token named {plan.token_name!r} already exists — --apply will mint a SECOND one. "
              "Revoke the stale one at the CF dashboard if this is a re-run.")

    if not args.apply:
        print("\n[dry-run] Nothing minted. Re-run with --apply to create the token and funnel it.")
        return 0

    try:
        token_id, secret = create_token(client, plan)
    except CFApiError as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 1

    try:
        funnel(secret, rotate_runner or _make_rotate_runner(Path(_REPO_ROOT) / "pmoves"))
    except RuntimeError as exc:
        # The token WAS created but the funnel failed — tell the operator so they can
        # retry the funnel or revoke the orphan. Never print the value.
        print(f"✖ Token created (id {token_id}) but funnel failed: {exc}\n"
              f"  The secret was NOT printed. Re-run the funnel, or revoke token {token_id} "
              "at the CF dashboard and re-run this tool.", file=sys.stderr)
        return 1
    finally:
        # Drop the reference promptly; do not keep the secret around.
        secret = ""  # noqa: F841

    print(f"\n✔ Created CF token id {token_id} ({plan.token_name}) and funnelled it to {FUNNEL_KEY}.")
    print("  STILL TO DO: (1) make -C pmoves up-edge  (recreate Traefik → issues the cert);")
    print("  (2) confirm acme.json now has a 'main' entry for the edge hosts;")
    print("  (3) if an old CLOUDFLARE_DNS_API_TOKEN existed elsewhere (GitHub/Docker), rotate it too.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
