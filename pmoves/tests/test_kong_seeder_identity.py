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


# --- the selected credential must survive into the plan (review on #2825) -----
#
# `_parse_model_suits` picks the token-plan key over the pay-as-you-go one, but
# `_generate_plan` used to drop it: the identity snapshot said
# MINIMAX_TOKEN_PLAN_API_KEY while the plan -- the thing that actually reaches
# Kong -- carried no opinion at all. Nothing downstream could tell the two
# apart, which is how a selection becomes unauditable.


def test_the_plan_carries_the_selected_key():
    seeder = _seeder()
    groups = {"minimax": [
        {"model_id": "MiniMax-M3", "api_base": "https://x/v1",
         "api_key_env": "MINIMAX_TOKEN_PLAN_API_KEY"},
    ]}
    plan = seeder._generate_plan(groups)
    svc = plan["services"][0]
    assert svc["api_key_env"] == "MINIMAX_TOKEN_PLAN_API_KEY"
    assert svc["api_key_envs"] == ["MINIMAX_TOKEN_PLAN_API_KEY"]


def test_conflicting_keys_in_one_service_are_not_collapsed():
    """A service groups several models. If they disagree on the credential,
    picking one silently would bill some of them on a key nobody chose."""
    seeder = _seeder()
    groups = {"minimax": [
        {"model_id": "a", "api_base": "https://x/v1", "api_key_env": "PLAN_KEY"},
        {"model_id": "b", "api_base": "https://x/v1", "api_key_env": "PAYG_KEY"},
    ]}
    svc = seeder._generate_plan(groups)["services"][0]
    assert svc["api_key_env"] is None, "an ambiguous choice must not be made silently"
    assert svc["api_key_envs"] == ["PAYG_KEY", "PLAN_KEY"]


def test_execution_says_kong_auth_is_not_configured(caplog):
    """The seeder upserts services and routes and configures NO auth plugin, so
    whichever key the gateway already holds is the key that bills. A run that
    reports "routes created" otherwise reads as "routes use the token plan"."""
    import logging
    seeder = _seeder()
    plan = {
        "services": [{"name": "pmoves-minimax", "url": "https://x/v1",
                      "api_key_env": "MINIMAX_TOKEN_PLAN_API_KEY",
                      "api_key_envs": ["MINIMAX_TOKEN_PLAN_API_KEY"]}],
        "routes": [],
    }

    class _Client:
        def upsert_service(self, *a, **k):
            return True

    with caplog.at_level(logging.WARNING):
        seeder._execute_plan(_Client(), plan, dry_run=False)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "auth is NOT configured" in joined
    assert "MINIMAX_TOKEN_PLAN_API_KEY" in joined
