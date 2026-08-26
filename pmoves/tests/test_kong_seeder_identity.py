"""Kong reads routing identity from the TOP LEVEL of each suit file.

Any schema change that re-parents `name`/`provider`/`base_url`/`api_key_env`
makes every lookup in `_parse_model_suits` miss, so each file yields no model_id,
is skipped, and every model silently drops out of Kong while Kong reports healthy.
This pins the shape so that failure is caught here rather than in production.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"


def _seeder():
    path = REPO_ROOT / "pmoves" / "tools" / "kong_route_seeder.py"
    spec = importlib.util.spec_from_file_location("kong_route_seeder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kong_route_seeder"] = module
    spec.loader.exec_module(module)
    return module


def test_every_suit_file_yields_a_routable_entry():
    seeder = _seeder()
    on_disk = sorted(p.stem for p in SUITS_DIR.glob("*.yaml"))
    parsed = seeder._parse_model_suits(SUITS_DIR)

    assert len(parsed) == len(on_disk), (
        f"{len(on_disk)} suit files on disk but the seeder returned {len(parsed)}. "
        "A dropped entry means that model is absent from Kong."
    )


def test_routing_fields_match_the_committed_snapshot():
    """Presence and count are not enough. A change that re-parents only
    base_url/api_key_env leaves name/provider resolvable through the parser's
    fallback chain, so the entry still appends and the COUNT IS UNCHANGED —
    while Kong silently falls back to _infer_api_base()/_infer_key_env()
    instead of the file's real values. Pin all four fields by value.

    Regenerate only after proving the existing entries are untouched: compare
    old against new and require the changed-and-removed sets to be empty, so a
    genuine re-parenting cannot be absorbed as "just an addition". Done once
    already, when main added the MiniMax-M3 suit (#2712) after this snapshot
    was taken: 18 -> 19, 0 changed, 0 removed.
    """
    seeder = _seeder()
    snapshot_path = Path(__file__).parent / "data" / "kong_route_identity.json"
    with open(snapshot_path, encoding="utf-8") as handle:
        expected = json.load(handle)

    actual = {
        Path(entry["file"]).stem: {
            "model_id": entry.get("model_id"),
            "provider": entry.get("provider"),
            "api_base": entry.get("api_base"),
            "api_key_env": entry.get("api_key_env"),
        }
        for entry in seeder._parse_model_suits(SUITS_DIR)
    }

    assert actual == expected, (
        "Kong routing identity drifted from the committed snapshot. If a suit "
        "legitimately changed one of these four fields, regenerate "
        "pmoves/tests/data/kong_route_identity.json deliberately — do not "
        "loosen this assertion."
    )
