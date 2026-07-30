"""Tests for services/common/topology.py network-awareness.

Imports topology.py by file path (service-root importlib convention) so the test
runs regardless of PYTHONPATH.
"""
import importlib.util
import pathlib

import pytest

_COMMON = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pmoves_topology_under_test", _COMMON / "topology.py")
topology = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(topology)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in (
        "PMOVES_NETWORKS", "TAILSCALE_SERVE_URL", "TS_NODE", "TAILNET", "TS_TAGS",
        "PINOKIO_ENDPOINTS", "TOPOLOGY_MODE", "DOCKED_MODE", "SUPABASE_RUNTIME",
    ):
        monkeypatch.delenv(k, raising=False)
    topology.reset_topology()
    yield
    topology.reset_topology()


def test_backward_compat_defaults():
    # Existing callers construct with just a mode — new fields must default cleanly.
    ctx = topology.TopologyContext(mode=topology.TopologyMode.DOCKED)
    assert ctx.docker_networks == frozenset()
    assert ctx.tailscale is None
    assert ctx.pinokio_endpoints == {}
    d = ctx.to_dict()
    assert d["external_egress"] is False
    assert d["tailscale"] == {"exposed": False}
    assert d["docker_networks"] == []


def test_docker_networks_and_egress(monkeypatch):
    monkeypatch.setenv("PMOVES_NETWORKS", "pmoves_app, pmoves_bus ,pmoves_external")
    ctx = topology.TopologyContext.from_env()
    assert ctx.on_network("pmoves_bus")
    assert not ctx.on_network("pmoves_data")
    assert ctx.has_external_egress()
    assert set(ctx.to_dict()["docker_networks"]) == {"pmoves_app", "pmoves_bus", "pmoves_external"}


def test_internal_only_has_no_egress(monkeypatch):
    monkeypatch.setenv("PMOVES_NETWORKS", "pmoves_app,pmoves_bus")
    ctx = topology.TopologyContext.from_env()
    assert not ctx.has_external_egress()


def test_tailscale_exposed_requires_serve_url(monkeypatch):
    # On the tailnet (node/tailnet known) but NOT serving this service -> not exposed.
    monkeypatch.setenv("TS_NODE", "pmoves-4090")
    monkeypatch.setenv("TAILNET", "example.ts.net")
    ctx = topology.TopologyContext.from_env()
    assert ctx.tailscale is not None
    assert not ctx.is_tailnet_exposed()
    # With a Serve URL -> exposed.
    topology.reset_topology()
    monkeypatch.setenv("TAILSCALE_SERVE_URL", "https://pmoves-4090.example.ts.net")
    ctx2 = topology.TopologyContext.from_env()
    assert ctx2.is_tailnet_exposed()
    assert ctx2.to_dict()["tailscale"]["serve_url"].endswith(".ts.net")


def test_pinokio_endpoints(monkeypatch):
    monkeypatch.setenv("PINOKIO_ENDPOINTS", '{"ultimate-tts":"http://host.docker.internal:7860"}')
    ctx = topology.TopologyContext.from_env()
    assert ctx.pinokio_url("ultimate-tts") == "http://host.docker.internal:7860"
    assert ctx.pinokio_url("missing") is None


def test_pinokio_invalid_json_is_empty(monkeypatch):
    monkeypatch.setenv("PINOKIO_ENDPOINTS", "not-json")
    ctx = topology.TopologyContext.from_env()
    assert ctx.pinokio_endpoints == {}
