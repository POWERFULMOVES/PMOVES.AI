#!/usr/bin/env python3
"""Green-but-disconnected detector.

The defect class: a thing that is BUILT, RUNNING, and REPORTING HEALTHY while
being functionally disconnected from everything that was supposed to consume it.
Five instances were measured on PMOVES-B850-AI-TOP on 2026-09-08 and are the
ground-truth fixtures for the test suite:

  1. cipher-api          -- container `healthy`, /health 200, bound 127.0.0.1:8105.
                            Unreachable from any peer.                        [D1]
  2. promtail            -- `Up 5 days`, emitting the same docker-socket error
                            every 5s, shipping nothing.                       [D2]
  3. archon              -- `Up (healthy)`, failing_streak 0, never ready. The
                            healthcheck curls a route that answers 200 with
                            `{"ready": false}` in the BODY.               [D2/D4]
  4. hardware_requirements.cpu_arch
                         -- declared in room manifests, schema-validated, read
                            by ZERO code. A constraint that cannot bind.      [D3]
  5. Z890 cipher roster  -- TS_Z890 correct, host reachable, :8105 CLOSED.
                            Config right, service absent.                     [D4]

Every detector answers "does it FUNCTION", never "does it EXIST".

EXIT CODES ARE DOCTRINE
    0  clean             -- every subject measured, nothing fired
    1  findings          -- at least one detector fired
    3  could-not-measure -- something could not be observed from this node

`could-not-measure` is NOT a pass and must never collapse to 0. Note that
`make` collapses every nonzero exit to 2, so this tool also emits a structured
JSON verdict (stdout by default, or --json PATH) whose `exit_code` field
survives the make invocation. See `make -C pmoves disconnection-audit`.

HARNESS TRAP, MEASURED ON THIS NODE 2026-09-08 -- DO NOT "SIMPLIFY" D2:
    `docker logs --since <dur>` and `--since <RFC3339>` BOTH return zero lines
    on this host for a container that is actively logging (docker 29.8.0,
    json-file driver). `--since 10m`, `--since 24h`, `--since 1440m` and an
    explicit `--since <ten minutes ago>` all returned 0 while `--tail 8`
    returned live lines timestamped seconds earlier. A D2 built on `--since`
    would report EVERY container clean -- it would be instance #6 of the very
    defect it hunts. So D2 uses `--tail N --timestamps` and windows in Python,
    and always reports BOTH `lines_examined` and `lines_in_window` so an empty
    result can never be mistaken for a quiet service.

PRIVACY: this tool prints hostnames, env-var NAMES and ports. It never prints
resolved addresses, and never prints secret values.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------

FIRE = "FIRE"                 # the defect is present
CLEAN = "CLEAN"               # measured, and it functions
CNM = "COULD_NOT_MEASURE"     # not observable from this node -- NOT a pass

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_COULD_NOT_MEASURE = 3

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
WILDCARD_HOSTS = {"0.0.0.0", "::", ""}


@dataclass
class Finding:
    detector: str
    subject: str
    verdict: str
    reason: str
    evidence: dict = dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "detector": self.detector,
            "subject": self.subject,
            "verdict": self.verdict,
            "reason": self.reason,
            "evidence": self.evidence,
        }


def aggregate_exit_code(findings: Sequence[Finding]) -> int:
    """FIRE wins over COULD_NOT_MEASURE wins over clean.

    COULD_NOT_MEASURE must never collapse to 0: an unobserved subject is an
    unknown, and reporting an unknown as clean is the defect this tool hunts.
    """
    if any(f.verdict == FIRE for f in findings):
        return EXIT_FINDINGS
    if any(f.verdict == CNM for f in findings):
        return EXIT_COULD_NOT_MEASURE
    return EXIT_CLEAN


# --------------------------------------------------------------------------
# Runtime probes (injectable so tests can supply fixtures)
# --------------------------------------------------------------------------


@dataclass
class PortBinding:
    host_ip: str
    host_port: int
    container_port: int

    @property
    def is_loopback(self) -> bool:
        return self.host_ip in LOOPBACK_HOSTS

    @property
    def is_wildcard(self) -> bool:
        return self.host_ip in WILDCARD_HOSTS


@dataclass
class Container:
    name: str
    status: str            # docker's human status line, e.g. "Up 5 days (healthy)"
    health: str | None     # "healthy" | "unhealthy" | "starting" | None
    bindings: list[PortBinding] = dc_field(default_factory=list)

    @property
    def looks_green(self) -> bool:
        """Reporting fine: explicitly healthy, or Up with no healthcheck."""
        if self.health is not None:
            return self.health == "healthy"
        return self.status.startswith("Up")


class DockerUnavailable(RuntimeError):
    """Raised when the docker daemon cannot be reached -> could-not-measure."""


class DockerProbe:
    """Read-only view of the live docker runtime. Never mutates a container."""

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def _run(self, args: list[str]) -> str:
        try:
            proc = subprocess.run(
                ["docker", *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise DockerUnavailable("docker CLI not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerUnavailable(f"docker {args[0]} timed out") from exc
        if proc.returncode != 0:
            raise DockerUnavailable(
                f"docker {args[0]} exited {proc.returncode}: "
                f"{proc.stderr.strip()[:200]}"
            )
        return proc.stdout

    def containers(self) -> list[Container]:
        raw = self._run(["ps", "--format", "{{.Names}}\x1f{{.Status}}\x1f{{.Ports}}"])
        out: list[Container] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            parts = line.split("\x1f")
            if len(parts) < 3:
                continue
            name, status, ports = parts[0], parts[1], parts[2]
            out.append(
                Container(
                    name=name,
                    status=status,
                    health=health_from_status(status),
                    bindings=parse_port_bindings(ports),
                )
            )
        return out

    def logs(self, name: str, tail: int) -> list[tuple[datetime | None, str]]:
        """Return (timestamp, text) pairs, newest last.

        Deliberately uses --tail, NOT --since. See the module docstring: on this
        host --since silently returns zero lines for actively-logging
        containers, which would turn D2 into a check that cannot fail.
        """
        raw = self._run(["logs", "--tail", str(tail), "--timestamps", name])
        return parse_timestamped_logs(raw)


def health_from_status(status: str) -> str | None:
    m = re.search(r"\((healthy|unhealthy|health: starting|starting)\)", status)
    if not m:
        return None
    value = m.group(1)
    return "starting" if "starting" in value else value


_PORT_MAP_RE = re.compile(
    r"(?:(?P<host>\[[0-9a-fA-F:]+\]|[0-9.]+|::):(?P<hport>\d+)->)?"
    r"(?P<cport>\d+)/(?:tcp|udp)$"
)

_PORT_RANGE_RE = re.compile(
    r"(?P<host>\[[0-9a-fA-F:]+\]|[0-9.]+|::):"
    r"(?P<hlo>\d+)-(?P<hhi>\d+)->(?P<clo>\d+)-(?P<chi>\d+)/(?:tcp|udp)$"
)


def parse_port_bindings(ports: str) -> list[PortBinding]:
    """Parse the `docker ps --format {{.Ports}}` column.

    Handles the shapes this fleet actually emits:
        "8090/tcp"                            -> exposed, NOT published (skipped)
        "0.0.0.0:8088->8080/tcp"              -> published on a wildcard
        "127.0.0.1:8000-8001->8000-8001/tcp"  -> published range on loopback
    """
    out: list[PortBinding] = []
    for chunk in (c.strip() for c in ports.split(",")):
        if not chunk:
            continue
        rng = _PORT_RANGE_RE.match(chunk)
        if rng:
            host = rng.group("host").strip("[]")
            hlo, hhi = int(rng.group("hlo")), int(rng.group("hhi"))
            clo = int(rng.group("clo"))
            for i, hp in enumerate(range(hlo, hhi + 1)):
                out.append(PortBinding(host, hp, clo + i))
            continue
        m = _PORT_MAP_RE.match(chunk)
        if not m:
            continue
        if m.group("host") is None:
            continue  # exposed but not published -- no host binding at all
        host = m.group("host").strip("[]")
        out.append(PortBinding(host, int(m.group("hport")), int(m.group("cport"))))
    return out


_TS_LINE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s?(?P<rest>.*)$")


def parse_timestamped_logs(raw: str) -> list[tuple[datetime | None, str]]:
    out: list[tuple[datetime | None, str]] = []
    for line in raw.splitlines():
        m = _TS_LINE_RE.match(line)
        if not m:
            out.append((None, line))
            continue
        ts_text = m.group("ts")
        try:
            # fromisoformat rejects >6 fractional digits before Python 3.11
            trimmed = re.sub(r"\.(\d{6})\d+Z$", r".\1Z", ts_text).replace("Z", "+00:00")
            ts: datetime | None = datetime.fromisoformat(trimmed)
        except ValueError:
            ts = None
        out.append((ts, m.group("rest")))
    return out


# --------------------------------------------------------------------------
# Repo evidence: what does this repo DECLARE as fleet/peer reachable?
# --------------------------------------------------------------------------


@dataclass
class Declaration:
    """A repo statement that <host>:<port> is reachable from another node."""

    host_expr: str   # "${TS_Z890}" or "pmoves-kvm4-2" -- never a resolved address
    port: int
    source: str      # repo-relative path
    kind: str        # "fleet-host-url" | "catalog-node-service"


# `${TS_Z890}:8105`, `$TS_Z890:8105`, `http://${TS_5090}:8055/...`
_TS_HOST_RE = re.compile(r"\$\{?(?P<var>TS_[A-Z0-9_]+)\}?:(?P<port>\d{2,5})")
# `| \`pmoves-kvm4-2\` | ... NATS \`:4222\` ...` rows in .claude/CATALOG.md
_CATALOG_PORT_RE = re.compile(r"`:(?P<port>\d{2,5})`")

CONFIG_GLOBS = (
    ".claude/*.json",
    ".claude/*.md",
    ".claude/context/*.md",
    "pmoves/config/*.yaml",
    "pmoves/config/*.yml",
    "pmoves/config/*.json",
    "pmoves/config/**/*.yaml",
    "pmoves/config/**/*.yml",
    "pmoves/config/**/*.json",
    "pmoves/configs/*.yaml",
    "pmoves/configs/*.yml",
    "pmoves/configs/*.json",
)


def _iter_config_files(repo_root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in CONFIG_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def load_node_reach_names(repo_root: Path) -> set[str]:
    """Reach names from pmoves/configs/node-vocabulary.yaml.

    Node identity comes from the vocabulary file -- not from a hardcoded list,
    and not from a profile's `id:`. A reach name in a URL means "another node in
    the fleet". A docker-compose service name in a URL means "the container next
    to me" and says NOTHING about peer reachability, which is why compose names
    are deliberately not a source of fleet declarations here.
    """
    path = repo_root / "pmoves" / "configs" / "node-vocabulary.yaml"
    names: set[str] = set()
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*reach:\s*['\"]?([A-Za-z0-9._-]+)['\"]?\s*$", line)
        if m:
            names.add(m.group(1))
    return names


def discover_declarations(repo_root: Path) -> list[Declaration]:
    """Derive fleet-reachable declarations from repo evidence only."""
    reach_names = load_node_reach_names(repo_root)
    reach_re = (
        re.compile(
            r"\b(?P<host>"
            + "|".join(re.escape(n) for n in sorted(reach_names, key=len, reverse=True))
            + r"):(?P<port>\d{2,5})"
        )
        if reach_names
        else None
    )

    decls: list[Declaration] = []
    for path in _iter_config_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _TS_HOST_RE.finditer(text):
            decls.append(
                Declaration("${%s}" % m.group("var"), int(m.group("port")),
                            rel, "fleet-host-url")
            )
        if reach_re is not None:
            for m in reach_re.finditer(text):
                decls.append(
                    Declaration(m.group("host"), int(m.group("port")),
                                rel, "fleet-host-url")
                )

    catalog = repo_root / ".claude" / "CATALOG.md"
    if catalog.exists():
        for line in catalog.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.lstrip().startswith("|"):
                continue
            host_m = re.search(r"`(?P<host>pmoves-[a-z0-9-]+)`", line)
            if not host_m or host_m.group("host") not in reach_names:
                continue
            for pm in _CATALOG_PORT_RE.finditer(line):
                decls.append(
                    Declaration(host_m.group("host"), int(pm.group("port")),
                                ".claude/CATALOG.md", "catalog-node-service")
                )
    return decls


def declared_fleet_ports(decls: Sequence[Declaration]) -> dict[int, list[Declaration]]:
    out: dict[int, list[Declaration]] = {}
    for d in decls:
        out.setdefault(d.port, []).append(d)
    return out


# --------------------------------------------------------------------------
# D1 -- loopback-vs-declared
# --------------------------------------------------------------------------


def detect_d1(
    containers: Sequence[Container],
    declared: dict[int, list[Declaration]],
) -> list[Finding]:
    """A port the repo tells peers to dial, published on loopback only."""
    findings: list[Finding] = []

    # A port may be published on loopback by one container and re-exposed on a
    # wildcard by a sidecar bridge -- pmoves-registry-port-bridge does exactly
    # this for :8110. Reachability is a property of the HOST PORT, not of one
    # container, so the wildcard set is computed runtime-wide before judging.
    wildcard_ports = {
        b.host_port for c in containers for b in c.bindings if b.is_wildcard
    }

    for c in containers:
        for b in c.bindings:
            if not b.is_loopback or b.host_port not in declared:
                continue
            group = declared[b.host_port]
            ev = {
                "host_port": b.host_port,
                "bound_to": b.host_ip,
                "declared_for_hosts": sorted({d.host_expr for d in group}),
                "declared_in": sorted({d.source for d in group})[:5],
                "declaration_count": len(group),
            }
            if b.host_port in wildcard_ports:
                findings.append(Finding(
                    "D1", f"{c.name}:{b.host_port}", CLEAN,
                    "loopback binding, but the same host port is published on a "
                    "wildcard address elsewhere in the runtime", ev))
            else:
                findings.append(Finding(
                    "D1", f"{c.name}:{b.host_port}", FIRE,
                    f"port {b.host_port} is declared peer-reachable in "
                    f"{len(group)} place(s) but is published only on "
                    f"{b.host_ip} -- unreachable from any peer", ev))
    return findings
