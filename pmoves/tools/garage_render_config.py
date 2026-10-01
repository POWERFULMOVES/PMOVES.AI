#!/usr/bin/env python3
"""Render a Garage node config, and preflight the node's secret files.

Plan: pmoves/docs/architecture/JUICEFS_GARAGE_MIGRATION_PLAN.md §1.3, §6.1.

    render         pmoves/config/garage/garage.toml.tmpl -> rendered/garage.toml for
                   THIS node: tailnet address, db_engine by tier, bootstrap_peers.
    check-secrets  the three secret files Garage reads exist, are non-empty, are
                   owned by the uid the container runs as, and have no group/other
                   bits. Garage refuses to start on `mode & 0o077 != 0`
                   (src/garage/secrets.rs read_secret_file); this catches it before
                   `up`, with the file named. It stats the files and NEVER opens them.

Exit codes: 0 clean, 1 findings, 3 could not measure (e.g. no tailscale, no dir).
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parents[1] / "config" / "garage"
TEMPLATE = HERE / "garage.toml.tmpl"
DEFAULT_OUT = HERE / "rendered" / "garage.toml"

# Operator decision (2026-10-01): lmdb on tier 1 (always-on), sqlite on tier 2
# (desktops), because LMDB is not recoverable after an unclean shutdown.
DB_ENGINE_BY_TIER = {"1": "lmdb", "2": "sqlite"}

SECRET_FILES = (
    "pmoves_garage_rpc_secret",
    "pmoves_garage_admin_token",
    "pmoves_garage_metrics_token",
)

TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
PEER_RE = re.compile(r"^([0-9a-f]{64})@(\d{1,3}(?:\.\d{1,3}){3}):3901$")

EXIT_OK, EXIT_FINDINGS, EXIT_UNMEASURED = 0, 1, 3


class Unmeasured(Exception):
    """An input could not be read, so no verdict is possible."""


def tailnet_ip(explicit: str | None) -> str:
    if explicit is None:
        try:
            out = subprocess.run(
                ["tailscale", "ip", "-4"], capture_output=True, text=True, check=True
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise Unmeasured(f"could not read the tailnet address: {exc}") from exc
        explicit = out.split()[0] if out.split() else ""
    try:
        ip = ipaddress.ip_address(explicit)
    except ValueError as exc:
        raise ValueError(f"not an IP address: {explicit!r}") from exc
    if ip.version != 4 or ip not in TAILNET_V4:
        # A public or LAN address here would bind S3/admin/RPC off the tailnet.
        raise ValueError(f"{ip} is not a tailnet (100.64.0.0/10) IPv4 address")
    return str(ip)


def parse_peers(text: str, self_ip: str) -> list[str]:
    peers: list[str] = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = PEER_RE.match(line)
        if not m:
            raise ValueError(f"peers line {n}: expected <64 hex node id>@<tailnet ipv4>:3901")
        if ipaddress.ip_address(m.group(2)) not in TAILNET_V4:
            raise ValueError(f"peers line {n}: {m.group(2)} is not a tailnet address")
        if m.group(2) != self_ip and line not in peers:
            peers.append(line)
    return peers


def render(template: str, *, tier: str, ip: str, peers: list[str]) -> str:
    peer_list = "".join(f'\n    "{p}",' for p in peers) + ("\n" if peers else "")
    # substitute(), not safe_substitute(): a placeholder left unfilled is an error.
    return Template(template).substitute(
        DB_ENGINE=DB_ENGINE_BY_TIER[tier], TAILNET_IP=ip, BOOTSTRAP_PEERS=peer_list
    )


def check_secrets(directory: Path, uid: int | None) -> list[str]:
    if not directory.is_dir():
        raise Unmeasured(f"secret directory not found: {directory}")
    problems: list[str] = []
    for name in SECRET_FILES:
        path = directory / name
        try:
            st = path.stat()
        except FileNotFoundError:
            problems.append(f"{path}: missing (deliver it through the funnel, §1.6)")
            continue
        except OSError as exc:
            raise Unmeasured(f"could not stat {path}: {exc}") from exc
        mode = stat.S_IMODE(st.st_mode)
        if not stat.S_ISREG(st.st_mode):
            problems.append(f"{path}: not a regular file")
        if mode & 0o077:
            problems.append(f"{path}: mode 0{mode:o}; Garage refuses to start unless it is 0600 or 0400")
        if st.st_size == 0:
            problems.append(f"{path}: empty")
        if uid is not None and st.st_uid != uid:
            problems.append(f"{path}: owned by uid {st.st_uid}, but the container runs as uid {uid}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render this node's garage.toml")
    r.add_argument("--tier", required=True, choices=sorted(DB_ENGINE_BY_TIER))
    r.add_argument("--tailnet-ip", help="default: `tailscale ip -4`")
    r.add_argument("--peers", type=Path, help="file of `<node id>@<tailnet ip>:3901` lines")
    r.add_argument("--template", type=Path, default=TEMPLATE)
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)

    c = sub.add_parser("check-secrets", help="stat (never read) the three secret files")
    c.add_argument("--dir", type=Path, required=True)
    c.add_argument("--uid", type=int, help="uid the container runs as (GARAGE_UID)")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "render":
            ip = tailnet_ip(args.tailnet_ip)
            peers = parse_peers(args.peers.read_text(), ip) if args.peers else []
            text = render(args.template.read_text(), tier=args.tier, ip=ip, peers=peers)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            tmp = args.out.with_suffix(".tmp")
            tmp.write_text(text)
            os.chmod(tmp, 0o644)  # no secret values in the config
            tmp.replace(args.out)
            print(f"[garage-render] {args.out}: tier {args.tier} ({DB_ENGINE_BY_TIER[args.tier]}), "
                  f"{len(peers)} bootstrap peer(s)")
            return EXIT_OK
        problems = check_secrets(args.dir, args.uid)
    except Unmeasured as exc:
        print(f"[garage] COULD-NOT-MEASURE: {exc}", file=sys.stderr)
        return EXIT_UNMEASURED
    except ValueError as exc:
        print(f"[garage] {exc}", file=sys.stderr)
        return EXIT_FINDINGS
    except OSError as exc:
        print(f"[garage] COULD-NOT-MEASURE: {exc}", file=sys.stderr)
        return EXIT_UNMEASURED
    for p in problems:
        print(f"[garage-secrets] {p}", file=sys.stderr)
    if problems:
        return EXIT_FINDINGS
    print(f"[garage-secrets] {len(SECRET_FILES)} secret files present, 0600-class, correctly owned")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
