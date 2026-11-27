"""The node's bind overlay (env.mesh-bind.local) must be the LAST compose env file.

Node-branded bind defaults: compose source defaults *_BIND to loopback, and a
node opts in to wider binds through its own gitignored env.mesh-bind.local.
That only works if the overlay is appended AFTER env.shared and every
env.tier-* file -- compose lets a later --env-file override an earlier one, so
an overlay loaded earlier would be silently overridden by the tiers.

This is a static check over the Makefile text on purpose: evaluating the
Makefile with a real env.mesh-bind.local would mean creating that file inside
the checkout, which would clobber a node's real overlay.
"""

from __future__ import annotations

import re
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[2]
MAKEFILE = PMOVES / "Makefile"
INFRA_MK = PMOVES / "mk" / "infra.mk"
OVERLAY = "env.mesh-bind.local"

APPEND = re.compile(r"^\s*COMPOSE_ENV_FILES\s*\+=\s*(.*)$")


def _appends() -> list[tuple[int, str]]:
    out = []
    for lineno, line in enumerate(MAKEFILE.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        m = APPEND.match(line)
        if m:
            out.append((lineno, m.group(1).strip()))
    return out


def test_overlay_is_appended_to_compose_env_files() -> None:
    appends = _appends()
    assert appends, "no COMPOSE_ENV_FILES += lines found -- Makefile layout changed"
    hits = [value for _, value in appends if OVERLAY in value]
    assert hits == [f"--env-file {OVERLAY}"], (
        f"{OVERLAY} must be appended exactly once as `--env-file {OVERLAY}`; "
        f"found {hits!r} among {len(appends)} appends"
    )


def test_overlay_is_the_last_env_file_appended() -> None:
    appends = _appends()
    last_lineno, last_value = appends[-1]
    assert OVERLAY in last_value, (
        f"the last COMPOSE_ENV_FILES append (Makefile:{last_lineno}) is "
        f"{last_value!r}; {OVERLAY} must come last so the node's bind decision "
        f"overrides the tier files ({len(appends)} appends inspected)"
    )


def test_overlay_append_is_guarded_by_existence() -> None:
    """A node with no overlay must not get a missing --env-file (compose errors)."""
    text = MAKEFILE.read_text(encoding="utf-8")
    assert f'ifneq ("$(wildcard {OVERLAY})","")' in text


def test_port_audit_resolves_through_dc_not_bare_compose() -> None:
    """port-audit must see the same env files as `up`, so it pipes $(DC) config."""
    text = INFRA_MK.read_text(encoding="utf-8")
    m = re.search(r"^port-audit:.*?(?=^\S)", text, re.S | re.M)
    assert m, "port-audit target not found in mk/infra.mk"
    recipe = "\n".join(
        ln for ln in m.group(0).splitlines() if not ln.strip().startswith("@#")
    )
    assert "$(DC) config --format json" in recipe
    assert "--config-json -" in recipe
    assert "@docker compose config" not in recipe, "bare compose reads no env files"
