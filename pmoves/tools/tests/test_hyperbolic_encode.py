# pmoves/tools/tests/test_hyperbolic_encode.py
import math
import numpy as np
import pytest
from pmoves.tools.hyperbolic_encode import poincare_encode, encode_hierarchy


def test_point_inside_unit_disk():
    p = poincare_encode(angle=0.0, depth=3, max_radius=0.95)
    assert p["x"] ** 2 + p["y"] ** 2 < 1.0
    assert 0.0 <= p["r"] <= 0.95
    assert 0.0 <= p["theta"] < 2 * math.pi


def test_root_is_near_center():
    root = poincare_encode(angle=1.2, depth=0, max_radius=0.95)
    assert root["r"] < 0.5  # depth 0 sits near origin


def test_deeper_is_farther_out():
    shallow = poincare_encode(angle=1.2, depth=1, max_radius=0.95)
    deep = poincare_encode(angle=1.2, depth=4, max_radius=0.95)
    assert deep["r"] > shallow["r"]
    assert deep["r"] < 0.95


def test_angle_from_vector_is_deterministic():
    a = poincare_encode(angle=None, vector=np.array([1.0, 0.0]), depth=2)
    b = poincare_encode(angle=None, vector=np.array([1.0, 0.0]), depth=2)
    assert a == b
    assert a["theta"] == pytest.approx(0.0, abs=1e-9)


def test_encode_hierarchy_links_parents():
    groups = {"g0": np.array([1.0, 0.0]), "g1": np.array([0.0, 1.0])}
    members = {"g0": {"t0": np.array([1.0, 0.1]), "t1": np.array([0.9, -0.1])},
               "g1": {"t2": np.array([0.0, 1.0])}}
    pts = encode_hierarchy(groups, members, max_radius=0.95)
    by_id = {p["id"]: p for p in pts}
    assert by_id["g0"]["depth"] == 1 and "parent_id" not in by_id["g0"]
    assert by_id["t0"]["parent_id"] == "g0" and by_id["t0"]["depth"] == 2
    assert all(p["x"] ** 2 + p["y"] ** 2 < 1.0 for p in pts)
