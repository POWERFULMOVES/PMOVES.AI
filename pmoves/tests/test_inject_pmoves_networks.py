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


# ── --check message classification (issue #2996) ───────────────────────
# The gate's assertion is broader than its old message: "file != injector-
# canonical" fires for network drift AND for pure ruamel round-trip noise.
# Same exit code either way; only the sentence must match the measured cause.

FORMAT_DRIFT = """\
services:
  demo:
    networks: [pmoves_api]
    environment:
    - PMOVES_NETWORKS=pmoves_api
    test:
      [
        "CMD",
        "node",
        "-e",
        "fetch('http://localhost:3000/api/platform/profile').then(...)",
      ]
"""


def _load_both(text: str):
    """Load twice: `data` PRE-apply (for _classify, as main() does) and the
    post-apply dump."""
    import io
    y = yaml_mod.YAML()
    y.preserve_quotes = True
    y.width = 4096
    data = y.load(text)          # fresh, un-mutated — classification input
    data2 = y.load(text)
    inj._apply(data2)
    buf = io.StringIO()
    y.dump(data2, buf)
    return data, buf.getvalue()


def test_check_classifies_pure_formatting_drift():
    """Multi-line flow sequence collapsing: values agree, layout doesn't."""
    data, updated = _load_both(FORMAT_DRIFT)
    assert updated != FORMAT_DRIFT  # ruamel re-emits it differently
    assert inj._classify(FORMAT_DRIFT, data) == "formatting"


def test_check_classifies_network_value_drift_as_semantic():
    text = (
        "services:\n  demo:\n    networks: [pmoves_api]\n"
        "    environment:\n    - PMOVES_NETWORKS=stale_wrong\n"
    )
    data, updated = _load_both(text)
    assert inj._classify(text, data) == "semantic"


def test_unified_diff_shows_the_collapsed_healthcheck():
    data, updated = _load_both(FORMAT_DRIFT)
    diff = inj._unified_diff(FORMAT_DRIFT, updated)
    assert "injector-canonical" in diff
    assert "fetch('http://localhost:3000" in diff  # the actual hunk, visible
