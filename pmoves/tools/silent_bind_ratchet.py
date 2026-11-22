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

THE BASE REVISION
-----------------
The baseline may only SHRINK. That is NOT enforceable by comparing the
baseline with the gaps measured in the SAME checkout: a change that
introduces a new internal-only published port AND adds the matching
baseline entry compares clean, because the entry and the gap arrive
together.

So the gate can measure the BASE revision too, and does when it is given
one (``--base-ref``). The base revision's compose files are materialized
into a temporary tree and measured with the SAME code, so the comparison is
between two MEASUREMENTS rather than between two intentions. A baseline
entry whose (file, service) pair is not a gap AT THE BASE is a
BASELINE_ADDITION.

This is the house's own shape for the same question: the damage-control
differential sweep (``.claude/hooks/damage-control/sweep_differential.py``)
materializes the base version of the thing under test and diffs the two
verdicts, and the workflow that drives it resolves the base SHA from
``github.event.pull_request.base.sha`` over a full-history checkout.

Without ``--base-ref`` the addition rule is NOT enforced, and the tool says
so on every run. A gate that silently does less than it claims is worse
than one that is explicit about the smaller thing it does.

FINDINGS
--------
  UNACTIVATABLE_PORT  a service publishes a host port but joins only
                       internal:true networks.
  STALE_GAP           a recorded gap that is no longer a gap (the service was
                       fixed but the record was left behind).
  UNREASONED_GAP      a recorded gap whose reason is missing or is still the
                       "REVIEW THIS" placeholder.
  BASELINE_ADDITION   a baseline entry for a gap that did NOT exist at the
                       base revision -- the escape hatch this gate exists to
                       close.
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
    python pmoves/tools/silent_bind_ratchet.py --check --base-ref <git-ref>
    python pmoves/tools/silent_bind_ratchet.py --write-baseline --yes
    python pmoves/tools/silent_bind_ratchet.py --check --json
"""
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

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
BASELINE_ADDITION = "BASELINE_ADDITION"
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


def _rel_path(path: Path, root: Optional[Path]) -> str:
    """The file's path RELATIVE to the pmoves/ root, POSIX style.

    Two different files in the house scope share the name
    ``docker-compose.core.yml``: ``pmoves/docker-compose.core.yml`` (the main
    stack's core overlay, 85 KB) and ``pmoves/compose/docker-compose.core.yml``
    (the separate n8n stack, 2.5 KB). Keying the baseline on the bare
    filename lets those two collide, so the key carries the path relative to
    the root instead.

    For the 73 currently measured gaps this changes nothing: every one of them
    lives in a top-level file, where the relative path IS the bare filename.
    It removes the collision rather than introducing a churn.
    """
    if root is None:
        return path.name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def scan_file(path: Path, canon: Dict[str, Optional[bool]], root: Optional[Path] = None) -> Tuple[List[dict], List[dict]]:
    """Return (gaps, errors) for one compose file."""
    gaps: List[dict] = []
    errors: List[dict] = []
    rel = _rel_path(path, root)
    try:
        doc = load_doc(path)
    except Exception as exc:
        errors.append({"kind": INSTRUMENT_ERROR, "file": rel, "detail": str(exc)})
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
                "file": rel,
                "service": sname,
                "networks": nets,
                "ports": ports,
            })
    return gaps, errors


def measure(root: Path) -> Tuple[List[dict], List[dict], Dict[str, Optional[bool]]]:
    """Measure one pmoves/ tree. Returns (gaps, errors, canonical networks).

    The SAME function measures the working tree and the base revision's
    materialized tree, so the baseline-addition rule compares two
    measurements instead of two intentions.
    """
    files = compose_files(root)
    canon = canonical_networks(files)
    gaps: List[dict] = []
    errors: List[dict] = []
    for f in files:
        g, e = scan_file(f, canon, root)
        gaps.extend(g)
        errors.extend(e)
    return gaps, errors, canon


# --------------------------------------------------------------------------
# base revision
# --------------------------------------------------------------------------
def _git(repo: Path, args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo)] + args, capture_output=True)


@contextlib.contextmanager
def base_tree(ref: str, repo: Path) -> Iterator[Path]:
    """Materialize the base revision's in-scope compose files.

    Yields the path of a temporary directory that plays the role of pmoves/.
    Any failure raises, and the caller turns that into exit 3 -- a gate that
    cannot read its base cannot judge the baseline, and must say so rather
    than report a clean tree.

    The blobs are read with ``git cat-file blob`` rather than ``git show``
    because ``git show`` applies the repository's end-of-line conversion on
    the way out, while ``cat-file`` hands back the bytes that are actually
    stored. The measurement must see the committed content.
    """
    tmp = Path(tempfile.mkdtemp(prefix="silent-bind-base-"))
    try:
        listing = _git(repo, ["ls-tree", "-r", "--name-only", ref, "--", "pmoves/"])
        if listing.returncode != 0:
            raise RuntimeError(
                f"cannot list {ref} in {repo}: "
                f"{listing.stderr.decode('utf-8', 'replace').strip()}")
        names = [
            n for n in listing.stdout.decode("utf-8", "replace").splitlines()
            if n.endswith(".yml")
            and (n.startswith("pmoves/docker-compose") or n.startswith("pmoves/compose/"))
        ]
        base_root = tmp / "pmoves"
        for name in names:
            blob = _git(repo, ["cat-file", "blob", f"{ref}:{name}"])
            if blob.returncode != 0:
                raise RuntimeError(
                    f"cannot read {ref}:{name}: "
                    f"{blob.stderr.decode('utf-8', 'replace').strip()}")
            out = base_root / Path(name).relative_to("pmoves")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(blob.stdout)
        yield base_root
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


def run_check(path: Optional[Path] = None, pmoves_dir: Optional[Path] = None,
              base_ref: Optional[str] = None, repo: Optional[Path] = None) -> Tuple[int, dict]:
    root = PMOVES if pmoves_dir is None else Path(pmoves_dir)
    gaps, errors, canon = measure(root)

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

    # The baseline-addition rule. Only enforceable against a base revision:
    # without one there is nothing to compare the entry against, and the run
    # says so rather than implying the rule was applied.
    base_gaps_measured: Optional[int] = None
    additions: List[dict] = []
    if base_ref:
        git_repo = REPO_ROOT if repo is None else Path(repo)
        base_keys: Optional[set] = None
        try:
            with base_tree(base_ref, git_repo) as base_root:
                b_gaps, b_errors, _ = measure(base_root)
                base_gaps_measured = len(b_gaps)
                base_keys = {(g["file"], g["service"]) for g in b_gaps}
                for e in b_errors:
                    errors.append({
                        "kind": INSTRUMENT_ERROR,
                        "file": f"base:{base_ref}:{e['file']}",
                        "detail": e["detail"],
                    })
        except Exception as exc:
            errors.append({
                "kind": INSTRUMENT_ERROR,
                "file": f"base:{base_ref}",
                "detail": str(exc),
            })
        if base_keys is not None:
            for key in sorted(baseline):
                if key not in base_keys:
                    additions.append({
                        "kind": BASELINE_ADDITION, "file": key[0], "service": key[1],
                        "networks": [], "ports": None,
                        "detail": "recorded for a gap that did not exist at the base revision",
                    })
            findings.extend(additions)

    report = {
        "files_in_scope": len(compose_files(root)),
        "files_out_of_scope": _out_of_scope_count(root),
        "canonical_networks": {k: v for k, v in sorted(canon.items())},
        "gaps_measured": len(gaps),
        "gap_services": len({g["service"] for g in gaps}),
        "baseline_entries": len(baseline),
        "base_ref": base_ref,
        "base_gaps_measured": base_gaps_measured,
        "baseline_additions": len(additions),
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
    ap.add_argument("--base-ref", default=None,
                    help="git ref of the base revision; enables the "
                         "baseline-addition rule (a baseline entry for a gap "
                         "that did not exist at the base)")
    ap.add_argument("--repo", default=None,
                    help="git repository to read the base revision from "
                         "(default: this repository)")
    args = ap.parse_args()

    pmoves_dir = Path(args.pmoves_dir) if args.pmoves_dir else None
    baseline_path = Path(args.baseline) if args.baseline else None
    repo_path = Path(args.repo) if args.repo else None

    if args.write_baseline:
        if not args.yes:
            print("refusing to write without --yes", file=sys.stderr)
            return 2
        root = PMOVES if pmoves_dir is None else pmoves_dir
        gaps, errors, _ = measure(root)
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

    rc, report = run_check(baseline_path, pmoves_dir, args.base_ref, repo_path)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return rc
    print(f"compose files in scope: {report['files_in_scope']} "
          f"(out of scope: {report['files_out_of_scope']})")
    print(f"silent-bind gaps measured: {report['gaps_measured']} "
          f"across {report['gap_services']} service(s)")
    print(f"baseline entries: {report['baseline_entries']}")
    if report.get("base_ref"):
        print(f"base revision: {report['base_ref']} "
              f"({report['base_gaps_measured']} gap(s) measured there) "
              f"-- the baseline-addition rule IS enforced")
    else:
        print("base revision: NOT SUPPLIED -- the baseline-addition rule is "
              "NOT enforced in this run")
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
