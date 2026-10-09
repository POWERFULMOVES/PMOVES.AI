#!/usr/bin/env python3
"""Green-but-disconnected detector.

The defect class: a thing that is BUILT, RUNNING, and REPORTING HEALTHY while
being functionally disconnected from everything that was supposed to consume it.
Five instances were measured on fleet-node-b850 on 2026-09-08 and are the
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
from fnmatch import fnmatch
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

    def _run(self, args: list[str], merge_stderr: bool = False) -> str:
        try:
            proc = subprocess.run(
                ["docker", *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise DockerUnavailable("docker CLI not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerUnavailable(f"docker {args[0]} timed out") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:200]
            raise DockerUnavailable(
                f"docker {args[0]} exited {proc.returncode}: {detail}")
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
        # merge_stderr is LOAD-BEARING. `docker logs` relays a container's
        # stderr to ITS stderr, and most services log errors there: promtail,
        # the D2 ground-truth fixture, writes 100% of its output to stderr.
        # Reading only stdout returned zero lines for it -- measured
        # 2026-09-08 -- so D2 called the fixture unmeasurable and would have
        # called it CLEAN under any less strict empty-result policy.
        raw = self._run(["logs", "--tail", str(tail), "--timestamps", name],
                        merge_stderr=True)
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

    host_expr: str   # "${TS_Z890}" or "fleet-node-vps" -- never a resolved address
    port: int
    source: str      # repo-relative path
    kind: str        # "fleet-host-url" | "catalog-node-service"


# `${TS_Z890}:8105`, `$TS_Z890:8105`, `http://${TS_5090}:8055/...`
_TS_HOST_RE = re.compile(r"\$\{?(?P<var>TS_[A-Z0-9_]+)\}?:(?P<port>\d{2,5})")
# `| \`fleet-node-vps\` | ... NATS \`:4222\` ...` rows in .claude/CATALOG.md
_CATALOG_PORT_RE = re.compile(r"`:(?P<port>\d{2,5})`")

CONFIG_GLOBS = (
    ".claude/*.json",
    ".claude/*.md",
    ".claude/**/*.json",
    ".claude/**/*.md",
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
        m = re.match(r"\s*-?\s*reach:\s*['\"]?([A-Za-z0-9._-]+)['\"]?\s*$", line)
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

    # docker publishes a wildcard port twice, once per address family
    # ("0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp"). One host port is one
    # reachability fact, so it gets one finding.
    seen: set[tuple[str, int]] = set()

    for c in containers:
        for b in c.bindings:
            if b.host_port not in declared:
                continue
            if (c.name, b.host_port) in seen:
                continue
            seen.add((c.name, b.host_port))
            group = declared[b.host_port]
            if b.is_wildcard:
                # The known-good counterpart is reported EXPLICITLY rather than
                # by omission. "No finding" and "measured and fine" read the
                # same in a summary, and this tool exists because things that
                # were never measured got counted as fine.
                findings.append(Finding(
                    "D1", f"{c.name}:{b.host_port}", CLEAN,
                    f"declared peer-reachable and published on {b.host_ip} -- "
                    "reachable from peers",
                    {"host_port": b.host_port, "bound_to": b.host_ip,
                     "declared_for_hosts": sorted({d.host_expr for d in group}),
                     "declared_in": sorted({d.source for d in group})[:5],
                     "declaration_count": len(group)}))
                continue
            if not b.is_loopback:
                continue
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


# --------------------------------------------------------------------------
# D2 -- healthy-but-erroring
# --------------------------------------------------------------------------

ERROR_MARKERS = (
    "level=error",
    "level=fatal",
    "level=critical",
    " error ",
    "error:",
    "exception",
    "traceback",
    "cannot connect",
    "connection refused",
    "name or service not known",
    "no such host",
    "permission denied",
    "panic:",
    "fatal:",
)

# Ordered most-specific-first: a UUID has to be collapsed before the bare-hex
# and digit rules chew it into fragments that no longer match across lines.
_NOISE_SUBS = (
    (re.compile(r"\b\d{4}-\d{2}-\d{2}t?[\d:.]+z?\b"), "<ts>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<uuid>"),
    (re.compile(r"\b[0-9a-f]{12,}\b"), "<hex>"),
    (re.compile(r"\b\d+(\.\d+)?\b"), "<n>"),
)


def error_signature(line: str) -> str | None:
    """Collapse a log line to a stable signature, or None if it is not an error.

    Timestamps, counters, durations, hashes and ids are erased so the SAME
    failure re-emitted with a fresh timestamp collapses to one signature --
    which is what "repeating" has to mean for D2 to be able to count anything.
    """
    low = line.lower()
    if not any(marker in low for marker in ERROR_MARKERS):
        return None
    sig = low
    for pattern, repl in _NOISE_SUBS:
        sig = pattern.sub(repl, sig)
    sig = re.sub(r"\s+", " ", sig).strip()
    return sig[:400] or None


def detect_d2(
    containers: Sequence[Container],
    log_fetch,
    *,
    window_minutes: int,
    repeat_threshold: int,
    tail: int,
    now: datetime | None = None,
) -> list[Finding]:
    """Green container whose own logs show the same error N+ times in M minutes.

    `window_minutes` and `repeat_threshold` are parameters, not magic numbers:
    a 5-second retry loop and a 5-minute reconcile loop need different
    thresholds, and one fixed pair would either miss the slow one or cry wolf
    on the fast one.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)
    findings: list[Finding] = []

    for c in containers:
        if not c.looks_green:
            continue  # already reporting badly -- not this defect class
        try:
            lines = log_fetch(c.name, tail)
        except DockerUnavailable as exc:
            findings.append(Finding("D2", c.name, CNM, f"could not read logs: {exc}",
                                    {"status": c.status, "health": c.health}))
            continue

        in_window = [(ts, t) for ts, t in lines if ts is not None and ts >= cutoff]
        undated = sum(1 for ts, _ in lines if ts is None)

        counts: dict[str, int] = {}
        for _, text in in_window:
            sig = error_signature(text)
            if sig:
                counts[sig] = counts.get(sig, 0) + 1

        # ALWAYS report both input sizes. An empty result reads identically
        # whether the service was quiet or the log read returned nothing --
        # see the --since harness trap in the module docstring.
        ev = {
            "status": c.status,
            "health": c.health,
            "lines_examined": len(lines),
            "lines_in_window": len(in_window),
            "lines_undated": undated,
            "window_minutes": window_minutes,
            "repeat_threshold": repeat_threshold,
            "distinct_error_signatures": len(counts),
        }

        if not lines:
            findings.append(Finding("D2", c.name, CNM,
                                    "log fetch returned zero lines -- cannot "
                                    "distinguish a silent service from a "
                                    "failed read", ev))
            continue
        if not in_window:
            # --tail returns the NEWEST N lines. If the newest DATED line
            # predates the cutoff, nothing was emitted inside the window and
            # that is a conclusive measurement, not an unknown. But if no line
            # carried a parseable timestamp at all, the window cannot be
            # applied and the honest answer is could-not-measure.
            dated = [ts for ts, _ in lines if ts is not None]
            if dated:
                newest = max(dated)
                ev["newest_line_age_minutes"] = round(
                    (now - newest).total_seconds() / 60.0, 1)
                findings.append(Finding(
                    "D2", c.name, CLEAN,
                    f"silent for the whole {window_minutes}m window "
                    f"(newest of {len(lines)} line(s) is "
                    f"{ev['newest_line_age_minutes']}m old)", ev))
            else:
                findings.append(Finding(
                    "D2", c.name, CNM,
                    f"{len(lines)} line(s) fetched but NONE carried a parseable "
                    "timestamp -- the window cannot be applied", ev))
            continue

        if counts:
            top_sig, top_n = max(counts.items(), key=lambda kv: kv[1])
            ev["top_signature"] = top_sig[:240]
            ev["top_signature_count"] = top_n
            if top_n >= repeat_threshold:
                findings.append(Finding(
                    "D2", c.name, FIRE,
                    f"reports {c.health or 'Up'} while the same error repeated "
                    f"{top_n}x in the last {window_minutes}m "
                    f"(threshold {repeat_threshold})", ev))
                continue
        findings.append(Finding(
            "D2", c.name, CLEAN,
            "no error signature reached the repeat threshold in the window", ev))
    return findings


# --------------------------------------------------------------------------
# D3 -- declared-but-unread
# --------------------------------------------------------------------------

DATA_SUFFIXES = {".json", ".yaml", ".yml", ".toml"}
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".sh", ".rs"}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages",
}

# Secret material is never a useful declaration source and this tool prints the
# paths it scanned, so the manifests are skipped outright rather than read and
# then filtered. Named as a glob so a v3 manifest is covered on arrival.
SKIP_DATA_GLOBS = ("pmoves/chit/secrets_manifest*",)

# The audit tool NAMES the fields it hunts, in prose and in DEFAULT_D3_FIELDS.
# Without this exclusion D3 finds itself and reports every field "read" --
# measured 2026-09-08: `cpu_arch` came back CLEAN with exactly one reader, this
# file, on the strength of the phrase `hardware_requirements.cpu_arch` in the
# module docstring. A detector that reports its own mention as a reader is the
# defect it hunts, so this exclusion is load-bearing, not cosmetic.
SELF_PATH = Path(__file__).resolve()
# The test suite names every field too, in assertions like out["cpu_arch"] --
# a genuine subscript that no regex can tell apart from a real read. Both files
# talk ABOUT the fields; neither consumes one.
SELF_EXCLUDED = {
    SELF_PATH,
    SELF_PATH.parent / "tests" / f"test_{SELF_PATH.stem}.py",
}

_PY_TRIPLE_DELIMS = (chr(34) * 3, chr(39) * 3)
_PY_TRIPLE_RE = re.compile("|".join(re.escape(d) for d in _PY_TRIPLE_DELIMS))


def strip_py_string_blocks(text: str) -> str:
    """Blank out triple-quoted blocks so prose cannot masquerade as a read.

    Docstrings routinely spell a field as `parent.field` while reading nothing.
    Lines are replaced, not deleted, so any reported line numbers stay true.
    """
    out: list[str] = []
    delim: str | None = None
    for line in text.splitlines():
        if delim is None:
            m = _PY_TRIPLE_RE.search(line)
            if not m:
                out.append(line)
                continue
            d = m.group(0)
            rest = line[m.end():]
            prefix = line[: m.start()]
            is_fstring = prefix.rstrip().endswith(("f", "rf", "fr"))
            if d in rest:  # opened and closed on the same line
                # f-strings contain LIVE reads (f"""{cfg['x']}""") —
                # blanking them turns a real read into a false FIRE
                # (2026-09-11 kilocode review finding). Keep content,
                # drop only the triple delimiters so patterns still match.
                if is_fstring:
                    out.append(prefix + rest.replace(d, "", 2))
                else:
                    out.append(prefix + rest.split(d, 1)[1])
                continue
            delim = d
            live_str = is_fstring  # multi-line f-string: interior interpolations read
            if live_str:
                out.append(line)  # keep opener + any same-line reads verbatim
            else:
                out.append(line[: m.start()])
        else:
            if delim in line:
                tail = line.split(delim, 1)[1]
                out.append(line if live_str else tail)
                delim = None
            else:
                out.append(line if live_str else "")
    return "\n".join(out)


def _walk(root: Path, suffixes: set[str]) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if p.suffix in suffixes:
                yield p


def _read_patterns(field: str) -> re.Pattern:
    f = re.escape(field)
    return re.compile(
        r"(?:"
        rf"\.get\(\s*['\"]{f}['\"]"        # d.get("field")
        # A subscript needs something to subscript. Without the lookbehind
        # the bare list literal ["cpu_arch", "room_id"] reads as a field
        # access, which is how an audit tool's own field list -- and its test
        # suite's -- got counted as readers on 2026-09-08.
        rf"|(?<=[\w\)\]])\[\s*['\"]{f}['\"]\s*\]"   # d["field"]
        rf"|getattr\([^)]*['\"]{f}['\"]"   # getattr(o, "field")
        rf"|\.{f}\b"                       # o.field / obj?.field / jq '.field'
        rf"|\b{f}\s*="                     # field = ...  (assignment / kwarg)
        rf"|\b{f}\s*:"                     # field: T     (annotation / TS type)
        r")"
    )


_COMMENT_PREFIXES = ("#", "//", "*", "/*", '"""', "'''")


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith(_COMMENT_PREFIXES)


def detect_d3(
    repo_root: Path,
    fields: Sequence[str],
    search_roots: Sequence[str] = ("pmoves",),
) -> list[Finding]:
    """Is a declared config field read by ANY code?

    A field that is declared, schema-validated and read by nothing is a
    constraint that cannot bind: it looks enforced and enforces nothing.
    """
    roots = [repo_root / r for r in search_roots if (repo_root / r).is_dir()]
    if not roots:
        return [Finding("D3", ",".join(fields), CNM,
                        f"no search root exists under {repo_root}",
                        {"search_roots": list(search_roots)})]

    def _skipped_data(p: Path) -> bool:
        rel = p.relative_to(repo_root).as_posix()
        return any(fnmatch(rel, g) for g in SKIP_DATA_GLOBS)

    data_files = [p for r in roots for p in _walk(r, DATA_SUFFIXES)
                  if not _skipped_data(p)]
    code_files = [p for r in roots for p in _walk(r, CODE_SUFFIXES)
                  if p.resolve() not in SELF_EXCLUDED]

    findings: list[Finding] = []
    for f in fields:
        decl_re = re.compile(rf"['\"]{re.escape(f)}['\"]\s*:|^\s*{re.escape(f)}\s*:")
        read_re = _read_patterns(f)

        declared_in: list[str] = []
        for p in data_files:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if f not in text:
                continue
            if any(decl_re.search(ln) for ln in text.splitlines()):
                declared_in.append(p.relative_to(repo_root).as_posix())

        read_in: list[str] = []
        for p in code_files:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if f not in text:
                continue
            if p.suffix == ".py":
                text = strip_py_string_blocks(text)
            for ln in text.splitlines():
                if _is_comment(ln):
                    continue  # a mention in a comment is not a reader
                if read_re.search(ln):
                    read_in.append(p.relative_to(repo_root).as_posix())
                    break

        ev = {
            "field": f,
            "data_files_scanned": len(data_files),
            "code_files_scanned": len(code_files),
            "declared_in_count": len(declared_in),
            "declared_in": sorted(declared_in)[:8],
            "read_in_count": len(read_in),
            "read_in": sorted(read_in)[:8],
        }
        if not declared_in:
            findings.append(Finding("D3", f, CNM,
                                    "field is not declared in any data file under "
                                    "the search roots -- nothing to assess", ev))
        elif read_in:
            findings.append(Finding("D3", f, CLEAN,
                                    f"declared in {len(declared_in)} file(s) and "
                                    f"read by {len(read_in)} code file(s)", ev))
        else:
            findings.append(Finding("D3", f, FIRE,
                                    f"declared in {len(declared_in)} data file(s) "
                                    "and read by ZERO code files -- a constraint "
                                    "that cannot bind", ev))
    return findings


# --------------------------------------------------------------------------
# D4 -- pointed-at-nothing
# --------------------------------------------------------------------------

R_LISTENING = "listening"
R_PORT_CLOSED = "port-closed"
R_ADDRESS_WRONG = "address-wrong"
R_TRANSPORT_DEAD = "transport-dead"


class NetProbe:
    """Three discriminators, because a single failure code lies.

    Lesson from this node on 2026-09-08: `HTTP 000` from curl meant an EXPIRED
    TAILSCALE NODE KEY, not a down service. Collapsing that to "service down"
    sends someone to restart a container that was never the problem. So a
    failure is only classified after asking three separate questions -- does the
    NAME resolve, does the MESH path carry, does the PORT answer.
    """

    def __init__(self, connect_timeout: float = 3.0, mesh_timeout: float = 4.0) -> None:
        self.connect_timeout = connect_timeout
        self.mesh_timeout = mesh_timeout

    def resolves(self, host: str) -> bool:
        try:
            socket.getaddrinfo(host, None)
            return True
        except socket.gaierror:
            return False

    def tcp(self, host: str, port: int) -> str:
        """-> "open" | "refused" | "unreachable" | "timeout"."""
        try:
            with socket.create_connection((host, port), timeout=self.connect_timeout):
                return "open"
        except socket.timeout:
            return "timeout"
        except OSError as exc:
            if exc.errno == errno.ECONNREFUSED:
                return "refused"
            if exc.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH):
                return "unreachable"
            return "timeout"

    def mesh_reachable(self, host: str) -> bool | None:
        """tailscale ping -> True / False, or None when tailscale is unavailable."""
        try:
            proc = subprocess.run(
                ["tailscale", "ping", "-c", "1",
                 "--timeout", f"{int(self.mesh_timeout)}s", host],
                capture_output=True, text=True, timeout=self.mesh_timeout + 4,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        return proc.returncode == 0


def detect_d4(
    decls: Sequence[Declaration],
    probe: NetProbe,
    env: dict[str, str] | None = None,
) -> list[Finding]:
    """For each declared endpoint: is anything actually LISTENING?"""
    env = env if env is not None else dict(os.environ)
    findings: list[Finding] = []

    targets: dict[tuple[str, int], list[Declaration]] = {}
    for d in decls:
        targets.setdefault((d.host_expr, d.port), []).append(d)

    for (host_expr, port), group in sorted(targets.items()):
        ev = {
            "host_expr": host_expr,   # env-var NAME or hostname, never an address
            "port": port,
            "declared_in": sorted({d.source for d in group})[:5],
        }
        subject = f"{host_expr}:{port}"

        m = re.fullmatch(r"\$\{?([A-Z0-9_]+)\}?", host_expr)
        if m:
            var = m.group(1)
            ev["env_var"] = var
            host = env.get(var, "")
            if not host:
                findings.append(Finding(
                    "D4", subject, CNM,
                    f"{var} is unset in this environment -- the endpoint cannot "
                    "be resolved from this node", ev))
                continue
            ev["env_var_resolved"] = True  # the VALUE is deliberately not recorded
        else:
            host = host_expr

        if not probe.resolves(host):
            findings.append(Finding(
                "D4", subject, FIRE,
                f"{R_ADDRESS_WRONG}: the declared host does not resolve from "
                "this node", {**ev, "classification": R_ADDRESS_WRONG}))
            continue

        state = probe.tcp(host, port)
        ev["tcp_state"] = state
        if state == "open":
            findings.append(Finding(
                "D4", subject, CLEAN,
                f"{R_LISTENING}: something answered on port {port}",
                {**ev, "classification": R_LISTENING}))
            continue
        if state == "refused":
            findings.append(Finding(
                "D4", subject, FIRE,
                f"{R_PORT_CLOSED}: host reachable, nothing listening on port "
                f"{port} -- config right, service absent",
                {**ev, "classification": R_PORT_CLOSED}))
            continue

        # timeout / unreachable is ambiguous: dead mesh path or filtered port.
        mesh = probe.mesh_reachable(host)
        ev["mesh_reachable"] = mesh
        if mesh is None:
            findings.append(Finding(
                "D4", subject, CNM,
                f"tcp {state} and no mesh prober available -- cannot tell a dead "
                "transport from a filtered port", ev))
        elif mesh is False:
            findings.append(Finding(
                "D4", subject, FIRE,
                f"{R_TRANSPORT_DEAD}: the mesh path to the host does not carry "
                "(e.g. expired node key) -- the SERVICE is not the thing to "
                "restart", {**ev, "classification": R_TRANSPORT_DEAD}))
        else:
            findings.append(Finding(
                "D4", subject, FIRE,
                f"{R_PORT_CLOSED}: mesh path carries but port {port} did not "
                f"answer ({state}) -- filtered or not bound",
                {**ev, "classification": R_PORT_CLOSED}))
    return findings


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

# A matched pair, both declared in pmoves/config/rooms/*.json, so the control
# differs from the fixture in exactly one way -- whether anything reads it.
DEFAULT_D3_FIELDS = (
    "cpu_arch",   # fixture 4: expect FIRE  -- declared + schema-validated, 0 readers
    "room_id",    # positive control: expect CLEAN -- read at
                  # pmoves/services/p7-room-orchestrator/catalog.py:107
)

VERDICT_NAME = {
    EXIT_CLEAN: "clean",
    EXIT_FINDINGS: "findings",
    EXIT_COULD_NOT_MEASURE: "could-not-measure",
}


def build_report(findings: Sequence[Finding], node: str) -> dict:
    by_verdict: dict[str, int] = {}
    by_detector: dict[str, dict[str, int]] = {}
    for f in findings:
        by_verdict[f.verdict] = by_verdict.get(f.verdict, 0) + 1
        bucket = by_detector.setdefault(f.detector, {})
        bucket[f.verdict] = bucket.get(f.verdict, 0) + 1
    code = aggregate_exit_code(findings)
    return {
        "tool": "disconnection_audit",
        "schema": 1,
        "node": node,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": code,
        "verdict": VERDICT_NAME[code],
        "counts": by_verdict,
        "by_detector": by_detector,
        "findings": [f.to_dict() for f in findings],
    }


def _infer_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() and (parent / "pmoves").is_dir():
            return parent
    return here.parents[2]


def _print_summary(report: dict, stream) -> None:
    print("", file=stream)
    print(f"disconnection_audit -> {report['verdict']} "
          f"(exit {report['exit_code']})", file=stream)
    for f in report["findings"]:
        if f["verdict"] == CLEAN:
            continue
        print(f"  [{f['verdict']:<17}] {f['detector']} {f['subject']}: "
              f"{f['reason']}", file=stream)
    print("  totals: " + ", ".join(f"{k}={v}" for k, v in sorted(report["counts"].items())),
          file=stream)
    if report["exit_code"] != EXIT_CLEAN:
        print("  NOTE: `make` collapses every nonzero exit to 2. "
              "Read exit_code in the JSON verdict.", file=stream)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Detect built-running-healthy-and-disconnected services.",
        epilog="exit 0 clean / 1 findings / 3 could-not-measure "
               "(make collapses nonzero to 2 -- read exit_code in the JSON)",
    )
    ap.add_argument("--repo-root", default=None, help="repo root (default: infer)")
    ap.add_argument("--detectors", default="D1,D2,D3,D4",
                    help="comma-separated subset, e.g. D1,D3")
    ap.add_argument("--log-window-min", type=int, default=15,
                    help="D2: minutes of log history to consider (default 15)")
    ap.add_argument("--repeat-threshold", type=int, default=5,
                    help="D2: identical error signatures needed to call it "
                         "repeating (default 5)")
    ap.add_argument("--log-tail", type=int, default=400,
                    help="D2: lines to pull per container (default 400)")
    ap.add_argument("--field", action="append", default=None,
                    help="D3: config field to test (repeatable). default: "
                         + ", ".join(DEFAULT_D3_FIELDS))
    ap.add_argument("--json", default=None,
                    help="write the JSON verdict here instead of stdout")
    ap.add_argument("--quiet", action="store_true", help="suppress the text table")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _infer_repo_root()
    wanted = {d.strip().upper() for d in args.detectors.split(",") if d.strip()}
    if not wanted:
        print("error: --detectors selected nothing (empty set)", file=sys.stderr)
        sys.exit(2)
    findings: list[Finding] = []

    docker = DockerProbe()
    containers: list[Container] = []
    docker_error: str | None = None
    if {"D1", "D2"} & wanted:
        try:
            containers = docker.containers()
        except DockerUnavailable as exc:
            docker_error = str(exc)

    decls = discover_declarations(repo_root) if {"D1", "D4"} & wanted else []

    if "D1" in wanted:
        if docker_error:
            findings.append(Finding("D1", "<runtime>", CNM,
                                    f"docker unavailable: {docker_error}", {}))
        elif not decls:
            findings.append(Finding("D1", "<repo>", CNM,
                                    "no fleet-reachable declarations found in repo "
                                    "config -- cannot judge any binding",
                                    {"repo_root": str(repo_root)}))
        else:
            findings += detect_d1(containers, declared_fleet_ports(decls))

    if "D2" in wanted:
        if docker_error:
            findings.append(Finding("D2", "<runtime>", CNM,
                                    f"docker unavailable: {docker_error}", {}))
        else:
            findings += detect_d2(
                containers, docker.logs,
                window_minutes=args.log_window_min,
                repeat_threshold=args.repeat_threshold,
                tail=args.log_tail,
            )

    if "D3" in wanted:
        findings += detect_d3(repo_root, args.field or list(DEFAULT_D3_FIELDS))

    if "D4" in wanted:
        if not decls:
            findings.append(Finding("D4", "<repo>", CNM,
                                    "no endpoint declarations found in repo config",
                                    {"repo_root": str(repo_root)}))
        else:
            findings += detect_d4(decls, NetProbe())

    report = build_report(
        findings, node=os.environ.get("PMOVES_NODE", socket.gethostname()))
    payload = json.dumps(report, indent=2)
    if args.json:
        Path(args.json).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

    if not args.quiet:
        _print_summary(report, sys.stderr)
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
