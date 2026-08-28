"""The injector must not eat comments belonging to neighbouring keys.

ruamel attaches a comment to the index of the item it FOLLOWS. So deleting an
entry destroys the comment on the next line -- which usually documents a
DIFFERENT key. The original implementation deleted every PMOVES_NETWORKS= match
and re-appended at the end, which silently removed this from
docker-compose.yml on every run:

    - PMOVES_NETWORKS=pmoves_api,pmoves_public
    # Admin server backs `postgrest --ready` (healthcheck below). ...
    - PGRST_ADMIN_SERVER_PORT=...

That loss was not optional. The drift gate requires the injector's output to
match what is committed, so `main` sat permanently one run away from dirty and
the only way to green the gate was to commit the deletion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

yaml_mod = pytest.importorskip("ruamel.yaml")

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import inject_pmoves_networks as inj  # noqa: E402


def _roundtrip(text: str):
    y = yaml_mod.YAML()
    y.preserve_quotes = True
    return y, y.load(text)


def _dump(y, data) -> str:
    import io
    buf = io.StringIO()
    y.dump(data, buf)
    return buf.getvalue()


SAMPLE = """\
services:
  demo:
    environment:
    - FIRST=1
    - PMOVES_NETWORKS=old_value
    # This comment documents the NEXT key, not the one above it.
    - SECOND=2
"""


def test_comment_on_the_following_line_survives():
    y, data = _roundtrip(SAMPLE)
    env = data["services"]["demo"]["environment"]
    inj._inject_into_env(env, "a,b")
    out = _dump(y, data)
    assert "This comment documents the NEXT key" in out, (
        "the injector ate a comment belonging to the following key:\n" + out
    )
    assert "PMOVES_NETWORKS=a,b" in out
    assert "PMOVES_NETWORKS=old_value" not in out


def test_entry_keeps_its_position():
    """Replacing in place, not delete-and-append. Position matters only because
    moving the entry is what detaches the comment."""
    y, data = _roundtrip(SAMPLE)
    env = data["services"]["demo"]["environment"]
    inj._inject_into_env(env, "a,b")
    keys = [str(e).split("=", 1)[0] for e in env]
    assert keys == ["FIRST", "PMOVES_NETWORKS", "SECOND"], keys


def test_appends_when_absent():
    y, data = _roundtrip("services:\n  demo:\n    environment:\n    - ONLY=1\n")
    env = data["services"]["demo"]["environment"]
    inj._inject_into_env(env, "x")
    assert [str(e) for e in env] == ["ONLY=1", "PMOVES_NETWORKS=x"]


def test_is_idempotent():
    y, data = _roundtrip(SAMPLE)
    env = data["services"]["demo"]["environment"]
    inj._inject_into_env(env, "a,b")
    once = _dump(y, data)
    inj._inject_into_env(env, "a,b")
    assert _dump(y, data) == once, "second run changed the output"


def test_duplicates_collapse_to_one():
    y, data = _roundtrip(
        "services:\n  demo:\n    environment:\n"
        "    - PMOVES_NETWORKS=a\n    - MID=1\n    - PMOVES_NETWORKS=b\n"
    )
    env = data["services"]["demo"]["environment"]
    inj._inject_into_env(env, "final")
    vals = [str(e) for e in env if str(e).startswith("PMOVES_NETWORKS=")]
    assert vals == ["PMOVES_NETWORKS=final"], vals
