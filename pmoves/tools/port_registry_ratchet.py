#!/usr/bin/env python3
"""Ratchet: every published HOST port comes from the canonical registry.

WHY
---
A host port that is a bare literal in a compose file is a claim nobody
recorded. It collides silently with whatever else claims the same port, and
the collision only shows up when two stacks are brought up together -- which
is exactly the case nobody tests.

That is not hypothetical. MEASURED 2026-11-01, BEFORE this lane's
re-parameterisation: 71 published host ports were BARE LITERALS (the bind
address was parameterised; the port was not) and ZERO used Docker's dynamic
host port. The 8115 case the operator named --
``pmoves/docker-compose.yt-cookies.yml`` publishing ``127.0.0.1:8115`` for
``yt-cookie-refresher`` while ``node-registry`` published ``0.0.0.0:8115``
-- is one of those bare literals, in a compose file that is NOT in the
default stack, which is why it was latent rather than caught.

The live figures are deliberately NOT written here: the tool RECOMPUTES and
PRINTS them on every run -- 63 compose files in scope, 265 published port
slots, ZERO bare literals. This paragraph is a dated record of the BEFORE
state; the tool is the authority on the present, and a number typed into a
docstring is a claim nobody recomputes. (This file previously carried "64
compose files" and "262 published-port stanzas" -- the file count was 63 at
``origin/main`` too, so it was never true, and the two figures counted
different things.)

WHAT THIS MEASURES
------------------
``pmoves/configs/ports.yaml`` is the canonical registry: one entry per
service, holding a LIST of published port SLOTS. A slot is keyed by its port
variable, because that is the stable name the fleet already uses.

This gate checks the compose files against it and FAILS on:

  BARE_LITERAL     a host port that is not a ``${VAR:-default}`` expression.
                   This is the "no hard coded ports" rule.
  REGISTRY_DRIFT   a compose host-port DEFAULT that disagrees with the
                   registry's value for that slot.
  UNKNOWN_SLOT     a compose slot the registry does not know about.
  ORPHAN_SLOT      a registry slot that no compose file publishes.
  COLLISION        two slots claiming the same host port. Pre-existing
                   collisions are in a reviewed baseline that must shrink;
                   a NEW collision fails.
  INSTRUMENT_ERROR a file that cannot be read or parsed.

FAIL CLOSED
-----------
An unreadable or unparseable compose file is an INSTRUMENT ERROR, not a
skip. A gate that cannot measure its input must not report success.

SCOPE
-----
The house scope: ``pmoves/docker-compose*.yml`` plus ``pmoves/compose/*.yml``
-- the SAME files ``get_all_compose_files()`` collects in
``pmoves/tests/smoke/test_port_conflicts.py``, so this gate and the house
test measure the same thing. Files outside it (pmoves/monitoring/,
pmoves/integrations/, pmoves/docker/, ...) are separate deployables; their
count is printed on every run so the boundary of the audit is a measured
number rather than an assertion.

Usage:
    python pmoves/tools/port_registry_ratchet.py --check
    python pmoves/tools/port_registry_ratchet.py --write-collisions --yes

THE WRITER HANDS YOU A TO-DO LIST, NOT A PASSING GATE
------------------------------------------------------
``--write-collisions`` writes the baseline for the host ports TWO OR MORE
services claim -- not every published port -- and every reason it writes is
the PLACEHOLDER, which the gate reports as UNREVIEWED. A freshly written
baseline therefore FAILS the gate until a human replaces each reason with
why those two services may share the port. The writer, the header it
writes and the gate's enforcement all say the same thing.

Exit codes: 0 clean | 1 gate failed | 2 instrument/setup error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PMOVES_DIR = REPO_ROOT / "pmoves"
REGISTRY = PMOVES_DIR / "configs" / "ports.yaml"
COLLISIONS = PMOVES_DIR / "configs" / "port_registry" / "_known_collisions.yaml"

VAR_DEFAULT = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]*)\}")
VAR_PLAIN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
PORT_LINE = re.compile(r"^\s*(?P<body>.+?)\s*$")

# Services whose compose entries are alternative deployments of the SAME
# thing (traefik vs nginx, rustdesk.yml vs remote.yml, a base stack vs its
# own override). They publish the same host ports on purpose.
KNOWN_ALTERNATIVE_PAIRS: set[frozenset[str]] = set()

# The reason the baseline writer emits for a collision NO HUMAN has
# reviewed yet. The gate reports any reason carrying this prefix as
# UNREVIEWED -- so the writer, the header it writes and the gate's
# enforcement all tell the SAME story: a written baseline is a to-do list
# until a human replaces each reason.
REVIEW_PLACEHOLDER_PREFIX = "REVIEW THIS"
PLACEHOLDER_REASON = "REVIEW THIS -- a pre-existing duplicate host port"


class InstrumentError(RuntimeError):
    """The ratchet could not measure its input."""


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates docker-compose merge tags.

    ``!reset`` and ``!override`` are docker-compose extensions, not YAML 1.1
    tags, so ``yaml.safe_load`` refuses them. MEASURED: exactly three files
    in the house scope use them -- docker-compose.amd.yml,
    docker-compose.amd-voice.yml and docker-compose.hardened.yml -- and a
    gate that could not read them would be a gate with a hole exactly where
    the hardened overlay lives.
    """


SEEN_TAGS: set[str] = set()


def _unknown(loader, suffix, node):
    SEEN_TAGS.add(str(node.tag))
    return None


ComposeLoader.add_multi_constructor("!", _unknown)


def split_top_level(text: str) -> list[str]:
    """Split on ':' that are NOT inside a ${...} substitution."""
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in text:
        if ch == "{" and depth == 0 and buf and buf[-1] == "$":
            depth = 1
        elif ch == "}" and depth == 1:
            depth = 0
        if ch == ":" and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return parts


def resolve_host_slot(slot: str) -> tuple[int | None, str | None, bool]:
    """Resolve a HOST port slot to (value, variable_name, is_bare_literal).

    ``is_bare_literal`` is True when the slot is a plain number with no
    ``${...}`` in it -- the "hard coded port" this gate exists to stop.
    """
    raw = slot.strip()
    if not raw:
        return None, None, False
    if raw.isdigit():
        return int(raw), None, True
    m = VAR_DEFAULT.search(raw)
    if m:
        value = m.group(2).strip()
        return (int(value) if value.isdigit() else None), m.group(1), False
    # A variable with NO default: the value is unknown until the operator
    # sets it, but the VARIABLE NAME is still the registry key -- so it
    # must be returned. Returning None for the name here made the lookup
    # `slots_map.get(None)` miss, and the entry was reported as an
    # UNKNOWN SLOT -- a live compose entry would have failed the gate for
    # the wrong reason.
    m = VAR_PLAIN.match(raw)
    if m:
        return None, m.group(1), False
    plain = VAR_DEFAULT.sub("", raw).strip()
    if plain.isdigit():
        return None, None, False
    return None, None, False


def compose_files(root: Path | None = None) -> list[Path]:
    """The house scope -- see the module docstring.

    `root` is the repo root; it defaults to this file's repo. It is
    injectable so the CLI can be driven against a synthetic tree -- a gate
    that can only ever run against one tree cannot be tested at all.
    """
    base = (root or REPO_ROOT) / "pmoves"
    return sorted(
        [p for p in base.glob("docker-compose*.yml") if p.is_file()]
        + [p for p in (base / "compose").glob("*.yml") if p.is_file()]
    )


def out_of_scope_count(root: Path | None = None) -> int:
    """Compose files that exist in the tree but are OUTSIDE the house scope."""
    repo = root or REPO_ROOT
    in_scope = {p.resolve() for p in compose_files(repo)}
    count = 0
    for p in repo.rglob("docker-compose*.yml"):
        if ".git" in p.parts or "node_modules" in p.parts:
            continue
        try:
            p.resolve().relative_to(repo)
        except ValueError:
            continue
        if p.resolve() not in in_scope:
            count += 1
    return count


def load_registry(path: Path | None = None) -> dict:
    target = path or REGISTRY
    if not target.exists():
        raise InstrumentError(f"missing registry: {target}")
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise InstrumentError(f"cannot parse {target}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("services"), dict):
        raise InstrumentError(f"{target}: expected a mapping with a 'services' key")
    return data["services"]


def load_collisions(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise InstrumentError(f"cannot parse {path}: {exc}") from exc
    known = data.get("known_collisions") or {}
    if not isinstance(known, dict):
        raise InstrumentError(f"{path}: known_collisions must be a mapping")
    return known


def scan(registry: dict, files: list[Path] | None = None, root: Path | None = None) -> dict:
    """Read every compose file in scope and compare it with the registry.

    `files` is injectable so a test can drive the REAL scan over a synthetic
    tree. A test that re-types the rule's expression proves nothing; this
    way the test drives the same code path the CLI does.
    """
    if files is None:
        files = compose_files(root)
    if not files:
        raise InstrumentError("no compose files in scope -- nothing to measure")

    bare: list[dict] = []
    drift: list[dict] = []
    unknown: list[dict] = []
    errors: list[dict] = []
    anchors_only: list[str] = []
    published: list[dict] = []
    registry_slots_used: set[tuple[str, str]] = set()

    for path in files:
        try:
            rel = path.relative_to(PMOVES_DIR).as_posix()
        except ValueError:
            # The file list is INJECTABLE, so a file need not live under this
            # repo's `pmoves/` directory. Falling back to the path as given
            # keeps the label honest instead of raising -- a scan that
            # crashes on its own input cannot report anything.
            rel = path.as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append({"file": rel, "error": f"unreadable: {exc}"})
            continue
        try:
            data = yaml.load(text, Loader=ComposeLoader)
        except Exception as exc:
            errors.append({"file": rel, "error": f"cannot parse: {exc}"})
            continue
        if not isinstance(data, dict):
            errors.append({"file": rel, "error": "not a mapping"})
            continue
        services = data.get("services")
        if services is None:
            # A compose file with NO `services:` key declares no services.
            # MEASURED: `pmoves/docker-compose.base.yml` is exactly that --
            # the shared anchors / volumes / networks base that every
            # overlay merges into. It publishes ZERO host ports, which is a
            # MEASURED fact about the file, not an instrument failure.
            #
            # The distinction matters for the fail-closed rule: a file that
            # cannot be READ or PARSED is still an error (above), and a
            # `services:` key that is not a mapping is still an error
            # (below). Only "parsed, is a mapping, has no `services` key"
            # is a file that legitimately declares nothing.
            anchors_only.append(rel)
            continue
        if not isinstance(services, dict):
            errors.append({"file": rel, "error": "services is not a mapping"})
            continue

        for svc, spec in services.items():
            if not isinstance(spec, dict):
                continue
            raw_entries = spec.get("ports")
            if raw_entries is None:
                entries: list = []
            elif isinstance(raw_entries, list):
                entries = raw_entries
            else:
                # FAIL CLOSED at ENTRY granularity: a `ports:` this
                # instrument cannot read is reported, not walked past.
                errors.append(
                    {
                        "file": rel,
                        "error": (
                            f"service {svc}: `ports` is not a list "
                            f"(got {type(raw_entries).__name__}) -- this instrument "
                            "cannot measure it"
                        ),
                    }
                )
                continue
            for entry in entries:
                if not isinstance(entry, str):
                    # FAIL CLOSED at ENTRY granularity. The compose
                    # LONG-SYNTAX mapping form (`published:`/`target:`) is a
                    # legitimate Docker Compose feature -- it is NOT malformed
                    # -- but this instrument measures only the short string
                    # form, so the entry is REPORTED as unmeasured rather than
                    # silently skipped.
                    errors.append(
                        {
                            "file": rel,
                            "error": (
                                f"service {svc}: port entry is not a string "
                                f"(got {type(entry).__name__}) -- this instrument "
                                "measures only the short string form of a compose "
                                "port entry; the compose LONG-SYNTAX mapping form "
                                "(`published:`/`target:`) is a legitimate Docker "
                                "Compose feature that this instrument does not yet "
                                "measure, so the entry is REPORTED rather than "
                                "skipped"
                            ),
                        }
                    )
                    continue
                m = PORT_LINE.match(entry)
                if not m:
                    continue
                body = m.group("body").strip().strip('"').strip("'")
                slots = split_top_level(body)
                if len(slots) >= 3:
                    host_slot = slots[1]
                elif len(slots) == 2:
                    host_slot = slots[0]
                else:
                    # One slot: container port only. Docker assigns the host
                    # port dynamically. Nothing to check.
                    continue
                value, var, is_bare = resolve_host_slot(host_slot)
                cont_slot = slots[2] if len(slots) >= 3 else slots[1]
                cont_value = None
                cm = VAR_DEFAULT.search(cont_slot.strip().strip('"').strip("'"))
                if cm:
                    if cm.group(2).strip().isdigit():
                        cont_value = int(cm.group(2).strip())
                elif cont_slot.strip().strip('"').strip("'").isdigit():
                    cont_value = int(cont_slot.strip().strip('"').strip("'"))

                if is_bare:
                    bare.append(
                        {
                            "file": rel,
                            "service": svc,
                            "host_port": value,
                            "entry": entry,
                        }
                    )
                    continue

                reg = registry.get(svc)
                if reg is None:
                    unknown.append(
                        {"file": rel, "service": svc, "entry": entry, "reason": "service not in registry"}
                    )
                    continue
                slots_map = reg.get("slots") or {}
                slot = slots_map.get(var) if var else None
                if slot is None:
                    unknown.append(
                        {
                            "file": rel,
                            "service": svc,
                            "entry": entry,
                            "reason": f"no registry slot for port_var {var!r}",
                        }
                    )
                    continue
                registry_slots_used.add((svc, var))
                if value is not None and slot.get("host_port") is not None:
                    if value != slot.get("host_port"):
                        drift.append(
                            {
                                "file": rel,
                                "service": svc,
                                "port_var": var,
                                "compose": value,
                                "registry": slot.get("host_port"),
                                "entry": entry,
                            }
                        )
                if cont_value is not None and slot.get("container_port") is not None:
                    if cont_value != slot.get("container_port"):
                        drift.append(
                            {
                                "file": rel,
                                "service": svc,
                                "port_var": var,
                                "compose_container": cont_value,
                                "registry_container": slot.get("container_port"),
                                "entry": entry,
                            }
                        )
                published.append(
                    {
                        "file": rel,
                        "service": svc,
                        "port_var": var,
                        "host_port": value,
                        "container_port": cont_value,
                    }
                )

    orphans: list[dict] = []
    for svc, entry in registry.items():
        slots_map = entry.get("slots") or {}
        for var, slot in slots_map.items():
            if not slot.get("compose_files"):
                continue
            if (svc, var) not in registry_slots_used:
                orphans.append(
                    {
                        "service": svc,
                        "port_var": var,
                        "reason": "registry slot is published by no compose file in scope",
                    }
                )

    return {
        "files": files,
        "bare": bare,
        "drift": drift,
        "unknown": unknown,
        "orphans": orphans,
        "errors": errors,
        "anchors_only": anchors_only,
        "published": published,
        "registry_slots_used": registry_slots_used,
    }


def find_collisions(published: list[dict]) -> dict:
    """Group published slots by host port, within and across compose files."""
    by_port: dict = {}
    for rec in published:
        port = rec["host_port"]
        if not port:
            continue
        by_port.setdefault(port, []).append(rec)
    collisions: dict = {}
    for port, recs in by_port.items():
        services = sorted({r["service"] for r in recs})
        files = sorted({r["file"] for r in recs})
        collisions[port] = {"services": services, "files": files, "count": len(services)}
    return collisions


def load_python_registries(root: Path | None = None) -> dict:
    """The two Python port registries, read the way the fleet reads them.

    ``pmoves/tests/utils/service_catalog.py`` (the 45-service catalog, imported
    by 11 files) and ``pmoves/scripts/port_allocator.py::DEFAULT_PORTS`` (the
    40-service allocator). They are NOT regenerated from the registry -- the
    house pattern for a hand-maintained list is ONE list plus a ratchet that
    cross-checks it, not a codegen step whose output can itself drift. This
    gate is that cross-check.

    A registry file that is ABSENT means the tree has no such registry to
    cross-check -- nothing to check, so nothing is claimed. A registry file
    that is PRESENT but cannot be read is an INSTRUMENT ERROR: the gate's
    own probe gagged, and a gate that cannot measure fails closed. The real
    tree has both files, and `test_the_real_tree_has_both_python_registries`
    keeps it that way.
    """
    base = (root or REPO_ROOT) / "pmoves"
    out: dict = {"service_catalog": {}, "port_allocator": {}}

    catalog_path = base / "tests" / "utils" / "service_catalog.py"
    if catalog_path.is_file():
        sys.path.insert(0, str(base / "tests"))
        try:
            from utils.service_catalog import SERVICES  # type: ignore

            out["service_catalog"] = {s.name: s.port for s in SERVICES}
        except Exception as exc:
            raise InstrumentError(f"cannot import service_catalog: {exc}") from exc
        finally:
            sys.path.pop(0)

    allocator_path = base / "scripts" / "port_allocator.py"
    if allocator_path.is_file():
        src = allocator_path.read_text(encoding="utf-8")
        ns: dict = {}
        try:
            exec(compile(src, "port_allocator.py", "exec"), ns)
            out["port_allocator"] = dict(ns["DEFAULT_PORTS"])
        except Exception as exc:
            raise InstrumentError(f"cannot load port_allocator DEFAULT_PORTS: {exc}") from exc
    return out


def check_python_registries(registry: dict, py: dict) -> list[dict]:
    """Each Python registry's port must exist as a slot in the canonical registry.

    THE SEMANTIC DISTINCTION, MEASURED: the two Python registries record the
    port a client uses to reach the service. For most services that is the
    CONTAINER port, but it is NOT always: compose publishes a HOST port,
    which is a different number for most services (``pmoves-ui`` listens on
    3000 and is published on 4482; ``supabase-db`` listens on 5432 and is
    published on 54322), and a service the canonical registry records with
    BOTH a container port and a host port is sometimes listed in a Python
    registry under its published HOST port.

    ENFORCED RULE: a Python registry port matches when it equals the
    CONTAINER port or the HOST port of any slot of that service. A drift is
    reported only when it matches NEITHER.

    WHY NOT THE STRICTER RULE: an earlier version of this docstring promised
    that the host port counted only for a service whose slots record no
    container port. MEASURED against the committed tree, the two Python
    registries do not satisfy that rule -- the host-port arm is load-bearing,
    and the strict rule turns the committed tree RED for a shape the
    registries legitimately have. The looser rule above is therefore the
    enforced one, and the measurement lives in the tree rather than in this
    paragraph: `test_the_python_registry_host_port_fallback_is_load_bearing`
    computes it.
    """
    findings: list[dict] = []
    for source, ports in py.items():
        for name, port in sorted(ports.items()):
            if not port:
                continue
            entry = registry.get(name)
            if entry is None:
                findings.append(
                    {
                        "source": source,
                        "service": name,
                        "port": port,
                        "reason": "service is not in the canonical registry",
                    }
                )
                continue
            slots = entry.get("slots") or {}
            container_ports = [s.get("container_port") for s in slots.values()]
            host_ports = [s.get("host_port") for s in slots.values()]
            # ENFORCED RULE -- see the docstring: the CONTAINER port or the
            # HOST port of any slot is a match; only a port that matches
            # neither is a drift.
            if port in container_ports:
                continue
            if port in host_ports:
                continue
            findings.append(
                {
                    "source": source,
                    "service": name,
                    "port": port,
                    "reason": (
                        "no slot in the canonical registry carries this port; "
                        f"registry container ports {sorted(p for p in container_ports if p)}, "
                        f"host ports {sorted(p for p in host_ports if p)}"
                    ),
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--collisions", type=Path, default=COLLISIONS)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repo root the compose scope and the Python registries resolve against",
    )
    parser.add_argument("--write-collisions", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        registry = load_registry(args.registry)
        result = scan(registry, root=args.repo_root)
        known = load_collisions(args.collisions)
        py = load_python_registries(args.repo_root)
        py_findings = check_python_registries(registry, py)
    except InstrumentError as exc:
        print(f"port-registry-ratchet: INSTRUMENT ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive, but must fail closed
        print(f"port-registry-ratchet: INSTRUMENT ERROR: {exc}", file=sys.stderr)
        return 2

    collisions = find_collisions(result["published"])

    if args.write_collisions:
        if not args.yes:
            print("error: --write-collisions rewrites the baseline; pass --yes", file=sys.stderr)
            return 2
        # ONLY the host ports TWO OR MORE services claim. A port claimed by
        # ONE service is not a collision: baselining it would make the very
        # next `--check` report the entry STALE (the port is not shared) and
        # turn the gate red -- the writer manufacturing the failure it was
        # written to prevent.
        shared = {
            port: info for port, info in collisions.items() if info["count"] > 1
        }
        body = {
            "known_collisions": {
                str(port): {
                    "services": info["services"],
                    "files": info["files"],
                    "reason": PLACEHOLDER_REASON,
                }
                for port, info in sorted(shared.items())
            }
        }
        header = (
            "# pmoves/configs/port_registry/_known_collisions.yaml\n"
            "#\n"
            "# Pre-existing duplicate host ports -- the host ports that TWO OR\n"
            "# MORE services claim. Each entry names the services that claim\n"
            "# the port and WHY they may share it. A NEW collision -- one not\n"
            "# listed here -- FAILS the gate, so this baseline cannot grow.\n"
            "#\n"
            "# Every entry needs a real reason. The writer emits the\n"
            "# PLACEHOLDER reason\n"
            "#\n"
            "#     REVIEW THIS -- a pre-existing duplicate host port\n"
            "#\n"
            "# and the gate reports EVERY entry that still carries it as\n"
            "# UNREVIEWED. So a freshly written baseline FAILS the gate until\n"
            "# a human replaces each reason with why these two services may\n"
            "# share the port. The placeholder is a to-do, NOT a review: the\n"
            "# ratchet does not accept it.\n"
        )
        args.collisions.parent.mkdir(parents=True, exist_ok=True)
        args.collisions.write_text(
            header + yaml.safe_dump(body, sort_keys=True, default_flow_style=False, width=110),
            encoding="utf-8",
        )
        print(
            f"port-registry-ratchet: baseline written: {args.collisions} "
            f"({len(shared)} entr(ies)) -- every reason is the PLACEHOLDER, so the "
            f"gate reports them UNREVIEWED until a human replaces each one"
        )
        return 0

    new_collisions = {
        port: info
        for port, info in collisions.items()
        if info["count"] > 1 and str(port) not in known
    }
    stale_collisions = []
    unreviewed_collisions = []
    for port, entry in known.items():
        info = collisions.get(int(port))
        if info is None or info["count"] <= 1:
            # The port is no longer claimed by two services -- the defect
            # the entry described is gone, and leaving it in the baseline
            # would let it come back unnoticed.
            stale_collisions.append(port)
            continue
        # The baseline names the claimants. If the claimant set CHANGED,
        # the reason on file was written about a DIFFERENT set of services
        # -- so the baseline is stale even though the port is still shared.
        recorded = entry.get("services")
        if isinstance(recorded, list) and sorted(str(s) for s in recorded) != info["services"]:
            stale_collisions.append(port)
            continue
        # A reason that says nothing is a claim nobody checked. The
        # baseline writer emits the literal placeholder; accepting it
        # would let the baseline grow without anybody ever reading why
        # the two services may share the port.
        reason = str(entry.get("reason") or "").strip()
        if not reason or reason.upper().startswith(REVIEW_PLACEHOLDER_PREFIX):
            unreviewed_collisions.append(port)

    payload = {
        "files_scanned": len(result["files"]),
        "slots_published": len(result["published"]),
        "bare_literals": result["bare"],
        "registry_drift": result["drift"],
        "unknown_slots": result["unknown"],
        "orphan_slots": result["orphans"],
        "problems": result["errors"],
        "new_collisions": new_collisions,
        "stale_collisions": stale_collisions,
        "unreviewed_collisions": unreviewed_collisions,
        "python_registry_drift": py_findings,
        "out_of_scope_compose_files": out_of_scope_count(args.repo_root),
        "anchors_only_compose_files": result["anchors_only"],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print("port-registry-ratchet: every published host port comes from the registry")
        print(f"  compose files in scope : {payload['files_scanned']}")
        print(f"  published port slots    : {payload['slots_published']}")
        print(f"  out-of-scope compose   : {payload['out_of_scope_compose_files']} file(s) not in scope")
        if payload["anchors_only_compose_files"]:
            print(
                f"  anchors-only compose   : {len(payload['anchors_only_compose_files'])} file(s) "
                f"declare no services and publish no host port "
                f"({', '.join(payload['anchors_only_compose_files'])})"
            )
        if payload["bare_literals"]:
            print(f"  {len(payload['bare_literals'])} BARE-LITERAL host port(s) -- the gate FAILS:")
            for item in payload["bare_literals"]:
                print(f"    - {item['file']}:{item['service']} -> {item['entry']}")
        if payload["registry_drift"]:
            print(f"  {len(payload['registry_drift'])} REGISTRY DRIFT(s) -- the gate FAILS:")
            for item in payload["registry_drift"]:
                print(f"    - {item['file']}:{item['service']}/{item.get('port_var')}: {item}")
        if payload["unknown_slots"]:
            print(f"  {len(payload['unknown_slots'])} UNKNOWN SLOT(s) -- the gate FAILS:")
            for item in payload["unknown_slots"]:
                print(f"    - {item['file']}:{item['service']}: {item['reason']}")
        if payload["orphan_slots"]:
            print(f"  {len(payload['orphan_slots'])} ORPHAN SLOT(s) -- the gate FAILS:")
            for item in payload["orphan_slots"]:
                print(f"    - {item['service']}/{item['port_var']}: {item['reason']}")
        if new_collisions:
            print(f"  {len(new_collisions)} NEW COLLISION(s) -- the gate FAILS:")
            for port, info in sorted(new_collisions.items(), key=lambda kv: int(kv[0])):
                print(f"    - host {port}: {info['services']} in {info['files']}")
        if stale_collisions:
            print(f"  {len(stale_collisions)} STALE collision entr(ies) -- the gate FAILS:")
            for port in stale_collisions:
                print(f"    - host {port}: no longer a collision, or the claimants changed -- drop the baseline entry")
        if unreviewed_collisions:
            print(
                f"  {len(unreviewed_collisions)} UNREVIEWED collision entr(ies) -- the gate FAILS:"
            )
            for port in unreviewed_collisions:
                print(
                    f"    - host {port}: the baseline entry has no real reason (placeholder or empty) "
                    f"-- write why these two services may share the port"
                )
        if payload["python_registry_drift"]:
            print(f"  {len(payload['python_registry_drift'])} PYTHON REGISTRY DRIFT(s) -- the gate FAILS:")
            for item in payload["python_registry_drift"]:
                print(
                    f"    - {item['source']}: {item['service']} claims {item['port']}: {item['reason']}"
                )
        if payload["problems"]:
            print(f"  {len(payload['problems'])} INSTRUMENT ERROR(S) -- the gate FAILS:")
            for item in payload["problems"]:
                print(f"    - {item['file']}: {item['error']}")

    return (
        1
        if (
            payload["bare_literals"]
            or payload["registry_drift"]
            or payload["unknown_slots"]
            or payload["orphan_slots"]
            or payload["problems"]
            or payload["python_registry_drift"]
            or new_collisions
            or stale_collisions
            or unreviewed_collisions
        )
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
