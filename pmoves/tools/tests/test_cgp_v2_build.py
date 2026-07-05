# pmoves/tools/tests/test_cgp_v2_build.py
import re
import numpy as np
from pmoves.tools.cgp_v2_build import (
    build_attribution, build_hyperbolic_block, merkle_root,
)

HEX64 = re.compile(r"^0x[a-fA-F0-9]{64}$")


def test_merkle_root_shape_and_determinism():
    leaves = ["track_a", "track_b", "track_c"]
    r1 = merkle_root(leaves)
    r2 = merkle_root(leaves)
    assert HEX64.match(r1) and r1 == r2


def test_merkle_root_order_independent_is_false():
    # order matters (leaves are pre-sorted by caller); different order -> different root
    assert merkle_root(["a", "b"]) != merkle_root(["b", "a"])


def test_build_attribution_weights_sum_to_one():
    attr = build_attribution({"t0": 3.0, "t1": 1.0})
    weights = [c["weight"] for c in attr["contributors"]]
    assert abs(sum(weights) - 1.0) < 1e-9
    assert attr["total_alpha"] == 4.0
    assert HEX64.match(attr["merkle_root"])
    # t0 had 3x the raw contribution -> 0.75 weight
    by_addr = {c["address"]: c for c in attr["contributors"]}
    assert abs(by_addr["t0"]["weight"] - 0.75) < 1e-9


def test_build_attribution_handles_zero_total():
    attr = build_attribution({"t0": 0.0, "t1": 0.0})
    # uniform fallback when all alpha are zero
    weights = sorted(c["weight"] for c in attr["contributors"])
    assert weights == [0.5, 0.5]


def test_build_hyperbolic_block_shape():
    groups = {"g0": np.array([1.0, 0.0])}
    members = {"g0": {"t0": np.array([1.0, 0.1])}}
    block = build_hyperbolic_block(groups, members)
    assert block["space"] == "poincare_disk"
    assert block["curvature"] == -1
    assert block["max_radius"] == 0.95
    assert block["hierarchy_depth"] == 2
    assert all(p["x"] ** 2 + p["y"] ** 2 < 1.0 for p in block["points"])
