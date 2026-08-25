"""Kong reads routing identity from the TOP LEVEL of each suit file.

Any schema change that re-parents `name`/`provider`/`base_url`/`api_key_env`
makes every lookup in `_parse_model_suits` miss, so each file yields no model_id,
is skipped, and every model silently drops out of Kong while Kong reports healthy.
This pins the shape so that failure is caught here rather than in production.
"""
from __future__ import annotations

import importlib.util
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

    missing_id = [e for e in parsed if not e.get("model_id")]
    assert not missing_id, (
        f"{len(missing_id)} entries have no model_id and would be skipped: "
        f"{[e.get('file') for e in missing_id]}"
    )
