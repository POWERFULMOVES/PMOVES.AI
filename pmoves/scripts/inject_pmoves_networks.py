#!/usr/bin/env python3
"""Mirror each service's ``networks:`` list into ``PMOVES_NETWORKS=`` in its own
``environment:`` block of ``pmoves/docker-compose.yml`` (the canonical SOURCE).

Why: ``pmoves/services/common/topology.py`` (``TopologyContext.from_env()``, added
by #2183) reads ``PMOVES_NETWORKS`` (comma-separated) to populate
``docker_networks``, which backs ``on_network()`` and ``has_external_egress()``.
Nothing sets ``PMOVES_NETWORKS`` today, so every deployed service sees
``docker_networks == frozenset()`` and ``has_external_egress()`` is always False.
This closes that wiring gap (PR #2188 design plan).

The SOURCE file is mutated (not just the generated overlays) because the default
``make -C pmoves up`` path reads ``docker-compose.yml`` directly while the
``overlay-up-*`` path reads the ``split_compose.py`` overlays regenerated FROM it;
both must agree, and ``compose-split-check`` requires the overlays to be a
byte-identical regeneration of source. After running this, run
``make -C pmoves compose-split`` to regenerate the overlays.

Idempotent: re-running replaces (never duplicates) each service's
``PMOVES_NETWORKS=`` entry, so it is safe to re-run whenever a service's
``networks:`` block changes — same convention as ``split_compose.py``.

Usage:
    # rewrite in place
    uv run --no-project --with ruamel.yaml==0.19.1 python scripts/inject_pmoves_networks.py
    # check-only (exit 1 if the file would change — for the drift gate)
    uv run --no-project --with ruamel.yaml==0.19.1 python scripts/inject_pmoves_networks.py --check
"""
from __future__ import annotations

import argparse
import io
import pathlib
import sys

from ruamel.yaml import YAML

_PMOVES_DIR = pathlib.Path(__file__).resolve().parents[1]  # scripts/ -> pmoves/
_SOURCE_COMPOSE = _PMOVES_DIR / "docker-compose.yml"

_ENV_KEY = "PMOVES_NETWORKS"


def _network_names(networks) -> list[str]:
    """Extract ordered network names from a service ``networks:`` value.

    Handles both the list form (``[a, b]`` / block list) and the mapping form
    (``{a: {aliases: [...]}, b: null}``). Preserves declared order.
    """
    if networks is None:
        return []
    if isinstance(networks, dict):
        return [str(k) for k in networks.keys()]
    if isinstance(networks, (list, tuple)):
        return [str(n) for n in networks]
    return []


def _inject_into_env(env, value: str):
    """Return the service's environment with a single ``PMOVES_NETWORKS=`` entry.

    Works on the two shapes used in this compose file:
      * list form  -> ``["KEY=val", ...]``  (append/replace ``PMOVES_NETWORKS=<value>``)
      * dict form  -> ``{KEY: val, ...}``    (set ``PMOVES_NETWORKS``)
    Preserves the ruamel container type (and thus comments/formatting) when one
    already exists; creates a plain list when the service has no ``environment:``.
    """
    entry = f"{_ENV_KEY}={value}"
    if env is None:
        return [entry]
    if isinstance(env, dict):
        env[_ENV_KEY] = value
        return env
    if isinstance(env, list):
        # Replace an existing entry IN PLACE; only append when there is none.
        #
        # The previous version deleted every match and re-appended at the end.
        # In ruamel a comment is attached to the index of the item it FOLLOWS,
        # so `del env[i]` destroys the comment on the next line -- which
        # documents a DIFFERENT key. Observed in docker-compose.yml:
        #
        #   - PMOVES_NETWORKS=pmoves_api,pmoves_public
        #   # Admin server backs `postgrest --ready` (healthcheck below). ...
        #   - PGRST_ADMIN_SERVER_PORT=...
        #
        # Re-running the injector silently ate line 2, which belongs to
        # PGRST_ADMIN_SERVER_PORT. Because the drift gate requires the
        # injector's output to match what is committed, that loss was not
        # optional: main was permanently one run away from dirty, and the only
        # way to green the gate was to commit the deletion.
        found = [
            i for i, item in enumerate(env)
            if isinstance(item, str) and item.split("=", 1)[0] == _ENV_KEY
        ]
        if found:
            env[found[0]] = entry          # keeps position AND ca.items[i]
            for i in reversed(found[1:]):  # drop accidental duplicates
                del env[i]
        else:
            env.append(entry)
        return env
    raise TypeError(f"unexpected environment shape: {type(env)!r}")


def _apply(data) -> int:
    """Mutate ``data`` in place. Returns the number of services wired."""
    services = data.get("services") or {}
    wired = 0
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        names = _network_names(svc.get("networks"))
        if not names:
            continue
        value = ",".join(names)
        svc["environment"] = _inject_into_env(svc.get("environment"), value)
        wired += 1
    return wired


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if docker-compose.yml would change (drift gate), write nothing",
    )
    args = ap.parse_args()

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't rewrap long lines (matches split_compose.py intent)

    original = _SOURCE_COMPOSE.read_text(encoding="utf-8")
    data = yaml.load(original)
    wired = _apply(data)

    buf = io.StringIO()
    yaml.dump(data, buf)
    updated = buf.getvalue()

    if args.check:
        if updated != original:
            print(
                "ERROR: PMOVES_NETWORKS wiring out of sync with services' networks: "
                "blocks — run 'uv run --no-project --with ruamel.yaml==0.19.1 python "
                "scripts/inject_pmoves_networks.py' and 'make -C pmoves compose-split', "
                "then commit.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: PMOVES_NETWORKS wiring in sync ({wired} services).")
        return 0

    _SOURCE_COMPOSE.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Wired PMOVES_NETWORKS into {wired} services in {_SOURCE_COMPOSE.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
