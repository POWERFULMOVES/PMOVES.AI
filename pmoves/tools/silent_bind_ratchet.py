#!/usr/bin/env python3
"""Ratchet: a published HOST port must be able to activate.

WHY
---
Docker activates a published port only when the container is attached to at
least one network that is NOT ``internal: true``. On an internal-only
container the binding is STORED and never activated -- the container looks
published in ``docker inspect`` and the host port refuses connections.

Upstream source of truth
-------------------------
moby/moby#36174 -- "--internal bridge networked containers cannot expose
ports" -- https://github.com/moby/moby/issues/36174 (OPEN as of 2026-11-22).
The issue carries the canonical proof shape in its own ``docker container
inspect`` output: ``HostConfig.PortBindings`` holds the REQUESTED binding
while ``NetworkSettings.Ports`` is empty. Comparing those two maps PER KEY
is therefore the authoritative detection, not a text search for
``"HostPort": null`` -- that grep misses the ``{"8084/tcp": null}`` shape
entirely.

Docker's own maintainer on that issue (thaJeztah, 2018-02-07): "As far as
I'm aware, this is by design, and ``--internal`` networks should not be
reachable, even with ``-p`` being used". The behaviour is documented in the
house, not merely in an upstream tracker:

    pmoves/docs/operations/DOCKER_NETWORK_HARDENING.md Rule 5 --
    "There is no 'publish without egress.' Front it with a gateway."

        | network config              | host port published          | outbound egress |
        |-----------------------------|------------------------------|-----------------|
        | internal: true              | no (binding stored, never    | blocked         |
        |                             | activated)                   |                 |
        | internal: false             | yes                          | yes             |

The same doc names the tier that DOES publish: ``pmoves_public`` is the
"Host-reachable + egress-capable" bridge (``internal: false``), and
``pmoves_external`` / ``pmoves_db_egress`` are ``external: true`` -- compose
adopts them and does not own their ``internal`` flag, so their internality
is NOT knowable from source.

WHERE THIS SITS AMONG THE HOUSE INSTRUMENTS
--------------------------------------------
This is the STATIC twin of the house's RUNTIME auditor, not a replacement
for it:

  * ``make -C pmoves net-reality``
    (``pmoves/scripts/audit_network_reality.sh``) compares what each
    container REQUESTED against what the daemon ACTIVATED. It needs a
    running Docker daemon, so it cannot run on a GitHub-hosted runner.
  * ``pmoves/scripts/smoke-tests.sh`` owns ``_silent_bind_owner()``. It is
    wired into ``test_tcp_connectivity()`` (which FAILS on a silent bind)
    but NOT into ``test_http_endpoint()``, which collapses a refused
    connection into a WARNING -- so the live run reported "41 tests, 22
    passed, 20 warnings, 0 failed" while four of those warnings WERE
    silent binds, and ``grep SILENT BIND`` matched nothing.

This gate needs no daemon, so it runs on every PR.

WHAT IS MEASURED
----------------
For every service in the house compose scope that publishes a host port,
the service's networks are resolved and each network's ``internal`` flag is
read. A service whose every network is ``internal: true`` CANNOT activate
its published port.

Network internality is resolved per file, in this order:

  1. the file declares the network ``external: true``  -> UNKNOWN (compose
     does not own it; the flag is not knowable from source);
  2. the file declares the network with ``internal:``   -> that value;
  3. otherwise the network INHERITS the canonical PMOVES declaration from
     ``docker-compose.yml`` + ``docker-compose.base.yml`` -- the two files
     that own the main stack's network topology. This step is load-bearing:
     ten files in the scope re-declare ``pmoves_api`` / ``pmoves_app`` /
     ``pmoves_bus`` WITHOUT an ``internal:`` key, and a naive "first
     declaration wins" map silently degrades those networks to UNKNOWN and
     blinds the gate to the split overlays;
  4. the canonical set is silent on it                   -> UNKNOWN.

UNKNOWN is never a finding: an unknown network means the service may already
be reachable, and claiming a defect there would be a guess.

A service that declares NO ``networks:`` key joins the file's DEFAULT
network, which is a normal bridge -- so it is NOT a gap unless that file
declares its ``default:`` network with ``internal: true``. Scoring an empty
network set as a gap is vacuous truth, and it is not what Docker does.

FINDINGS
--------
  UNACTIVATABLE_PORT  a service publishes a host port but joins only
                       internal:true networks.
  STALE_GAP           a recorded gap that is no longer a gap (the service was
                       fixed but the record was left behind).
  UNREASONED_GAP      a recorded gap whose reason is missing or is still the
                       "REVIEW THIS" placeholder.
  INSTRUMENT_ERROR    a compose file that cannot be read or parsed.

FAIL CLOSED
-----------
An unreadable or unparseable compose file is an INSTRUMENT ERROR, not a
skip. A gate that cannot measure its input must not report success. Exit
codes follow the house convention: 0 clean, 1 drift, 3 COULD NOT MEASURE.

SCOPE
-----
The house scope: ``pmoves/docker-compose*.yml`` plus ``pmoves/compose/*.yml``
-- the SAME files ``get_all_compose_files()`` collects in
``pmoves/tests/smoke/test_port_conflicts.py``, so this gate and the house
port test measure the same thing. The count of files OUTSIDE the scope is
printed on every run, so the boundary of the audit is a measured number
rather than an assertion.

Usage:
    python pmoves/tools/silent_bind_ratchet.py --check
    python pmoves/tools/silent_bind_ratchet.py --write-baseline --yes
    python pmoves/tools/silent_bind_ratchet.py --check --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES = REPO_ROOT / "pmoves"
BASELINE = PMOVES / "configs" / "silent_bind" / "_known_gaps.yaml"

# The files that own the main stack's network topology. Every other file in
# the scope inherits these declarations.
CANONICAL_NETWORK_FILES = ("docker-compose.yml", "docker-compose.base.yml")

UNACTIVATABLE_PORT = "UNACTIVATABLE_PORT"
STALE_GAP = "STALE_GAP"
UNREASONED_GAP = "UNREASONED_GAP"
INSTRUMENT_ERROR = "INSTRUMENT_ERROR"

PLACEHOLDER_REASON = "REVIEW THIS"

EXIT_CLEAN = 0
EXIT_DRIFT = 1
EXIT_COULD_NOT_MEASURE = 3


class ComposeLoader(yaml.SafeLoader):
    """A loader that understands Docker Compose's two custom YAML tags.

    Compose accepts ``!reset`` (drop the merged value, fall back to the
    default) and ``!override`` (replace the merged value outright). PyYAML
    rejects both with "could not determine a constructor", and three files
    in the house scope use them:

        pmoves/docker-compose.amd-voice.yml   devices: !reset []
        pmoves/docker-compose.amd.yml          runtime: !reset null
        pmoves/docker-compose.hardened.yml     tmpfs:  !override

    A gate that cannot read a file in its own scope must FAIL CLOSED, but
    failing closed on a tag the format legitimately has would make the gate
    permanently red and therefore ignored. The tags are resolved to their
    plain value here; for this gate's question -- can the port activate --
    a reset key is equivalent to the key being absent.
    """


def _compose_value(loader: yaml.Loader, node: yaml.Node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


ComposeLoader.add_constructor("!reset", _compose_value)
ComposeLoader.add_constructor("!override", _compose_value)


def compose_files(pmoves_dir: Optional[Path] = None) -> List[Path]:
    """The house scope -- the same files test_port_conflicts.py collects.

    ``pmoves_dir`` lets the gate be pointed at a temp tree by the tests; the
    default is this repository's ``pmoves/``.
    """
    root = PMOVES if pmoves_dir is None else Path(pmoves_dir)
    return sorted(root.glob("docker-compose*.yml")) + sorted(root.glob("compose/*.yml"))


def load_doc(path: Path) -> dict:
    """Parse one compose file, or raise."""
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=ComposeLoader)
    if not isinstance(doc, dict):
        raise ValueError("top level is not a mapping")
    return doc


def _declared_flags(doc: dict) -> Dict[str, Optional[bool]]:
    """networks.<name> -> internal? (None = external or unstated)."""
    flags: Dict[str, Optional[bool]] = {}
    for name, spec in (doc.get("networks") or {}).items():
        if not isinstance(spec, dict):
            flags[name] = None
            continue
        if spec.get("external"):
            # compose adopts the network and does not own its driver/internal
            flags[name] = None
            continue
        if "internal" in spec:
            flags[name] = bool(spec["internal"])
        else:
            flags[name] = None
    return flags


def canonical_networks(files: Optional[List[Path]] = None) -> Dict[str, Optional[bool]]:
    """The main stack's network topology: network -> internal?.

    A network the canonical pair declares with ``internal:`` is authoritative.
    A network it declares ``external: true`` is UNKNOWN (compose does not own
    it). A network it does not mention at all is UNKNOWN.
    """
    scope = files if files is not None else compose_files()
    canon: Dict[str, Optional[bool]] = {}
    for name in CANONICAL_NETWORK_FILES:
        path = next((f for f in scope if f.name == name), None)
        if path is None:
            continue
        try:
            doc = load_doc(path)
        except Exception:
            continue
        for net, flag in _declared_flags(doc).items():
            if net not in canon:
                canon[net] = flag
            elif canon[net] is None and flag is not None:
                # a pair of canonical files that disagree on internality is a
                # broken premise, not a nuance: keep the explicit value.
                canon[net] = flag
    return canon


def resolve_internality(doc: dict, net: str, canon: Dict[str, Optional[bool]]) -> Optional[bool]:
    """internal? for one network as used by one file. None = UNKNOWN."""
    spec = (doc.get("networks") or {}).get(net)
    if isinstance(spec, dict):
        if spec.get("external"):
            return None
        if "internal" in spec:
            return bool(spec["internal"])
    return canon.get(net)


def service_networks(service: dict) -> List[str]:
    nets = service.get("networks")
    if isinstance(nets, dict):
        return [str(k) for k in nets.keys()]
    if isinstance(nets, list):
        return [str(n) for n in nets if isinstance(n, str)]
    return []


def service_ports(service: dict) -> List[str]:
    """The service's published ports, as readable strings."""
    ports = service.get("ports")
    out: List[str] = []
    if isinstance(ports, list):
        for p in ports:
            out.append(str(p))
    elif isinstance(ports, dict):        # compose long syntax
        for target, spec in ports.items():
            out.append(f"{target}:{spec}")
    return out


def _default_network_is_internal(doc: dict) -> Optional[bool]:
    spec = (doc.get("networks") or {}).get("default")
    if isinstance(spec, dict) and "internal" in spec:
        return bool(spec["internal"])
    return None


def scan_file(path: Path, canon: Dict[str, Optional[bool]]) -> Tuple[List[dict], List[dict]]:
    """Return (gaps, errors) for one compose file."""
    gaps: List[dict] = []
    errors: List[dict] = []
    try:
        doc = load_doc(path)
    except Exception as exc:
        errors.append({"kind": INSTRUMENT_ERROR, "file": path.name, "detail": str(exc)})
        return gaps, errors

    default_internal = _default_network_is_internal(doc)
    for sname, service in (doc.get("services") or {}).items():
        if not isinstance(service, dict):
            continue
        ports = service_ports(service)
        if not ports:
            continue
        nets = service_networks(service)
        if not nets:
            # No networks key -> the file's DEFAULT network, which is a normal
            # bridge unless that file declares it internal:true.
            if default_internal is True:
                nets = ["default"]
            else:
                continue
        flags = {n: resolve_internality(doc, n, canon) for n in nets}
        # Every network is EXPLICITLY internal -> the port can never activate.
        # A single unknown (external, or unstated) network means the service
        # may already be reachable; that is not a finding.
        if all(v is True for v in flags.values()):
            gaps.append({
                "kind": UNACTIVATABLE_PORT,
                "file": path.name,
                "service": sname,
                "networks": nets,
                "ports": ports,
            })
    return gaps, errors


def load_baseline(path: Optional[Path] = None) -> Dict[Tuple[str, str], str]:
    """(file, service) -> reason. A missing file is an empty mapping."""
    cfg = BASELINE if path is None else Path(path)
    if not cfg.is_file():
        return {}
    doc = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {}
    out: Dict[Tuple[str, str], str] = {}
    for entry in (doc.get("known_gaps") or []):
        if not isinstance(entry, dict):
            continue
        key = (str(entry.get("file", "")), str(entry.get("service", "")))
        out[key] = str(entry.get("reason", "") or "")
    return out


def write_baseline(gaps: List[dict], path: Optional[Path] = None) -> int:
    cfg = BASELINE if path is None else Path(path)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    entries = [{
        "file": g["file"],
        "service": g["service"],
        "reason": PLACEHOLDER_REASON,
    } for g in sorted(gaps, key=lambda x: (x["file"], x["service"]))]
    body = {"known_gaps": entries}
    header = (
        "# Recorded silent-bind gaps -- pmoves/tools/silent_bind_ratchet.py\n"
        "#\n"
        "# A service that publishes a host port while joined only to\n"
        "# internal:true networks CANNOT activate that port: Docker stores the\n"
        "# binding and never activates it (moby/moby#36174; house\n"
        "# DOCKER_NETWORK_HARDENING.md Rule 5).\n"
        "#\n"
        "# Each entry is a (file, service) pair measured by the ratchet. They are\n"
        "# recorded so the gate can be ENFORCED today without turning it red in a\n"
        "# single step. They are NOT approved, and none of them is 'expected'.\n"
        "#\n"
        "# The list may shrink and must never silently grow. A service that is\n"
        "# fixed but still listed here fails the gate as a STALE entry, so the\n"
        "# count only goes down.\n"
        "#\n"
        "# Regenerate: python pmoves/tools/silent_bind_ratchet.py --write-baseline --yes\n"
    )
    cfg.write_text(header + yaml.safe_dump(body, sort_keys=False, allow_unicode=True),
                   encoding="utf-8", newline="\n")
    return len(entries)


def _out_of_scope_count(pmoves_dir: Optional[Path] = None) -> int:
    root = PMOVES if pmoves_dir is None else Path(pmoves_dir)
    all_compose = set(root.rglob("docker-compose*.yml"))
    scoped = set(compose_files(root))
    return len(all_compose - scoped)


def run_check(path: Optional[Path] = None, pmoves_dir: Optional[Path] = None) -> Tuple[int, dict]:
    files = compose_files(pmoves_dir)
    canon = canonical_networks(files)
    gaps: List[dict] = []
    errors: List[dict] = []
    for f in files:
        g, e = scan_file(f, canon)
        gaps.extend(g)
        errors.extend(e)

    baseline = load_baseline(path)
    measured = {(g["file"], g["service"]): g for g in gaps}

    findings: List[dict] = []
    for key, g in sorted(measured.items()):
        if key not in baseline:
            findings.append(dict(g, detail="not in the baseline"))
    for key, reason in sorted(baseline.items()):
        if key not in measured:
            findings.append({
                "kind": STALE_GAP, "file": key[0], "service": key[1],
                "networks": [], "ports": None,
                "detail": "recorded but no longer a gap",
            })
        elif not reason.strip() or reason.strip() == PLACEHOLDER_REASON:
            findings.append(dict(measured[key],
                                 detail="recorded without a reviewed reason"))

    report = {
        "files_in_scope": len(files),
        "files_out_of_scope": _out_of_scope_count(pmoves_dir),
        "canonical_networks": {k: v for k, v in sorted(canon.items())},
        "gaps_measured": len(gaps),
        "gap_services": len({g["service"] for g in gaps}),
        "baseline_entries": len(baseline),
        "findings": findings,
        "instrument_errors": errors,
    }
    if errors:
        rc = EXIT_COULD_NOT_MEASURE
    elif findings:
        rc = EXIT_DRIFT
    else:
        rc = EXIT_CLEAN
    return rc, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="run the gate")
    ap.add_argument("--write-baseline", action="store_true",
                    help="write the baseline for the measured gaps")
    ap.add_argument("--yes", action="store_true", help="confirm the write")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--pmoves-dir", default=None,
                    help="scan this directory instead of the repo's pmoves/")
    ap.add_argument("--baseline", default=None,
                    help="use this baseline file instead of the repo's")
    args = ap.parse_args()

    pmoves_dir = Path(args.pmoves_dir) if args.pmoves_dir else None
    baseline_path = Path(args.baseline) if args.baseline else None

    if args.write_baseline:
        if not args.yes:
            print("refusing to write without --yes", file=sys.stderr)
            return 2
        files = compose_files(pmoves_dir)
        canon = canonical_networks(files)
        gaps: List[dict] = []
        errors: List[dict] = []
        for f in files:
            g, e = scan_file(f, canon)
            gaps.extend(g)
            errors.extend(e)
        if errors:
            print("INSTRUMENT ERROR -- refusing to write a baseline from a partial read:",
                  file=sys.stderr)
            for e in errors:
                print(f"  {e['file']}: {e['detail']}", file=sys.stderr)
            return EXIT_COULD_NOT_MEASURE
        n = write_baseline(gaps, baseline_path)
        print(f"Baseline written: {n} entries")
        print("EVERY reason is a placeholder. Each one must be reviewed and "
              "written before the gate is meaningful.")
        return 0

    rc, report = run_check(baseline_path, pmoves_dir)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return rc
    print(f"compose files in scope: {report['files_in_scope']} "
          f"(out of scope: {report['files_out_of_scope']})")
    print(f"silent-bind gaps measured: {report['gaps_measured']} "
          f"across {report['gap_services']} service(s)")
    print(f"baseline entries: {report['baseline_entries']}")
    for e in report["instrument_errors"]:
        print(f"  INSTRUMENT ERROR {e['file']}: {e['detail']}")
    for f in report["findings"]:
        print(f"  {f['kind']} {f['file']}:{f['service']} -- {f['detail']}")
    if rc == EXIT_CLEAN:
        print(f"clean: every measured gap ({report['gaps_measured']}) is recorded in "
              f"the baseline and no baseline entry is stale. The recorded gaps "
              f"are NOT approved -- they are the work this gate is holding open.")
    elif rc == EXIT_COULD_NOT_MEASURE:
        print(f"COULD NOT MEASURE: {len(report['instrument_errors'])} unreadable "
              f"compose file(s). This is NOT a pass.")
    else:
        print(f"DRIFT: {len(report['findings'])} finding(s)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
