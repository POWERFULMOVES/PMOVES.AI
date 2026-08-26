"""The crush-configurator TS guard: no silent literal hostnames.

Pair-review finding on PR #2769 (2026-08-26): `crush_configurator` emits
``http://${TS_Z890}:8105/mcp/sse`` for ``pmoves-cipher``. On a node where
``TS_Z890`` cannot be resolved (no env value, no tailscale CLI), Crush receives
the literal string as a hostname and 404s silently -- the exact bug class PR
#2769's normalizer kills for Claude's roster, alive one launcher over, in the
harness whose cipher fix (#2762) had just deliberately dropped ``required_env``
for the *token*. This is the narrower hostname gate that replaces it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATOR = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"


def _module():
    spec = importlib.util.spec_from_file_location("crush_configurator", CONFIGURATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["crush_configurator"] = module
    spec.loader.exec_module(module)
    return module


cc = _module()


def _roster(ts_set):
    env = {"TS_Z890": "100.64.0.1"} if ts_set else {}
    cfg = {
        "pmoves-cipher": {
            "type": "sse",
            "url": "http://${TS_Z890}:8105/mcp/sse",
        },
        "pmoves-cipher-local": {
            "type": "sse",
            "url": "http://localhost:8105/mcp/sse",
        },
    }
    return cfg, env


def test_unresolvable_ts_disables_the_spec_with_a_named_reason(capsys, monkeypatch, tmp_path):
    # Isolate from the host: on a node WITH the tailscale CLI, the real helper
    # legitimately resolves TS_Z890 and the spec SHOULD stay enabled. Point the
    # helper at a nonexistent path to exercise the truly-unresolvable path.
    monkeypatch.setattr(cc, "TS_HELPER", tmp_path / "absent-helper.sh")
    cfg, env = _roster(ts_set=False)
    notes = cc.guard_unresolvable_ts(cfg, env=env)
    assert cfg["pmoves-cipher"].get("disabled") is True, (
        "the literal-${TS_Z890} hostname ships enabled — the silent-404 one "
        "launcher over that #2769 exists to kill"
    )
    assert any("TS_Z890" in n and "pmoves-cipher" in n for n in notes), notes
    err = capsys.readouterr().err
    assert "pmoves-cipher" in err and "TS_Z890" in err


def test_resolved_ts_keeps_the_spec_enabled():
    cfg, env = _roster(ts_set=True)
    cc.guard_unresolvable_ts(cfg, env=env)
    assert not cfg["pmoves-cipher"].get("disabled")


def test_local_urls_are_never_touched_by_the_ts_gate():
    """localhost carries no ${TS_*}: the gate must be a no-op for it."""
    cfg, env = _roster(ts_set=False)
    notes = cc.guard_unresolvable_ts(cfg, env=env)
    assert not cfg["pmoves-cipher-local"].get("disabled")
    assert not any("local" in n for n in notes), notes


def test_already_disabled_specs_are_not_rereported():
    cfg, env = _roster(ts_set=False)
    cfg["pmoves-cipher"]["disabled"] = True
    notes = cc.guard_unresolvable_ts(cfg, env=env)
    assert not any("pmoves-cipher:" in n for n in notes), notes


def test_the_helper_fallback_is_attempted_not_assumed(monkeypatch, tmp_path):
    """Env-missing but helper-resolvable must still enable the spec: the helper
    is the ONE shared definition (sourced by both launchers), so the guard has
    to consult it rather than trusting os.environ alone."""
    cfg, _ = _roster(ts_set=False)
    fake = tmp_path / "helper.sh"
    fake.write_text("#!/usr/bin/env bash\nexport TS_Z890=100.64.0.9\n")
    monkeypatch.setattr(cc, "TS_HELPER", fake)
    notes = cc.guard_unresolvable_ts(cfg, env={})
    assert not cfg["pmoves-cipher"].get("disabled"), notes
