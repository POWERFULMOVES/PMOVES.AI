#!/usr/bin/env python3
"""Read-only health preflight for the Docker Desktop data disk on Windows.

Why
---
2026-10-13/14, node z890. Docker Desktop's data vhdx lived on an external USB
drive (I:) behind a hand-made junction::

    %LOCALAPPDATA%\\Docker\\wsl\\disk  ->  I:\\DockerData\\disk

A USB stall (System event 153, "IO operation ... was retried", on that disk)
surfaced inside the VM as ext4 I/O errors, the engine hung for ~17h, and the
operator ran ``docker desktop restart``. Docker's wsl-bootstrap then could not
read the disk, logged ``detected no file system. Formatting`` and invoked the
ext4 format tool against it. The format failed only because the device
returned ENXIO. Docker's bootstrap cannot tell an UNREADABLE disk from a BLANK
one, so restarting Docker Desktop on a flaky disk can wipe every volume.

This tool answers one question before anyone restarts or resets Docker
Desktop: is the data disk readable and quiet right now? Runbook:
``pmoves/docs/handoffs/z890-docker-data-disk-usb-spof-2026-10-14.md``.

What it does NOT do
-------------------
It never mounts, never runs fsck/repair, never restarts or stops Docker, never
writes anything. Every probe is a read: one ``open(..., "rb")`` of 8 bytes, a
directory listing, and read-only PowerShell queries (Get-Partition, Get-Disk,
Get-PhysicalDisk, Get-WinEvent).

Checks
------
a. data-disk-location  resolve the wsl\\disk junction; WARN if the target sits
                       on a USB / removable bus
b. vhdx-header         vhdx exists, opens for read, first 8 bytes == b"vhdxfile"
c. disk-events         System log events 7/51/129/153 in the last N hours
d. physical-disk-health  Get-PhysicalDisk HealthStatus / OperationalStatus
e. vm-init-log         newest Docker VM init.log files for I/O / ext4 errors and
                       the "detected no file system" format trigger

Exit codes
----------
  0  every check PASS
  1  at least one WARN (no FAIL)
  2  at least one FAIL  -- do NOT restart/reset Docker Desktop
  3  could not measure (non-Windows host, or a check was SKIPPED with nothing
     else to report) -- NOT a pass
  4  usage error

Usage::

    make -C pmoves docker-disk-preflight
    make -C pmoves docker-disk-preflight ARGS='--json'
    python pmoves/tools/docker_disk_preflight.py --hours 24 --fail-hours 1
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"

EXIT_PASS = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_UNMEASURED = 3
EXIT_USAGE = 4

VHDX_MAGIC = b"vhdxfile"

# Docker Desktop has used both layouts. docker_data.vhdx is current (4.30+);
# ext4.vhdx under wsl\data is the older docker-desktop-data distro layout.
VHDX_CANDIDATES = (
    ("disk", "docker_data.vhdx"),
    ("data", "ext4.vhdx"),
)

# System log event IDs that indicate storage trouble.
#   7    disk: bad block
#   51   disk: error during a paging operation
#   129  storport/miniport: reset issued to device (bus-level timeout)
#   153  disk: IO operation retried (the 2026-10-13 signature)
DISK_EVENT_IDS = (7, 51, 129, 153)
# These two mean the medium itself reported an error, not a transient retry.
HARD_EVENT_IDS = frozenset({7, 51})

USB_BUS_TYPES = frozenset({"usb", "1394", "sd", "mmc"})
GOOD_OPERATIONAL = frozenset({"ok", "online"})
FATAL_OPERATIONAL_MARKERS = (
    "lost communication",
    "failed",
    "no media",
    "offline",
    "not ready",
    "stopped",
    "predictive failure",
)

# init.log patterns. FAIL patterns are specific to the incident chain; the
# generic "I/O error" is a WARN because it also appears for unrelated mounts.
INIT_LOG_FAIL_PATTERNS = (
    ("detected-no-filesystem", re.compile(r"detected no file system", re.I)),
    ("ext4-error", re.compile(r"EXT4-fs error", re.I)),
    ("buffer-io-error", re.compile(r"Buffer I/O error", re.I)),
)
INIT_LOG_WARN_PATTERNS = (("io-error", re.compile(r"\bI/O error\b", re.I)),)
INIT_LOG_MAX_BYTES = 8 * 1024 * 1024  # tail cap per file

_DISK_NUMBER_RES = (
    re.compile(r"\bHarddisk(\d+)\b", re.I),
    re.compile(r"\bDisk (\d+)\b"),
)

POWERSHELL_TIMEOUT_S = 60


@dataclass
class CheckResult:
    name: str
    status: str
    summary: str
    evidence: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- helpers ---


def display_path(path: str, env: Optional[Dict[str, str]] = None) -> str:
    """Render a path without the operator's profile directory.

    ``C:\\Users\\<name>\\AppData\\Local\\Docker`` -> ``%LOCALAPPDATA%\\Docker``.
    Paths outside the profile (e.g. ``I:\\DockerData\\disk``) are unchanged.
    """
    env = os.environ if env is None else env
    norm = path
    for var in ("LOCALAPPDATA", "APPDATA", "USERPROFILE"):
        base = env.get(var)
        if not base:
            continue
        base_n = base.rstrip("\\/")
        if norm.lower() == base_n.lower():
            return "%" + var + "%"
        for sep in ("\\", "/"):
            prefix = base_n + sep
            if norm.lower().startswith(prefix.lower()):
                return "%" + var + "%" + sep + norm[len(prefix):]
    return norm


def strip_extended_prefix(path: str) -> str:
    r"""``\\?\I:\x`` -> ``I:\x``; ``\\?\UNC\srv\x`` -> ``\\srv\x``."""
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\") or path.startswith("\\??\\"):
        return path[4:]
    return path


def aggregate_exit(results: Sequence[CheckResult]) -> int:
    """FAIL > WARN > SKIP > PASS. An all-SKIP or SKIP+PASS run is unmeasured."""
    statuses = {r.status for r in results}
    if FAIL in statuses:
        return EXIT_FAIL
    if WARN in statuses:
        return EXIT_WARN
    if SKIP in statuses or not results:
        return EXIT_UNMEASURED
    return EXIT_PASS


def overall_label(code: int) -> str:
    return {
        EXIT_PASS: PASS,
        EXIT_WARN: WARN,
        EXIT_FAIL: FAIL,
        EXIT_UNMEASURED: "COULD-NOT-MEASURE",
    }.get(code, "ERROR")


def _find_powershell() -> Optional[str]:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return found
    return None


def run_powershell(script: str, timeout: int = POWERSHELL_TIMEOUT_S) -> str:
    """Run a READ-ONLY PowerShell snippet and return stdout.

    Raises RuntimeError with a readable message on any failure.
    """
    exe = _find_powershell()
    if not exe:
        raise RuntimeError("PowerShell not found on PATH")
    prelude = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    try:
        proc = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command", prelude + script],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"PowerShell timed out after {timeout}s") from exc
    except OSError as exc:
        raise RuntimeError(f"PowerShell could not start: {exc}") from exc
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        first = err.splitlines()[0] if err else f"exit {proc.returncode}"
        raise RuntimeError(f"PowerShell query failed: {first}")
    return out


def _json_list(text: str) -> List[Dict[str, Any]]:
    """PowerShell emits nothing, an object, or an array. Normalise to a list."""
    text = (text or "").strip()
    if not text:
        return []
    parsed = json.loads(text)
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [p for p in parsed if isinstance(p, dict)]
    raise ValueError(f"unexpected JSON shape: {type(parsed).__name__}")


# ---------------------------------------------- (a) data-disk location ------


def resolve_disk_dir(disk_dir: str) -> Dict[str, Any]:
    """Follow the wsl\\disk junction/symlink (read-only)."""
    info: Dict[str, Any] = {
        "configured": disk_dir,
        "exists": os.path.isdir(disk_dir),
        "is_link": False,
        "link_target": None,
        "resolved": disk_dir,
    }
    try:
        target = os.readlink(disk_dir)  # junctions + symlinks on py3.8+ Windows
    except (OSError, ValueError, NotImplementedError, AttributeError):
        target = None
    if target:
        info["is_link"] = True
        info["link_target"] = strip_extended_prefix(target)
    try:
        info["resolved"] = strip_extended_prefix(os.path.realpath(disk_dir))
    except OSError:
        pass
    return info


def drive_of(path: str) -> str:
    """Drive letter (``I:``) of the fully resolved path, or '' if none."""
    try:
        real = os.path.realpath(path)
    except OSError:
        real = path
    return os.path.splitdrive(strip_extended_prefix(real))[0]


def query_disk_info(drive_letter: str) -> Dict[str, Any]:
    """Bus type + health for the physical disk holding ``drive_letter``."""
    letter = drive_letter.rstrip(":\\/")
    if not re.fullmatch(r"[A-Za-z]", letter):
        raise RuntimeError(f"not a drive letter: {drive_letter!r}")
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$p = Get-Partition -DriveLetter {letter}; "
        "$d = Get-Disk -Number $p.DiskNumber; "
        "$pd = Get-PhysicalDisk | Where-Object { $_.DeviceId -eq [string]$p.DiskNumber } "
        "| Select-Object -First 1; "
        "[pscustomobject]@{ "
        "disk_number = [int]$p.DiskNumber; "
        "friendly_name = [string]$d.FriendlyName; "
        "bus_type = [string]$d.BusType; "
        "disk_health = [string]$d.HealthStatus; "
        "disk_operational = [string]($d.OperationalStatus -join ','); "
        "pd_found = [bool]($null -ne $pd); "
        "pd_health = [string]$pd.HealthStatus; "
        "pd_operational = [string]($pd.OperationalStatus -join ','); "
        "pd_media_type = [string]$pd.MediaType "
        "} | ConvertTo-Json -Compress"
    )
    rows = _json_list(run_powershell(script))
    if not rows:
        raise RuntimeError("no disk information returned")
    return rows[0]


def check_location(link: Dict[str, Any], disk: Optional[Dict[str, Any]],
                   disk_error: Optional[str]) -> CheckResult:
    name = "data-disk-location"
    shown = display_path(link["configured"])
    # Never let the operator's profile path leak into --json output.
    link = {**link,
            "configured": shown,
            "resolved": display_path(link["resolved"]),
            "link_target": display_path(link["link_target"]) if link["link_target"] else None}
    ev: List[str] = []
    if link["is_link"]:
        ev.append(f"{shown} -> {link['link_target']} (junction/symlink)")
    else:
        ev.append(f"{shown} (not a link; Docker default location)")
    if not link["exists"]:
        return CheckResult(name, FAIL, "Docker data disk directory does not exist or "
                           "its link target is unreachable", ev, {"link": link})
    if disk_error:
        ev.append(f"bus query: {disk_error}")
        return CheckResult(name, SKIP, "data disk path resolved; bus type unmeasured",
                           ev, {"link": link})
    assert disk is not None
    bus = (disk.get("bus_type") or "").strip()
    ev.append(f"disk {disk.get('disk_number')} '{disk.get('friendly_name')}' bus={bus or '?'}")
    data = {"link": link, "disk": disk}
    if bus.lower() in USB_BUS_TYPES:
        return CheckResult(
            name, WARN,
            f"Docker data vhdx is on a {bus} disk -- removable bus is a single point "
            "of failure (stall -> ext4 I/O errors -> engine hang)", ev, data)
    if not bus:
        return CheckResult(name, WARN, "bus type unknown", ev, data)
    return CheckResult(name, PASS, f"Docker data vhdx is on an internal {bus} disk", ev, data)


# --------------------------------------------------- (b) vhdx header --------


def find_vhdx(docker_wsl_dir: str) -> Optional[str]:
    for sub, fname in VHDX_CANDIDATES:
        p = os.path.join(docker_wsl_dir, sub, fname)
        if os.path.exists(p):
            return p
    return None


def check_vhdx_header(path: Optional[str]) -> CheckResult:
    name = "vhdx-header"
    if not path:
        return CheckResult(name, FAIL, "no Docker data vhdx found",
                           [", ".join(os.path.join(s, f) for s, f in VHDX_CANDIDATES)])
    shown = display_path(path)
    ev = [shown]
    try:
        size = os.path.getsize(path)
        ev.append(f"size={size} bytes")
    except OSError:
        size = None
    try:
        with open(path, "rb") as fh:
            head = fh.read(len(VHDX_MAGIC))
    except FileNotFoundError:
        return CheckResult(name, FAIL, "vhdx disappeared between listing and open", ev)
    except PermissionError as exc:
        winerr = getattr(exc, "winerror", None)
        ev.append(f"open: {type(exc).__name__} winerror={winerr}")
        if winerr in (32, 33):  # sharing / lock violation: VM holds it exclusively
            return CheckResult(name, WARN, "vhdx is locked by another process; header "
                               "not verified", ev, {"size": size})
        return CheckResult(name, FAIL, "vhdx could not be opened for read", ev, {"size": size})
    except OSError as exc:
        ev.append(f"open/read: {type(exc).__name__} errno={exc.errno} "
                  f"winerror={getattr(exc, 'winerror', None)}")
        return CheckResult(name, FAIL, "vhdx read failed (I/O error on the backing disk?)",
                           ev, {"size": size})
    ev.append(f"first {len(VHDX_MAGIC)} bytes={head!r}")
    if head != VHDX_MAGIC:
        return CheckResult(name, FAIL, "vhdx signature mismatch -- file is not a readable "
                           "VHDX", ev, {"size": size})
    return CheckResult(name, PASS, "vhdx readable, signature ok", ev, {"size": size})


# --------------------------------------------------- (c) disk events --------


def query_disk_events(hours: int) -> str:
    ids = ",".join(str(i) for i in DISK_EVENT_IDS)
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "try { "
        f"$e = Get-WinEvent -FilterHashtable @{{LogName='System'; Id={ids}; "
        f"StartTime=(Get-Date).AddHours(-{int(hours)})}} "
        "} catch { "
        "if ($_.FullyQualifiedErrorId -match 'NoMatchingEventsFound') { $e = @() } "
        "else { throw } "
        "}; "
        "$rows = @($e | ForEach-Object { [pscustomobject]@{ "
        "time = $_.TimeCreated.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); "
        "id = [int]$_.Id; provider = [string]$_.ProviderName; "
        "message = [string]$_.Message } }); "
        "ConvertTo-Json -InputObject $rows -Compress -Depth 3"
    )
    return run_powershell(script)


def _parse_time(value: str) -> Optional[_dt.datetime]:
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def event_disk_number(message: str) -> Optional[int]:
    for rx in _DISK_NUMBER_RES:
        m = rx.search(message or "")
        if m:
            return int(m.group(1))
    return None


def parse_events(raw: str) -> List[Dict[str, Any]]:
    """Normalise Get-WinEvent JSON to [{time, id, provider, message, disk}]."""
    out: List[Dict[str, Any]] = []
    for row in _json_list(raw):
        try:
            eid = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        msg = str(row.get("message") or "")
        out.append({
            "time": row.get("time"),
            "id": eid,
            "provider": str(row.get("provider") or ""),
            "message": msg,
            "disk": event_disk_number(msg),
        })
    return out


def evaluate_events(events: Sequence[Dict[str, Any]], docker_disk: Optional[int],
                    hours: int, fail_hours: float,
                    now: Optional[_dt.datetime] = None) -> CheckResult:
    name = "disk-events"
    now = now or _dt.datetime.now(_dt.timezone.utc)
    fail_cutoff = now - _dt.timedelta(hours=fail_hours)
    ours: List[Dict[str, Any]] = []
    unattributed: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("disk") is None or docker_disk is None:
            unattributed.append(ev)
        elif ev["disk"] == docker_disk:
            ours.append(ev)
        else:
            other.append(ev)

    def _summ(group: Iterable[Dict[str, Any]]) -> str:
        counts: Dict[str, int] = {}
        for e in group:
            key = f"{e['id']}/{e['provider'] or '?'}"
            counts[key] = counts.get(key, 0) + 1
        return ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())) or "none"

    def _span(group: Sequence[Dict[str, Any]]) -> str:
        times = sorted(t for t in (e.get("time") for e in group) if t)
        return f"{times[0]} .. {times[-1]}" if times else "?"

    disk_label = f"disk {docker_disk}" if docker_disk is not None else "docker disk (unknown #)"
    evidence = [
        f"window={hours}h; on {disk_label}: {len(ours)} [{_summ(ours)}]",
        f"unattributed: {len(unattributed)} [{_summ(unattributed)}]",
        f"other disks: {len(other)} [{_summ(other)}]",
    ]
    if ours:
        evidence.append(f"docker-disk event span (UTC): {_span(ours)}")
    if unattributed:
        evidence.append(f"unattributed event span (UTC): {_span(unattributed)}")
    data = {"docker_disk": docker_disk, "ours": len(ours),
            "unattributed": len(unattributed), "other": len(other)}

    hard = [e for e in ours if e["id"] in HARD_EVENT_IDS]
    recent = [e for e in ours if (_parse_time(e.get("time") or "") or now) >= fail_cutoff]
    if hard:
        return CheckResult(name, FAIL, f"{len(hard)} bad-block/paging error(s) on the Docker "
                           f"data disk in the last {hours}h", evidence, data)
    if recent:
        return CheckResult(name, FAIL, f"{len(recent)} disk error event(s) on the Docker data "
                           f"disk within the last {fail_hours:g}h -- disk is actively "
                           "misbehaving", evidence, data)
    if ours:
        return CheckResult(name, WARN, f"{len(ours)} disk error event(s) on the Docker data "
                           f"disk in the last {hours}h (none in the last {fail_hours:g}h)",
                           evidence, data)
    if unattributed:
        return CheckResult(name, WARN, f"{len(unattributed)} storage event(s) not attributable "
                           "to a disk number (could be the Docker data disk)", evidence, data)
    return CheckResult(name, PASS, f"no disk error events on the Docker data disk in the "
                       f"last {hours}h", evidence, data)


# ------------------------------------------- (d) physical-disk health -------


def check_physical_health(disk: Optional[Dict[str, Any]],
                          disk_error: Optional[str]) -> CheckResult:
    name = "physical-disk-health"
    if disk_error or disk is None:
        return CheckResult(name, SKIP, "physical disk health unmeasured",
                           [f"query: {disk_error or 'no data'}"])
    pd_found = bool(disk.get("pd_found"))
    health = (disk.get("pd_health") if pd_found else disk.get("disk_health")) or ""
    oper = (disk.get("pd_operational") if pd_found else disk.get("disk_operational")) or ""
    source = "Get-PhysicalDisk" if pd_found else "Get-Disk (no PhysicalDisk match)"
    ev = [f"{source}: HealthStatus={health or '?'} OperationalStatus={oper or '?'}",
          f"Get-Disk: HealthStatus={disk.get('disk_health') or '?'} "
          f"OperationalStatus={disk.get('disk_operational') or '?'}"]
    data = {"health": health, "operational": oper, "source": source}
    states = [s.strip().lower() for s in oper.split(",") if s.strip()]
    disk_oper = (disk.get("disk_operational") or "").lower()
    if health.lower() == "unhealthy" or any(
            m in s for s in states + [disk_oper] for m in FATAL_OPERATIONAL_MARKERS):
        return CheckResult(name, FAIL, "physical disk reports an unhealthy / non-operational "
                           "state", ev, data)
    if health.lower() != "healthy" or not states or any(s not in GOOD_OPERATIONAL for s in states):
        return CheckResult(name, WARN, "physical disk health is not clean", ev, data)
    return CheckResult(name, PASS, "physical disk Healthy / OK", ev, data)


# ------------------------------------------------ (e) VM init.log -----------


def newest_init_logs(log_dir: str, count: int) -> List[str]:
    try:
        names = [n for n in os.listdir(log_dir) if n.startswith("init.log")]
    except OSError:
        return []
    paths = [os.path.join(log_dir, n) for n in names]
    paths = [p for p in paths if os.path.isfile(p)]
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return paths[:max(count, 0)]


def scan_init_log_text(text: str) -> Dict[str, Any]:
    hits: Dict[str, int] = {}
    samples: List[str] = []
    severity = PASS
    for line in text.splitlines():
        matched = None
        for label, rx in INIT_LOG_FAIL_PATTERNS:
            if rx.search(line):
                matched = (label, FAIL)
                break
        if matched is None:
            for label, rx in INIT_LOG_WARN_PATTERNS:
                if rx.search(line):
                    matched = (label, WARN)
                    break
        if matched is None:
            continue
        label, sev = matched
        hits[label] = hits.get(label, 0) + 1
        if sev == FAIL:
            severity = FAIL
        elif severity == PASS:
            severity = WARN
        if len(samples) < 3:
            samples.append(line.strip()[:200])
    return {"severity": severity, "hits": hits, "samples": samples}


def _read_tail(path: str, limit: int = INIT_LOG_MAX_BYTES) -> str:
    with open(path, "rb") as fh:
        try:
            size = os.fstat(fh.fileno()).st_size
            if size > limit:
                fh.seek(size - limit)
        except OSError:
            pass
        return fh.read().decode("utf-8", errors="replace")


def check_init_logs(log_dir: str, count: int) -> CheckResult:
    name = "vm-init-log"
    files = newest_init_logs(log_dir, count)
    shown_dir = display_path(log_dir)
    if not files:
        return CheckResult(name, SKIP, "no Docker VM init.log found", [shown_dir])
    severity = PASS
    evidence: List[str] = []
    total: Dict[str, int] = {}
    per_file: List[Dict[str, Any]] = []
    for path in files:
        base = os.path.basename(path)
        try:
            res = scan_init_log_text(_read_tail(path))
        except OSError as exc:
            evidence.append(f"{base}: unreadable ({type(exc).__name__})")
            if severity == PASS:
                severity = WARN
            continue
        per_file.append({"file": base, **res})
        for k, v in res["hits"].items():
            total[k] = total.get(k, 0) + v
        if res["severity"] == FAIL:
            severity = FAIL
        elif res["severity"] == WARN and severity == PASS:
            severity = WARN
        hit_s = ", ".join(f"{k} x{v}" for k, v in sorted(res["hits"].items())) or "clean"
        evidence.append(f"{base}: {hit_s}")
        for s in res["samples"]:
            evidence.append(f"  > {s}")
    data = {"dir": shown_dir, "files": per_file, "totals": total}
    if severity == FAIL:
        summary = "VM log shows disk I/O / ext4 errors or the format trigger"
    elif severity == WARN:
        summary = "VM log shows generic I/O errors (or a log was unreadable)"
    else:
        summary = f"newest {len(files)} VM init log(s) clean"
    return CheckResult(name, severity, summary, evidence, data)


# ------------------------------------------------------------ driver --------


def run_checks(args: argparse.Namespace) -> List[CheckResult]:
    localappdata = args.localappdata or os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        return [CheckResult("environment", SKIP, "%LOCALAPPDATA% is not set")]
    docker_wsl = os.path.join(localappdata, "Docker", "wsl")
    disk_dir = args.disk_dir or os.path.join(docker_wsl, "disk")
    log_dir = os.path.join(localappdata, "Docker", "log", "vm")

    results: List[CheckResult] = []

    # (a) + (d) share a single PowerShell query.
    link = resolve_disk_dir(disk_dir)
    vhdx = args.vhdx or find_vhdx(docker_wsl)
    probe_path = vhdx or link["resolved"]
    drive = drive_of(probe_path)
    disk: Optional[Dict[str, Any]] = None
    disk_error: Optional[str] = None
    if not drive or not re.fullmatch(r"[A-Za-z]:", drive):
        disk_error = f"cannot map {display_path(probe_path)} to a drive letter"
    else:
        try:
            disk = query_disk_info(drive)
        except (RuntimeError, ValueError) as exc:
            disk_error = str(exc)
    results.append(check_location(link, disk, disk_error))

    # (b)
    results.append(check_vhdx_header(vhdx))

    # (c)
    docker_disk = None
    if disk is not None and disk.get("disk_number") is not None:
        try:
            docker_disk = int(disk["disk_number"])
        except (TypeError, ValueError):
            docker_disk = None
    try:
        events = parse_events(query_disk_events(args.hours))
        results.append(evaluate_events(events, docker_disk, args.hours, args.fail_hours))
    except (RuntimeError, ValueError) as exc:
        results.append(CheckResult("disk-events", SKIP, "System event log unmeasured",
                                   [str(exc)]))

    # (d)
    results.append(check_physical_health(disk, disk_error))

    # (e)
    results.append(check_init_logs(log_dir, args.log_files))
    return results


def render_text(results: Sequence[CheckResult], code: int) -> str:
    lines = [f"docker-disk-preflight (read-only) on {platform.node() or 'this node'}"]
    for r in results:
        lines.append(f"[{r.status}] {r.name}: {r.summary}")
        for e in r.evidence:
            lines.append(f"       {e}")
    lines.append(f"RESULT: {overall_label(code)} (exit {code})")
    if code in (EXIT_FAIL, EXIT_UNMEASURED):
        lines.append("Do NOT restart/reset Docker Desktop until this passes and a read-only "
                     "e2fsck of the vhdx is clean.")
    lines.append("Runbook: pmoves/docs/handoffs/z890-docker-data-disk-usb-spof-2026-10-14.md")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Read-only Docker Desktop data-disk preflight (Windows).")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--hours", type=int, default=72,
                   help="System event-log look-back window in hours (default 72)")
    p.add_argument("--fail-hours", type=float, default=1.0,
                   help="events on the Docker disk newer than this FAIL (default 1)")
    p.add_argument("--log-files", type=int, default=3,
                   help="how many newest VM init.log files to scan (default 3)")
    p.add_argument("--localappdata", help=argparse.SUPPRESS)
    p.add_argument("--disk-dir", help="override the Docker wsl\\disk directory")
    p.add_argument("--vhdx", help="override the vhdx path")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code not in (0, None) else 0
    if args.hours <= 0 or args.fail_hours < 0 or args.log_files < 0:
        print("docker-disk-preflight: --hours must be > 0; --fail-hours/--log-files >= 0",
              file=sys.stderr)
        return EXIT_USAGE

    if sys.platform != "win32":
        msg = (f"SKIP: docker-disk-preflight is Windows-only (Docker Desktop data vhdx); "
               f"nothing measured on {sys.platform}. Exit 3 = could not measure, not a pass.")
        if args.json:
            print(json.dumps({"platform": sys.platform, "exit_code": EXIT_UNMEASURED,
                              "result": overall_label(EXIT_UNMEASURED), "checks": [],
                              "message": msg}, indent=2))
        else:
            print(msg)
        return EXIT_UNMEASURED

    results = run_checks(args)
    code = aggregate_exit(results)
    if args.json:
        print(json.dumps({
            "platform": sys.platform,
            "exit_code": code,
            "result": overall_label(code),
            "checks": [asdict(r) for r in results],
        }, indent=2, default=str))
    else:
        print(render_text(results, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
