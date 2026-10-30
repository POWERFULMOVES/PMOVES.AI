"""invidious_keys_preflight + brand_defaults: usable Invidious keys before compose runs.

Compose interpolates every service, profile or not, so once the compose files
declare ``${INVIDIOUS_*_KEY:?}`` a node without the keys loses every stack goal.
The preflight runs in front of those goals and must (a) fix what it safely can,
(b) never make a node worse than compose alone, (c) never print a value.
Fixture keys are INVENTED.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
REGISTRY = str(PMOVES / "bootstrap" / "registry.json")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


pf = _load("invidious_keys_preflight_under_test", PMOVES / "tools" / "invidious_keys_preflight.py")
bd = _load("brand_defaults_invidious_under_test", PMOVES / "tools" / "brand_defaults.py")
import pmoves.tools._secrets_common as common  # noqa: E402

COMPANION_RE = re.compile(r"[A-Za-z0-9]{16}")
LIVE_COMPANION = "a1b2c3d4e5f60718"
LIVE_HMAC = "f" * 40
PUBLISHED = "0123456789abcdef"


class Probe:
    def __init__(self, containers=None):
        self._c = containers or {}

    def available(self):
        return True

    def container_envs(self):
        return dict(self._c)

    def volumes(self):
        return []


@pytest.fixture(autouse=True)
def _no_shell_exports(monkeypatch):
    for key in pf.KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def published(monkeypatch):
    table = {k: set(v) for k, v in common.KNOWN_PUBLIC_SECRET_DIGESTS.items()}
    table.setdefault(len(PUBLISHED), set()).add(common.known_public_digest(PUBLISHED))
    monkeypatch.setattr(common, "KNOWN_PUBLIC_SECRET_DIGESTS", {k: frozenset(v) for k, v in table.items()})


def _env(tmp_path, text):
    p = tmp_path / ("env." + "shared")
    p.write_text(text, encoding="utf-8")
    return p


def _read(env, key):
    return pf._be.read_env_value(key, env)


def _usable(env):
    values = {k: _read(env, k) for k in pf.KEYS}
    return all(pf.problem(k, values[k], values) is None for k in pf.KEYS)


def test_mints_both_when_absent(tmp_path, capsys):
    env = _env(tmp_path, "OTHER=keep\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert _usable(env)
    assert COMPANION_RE.fullmatch(_read(env, "INVIDIOUS_COMPANION_KEY"))
    assert _read(env, "OTHER") == "keep"
    out = capsys.readouterr().out
    for k in pf.KEYS:
        assert _read(env, k) not in out


def test_recovers_a_live_private_value_instead_of_minting(tmp_path):
    env = _env(tmp_path, "OTHER=keep\n")
    probe = Probe({"pmoves-invidious-1": {"INVIDIOUS_COMPANION_KEY": LIVE_COMPANION}})
    assert pf.run(env, check=False, registry=REGISTRY, probe=probe) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") == LIVE_COMPANION


def test_private_valid_values_are_untouched(tmp_path):
    text = f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n"
    env = _env(tmp_path, text)
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert env.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("bad", ["ab-def_123456789", "short", "a" * 64])
def test_vendor_invalid_companion_is_rotated(tmp_path, bad):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={bad}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert COMPANION_RE.fullmatch(_read(env, "INVIDIOUS_COMPANION_KEY"))
    assert _read(env, "INVIDIOUS_HMAC_KEY") == LIVE_HMAC


def test_published_value_is_rotated(tmp_path, published):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={PUBLISHED}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") != PUBLISHED
    assert _usable(env)


def test_hmac_equal_to_companion_is_rotated(tmp_path):
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_COMPANION}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") == LIVE_COMPANION
    assert _read(env, "INVIDIOUS_HMAC_KEY") != LIVE_COMPANION


def test_absent_env_file_is_not_created(tmp_path):
    """Creating it would stop ensure-env-shared seeding the template."""
    env = tmp_path / ("env." + "shared")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert not env.exists()


def test_check_mode_never_writes(tmp_path):
    env = _env(tmp_path, "OTHER=keep\n")
    assert pf.run(env, check=True, registry=REGISTRY, probe=Probe()) == 1
    assert env.read_text(encoding="utf-8") == "OTHER=keep\n"


def test_empty_shell_export_blocks(tmp_path, monkeypatch):
    """Compose fails ${VAR:?} on an empty export no matter what env files say."""
    monkeypatch.setenv("INVIDIOUS_HMAC_KEY", "")
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 1


def test_non_empty_bad_export_only_warns(tmp_path, monkeypatch, capsys):
    """Compose accepts it; only Invidious is affected, so the stack must not block."""
    monkeypatch.setenv("INVIDIOUS_COMPANION_KEY", "has-dash_1234567")
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={LIVE_HMAC}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    out = capsys.readouterr().out
    assert "WARNING" in out and "has-dash_1234567" not in out


def test_makefile_runs_preflight_before_stack_goals_only():
    text = (PMOVES / "Makefile").read_text(encoding="utf-8")
    goals = text.split("INVIDIOUS_KEYS_PREFLIGHT_GOALS := $(filter ", 1)[1].split(",", 1)[0].split()
    for goal in ("up", "up-%", "down", "down-%", "ps", "overlay-up-full", "overlay-up-ui"):
        assert goal in goals
    for goal in ("secrets-%", "test", "overlay-up-bus", "compose-split-check"):
        assert goal not in goals
    assert "$(INVIDIOUS_KEYS_PREFLIGHT_GOALS): invidious-keys-preflight" in text


# ---------------------------------------------------------------------------
# brand_defaults -- the older road (ensure-env-shared on `make up` & co.)
# ---------------------------------------------------------------------------


def test_brand_defaults_mints_a_companion_key_the_companion_accepts():
    for _ in range(200):  # token_urlsafe used to fail this ~40% of the time
        text = bd._ensure_invidious_keys("INVIDIOUS_COMPANION_KEY=localhack\nINVIDIOUS_HMAC_KEY=localhack\n")
        companion = bd._get_kv(text, "INVIDIOUS_COMPANION_KEY")
        hmac = bd._get_kv(text, "INVIDIOUS_HMAC_KEY")
        assert COMPANION_RE.fullmatch(companion)
        assert len(hmac) >= 32 and hmac != companion


def test_brand_defaults_repairs_a_dashed_key_and_keeps_good_ones():
    text = bd._ensure_invidious_keys(f"INVIDIOUS_COMPANION_KEY=ab-def_123456789\nINVIDIOUS_HMAC_KEY={LIVE_HMAC}\n")
    assert COMPANION_RE.fullmatch(bd._get_kv(text, "INVIDIOUS_COMPANION_KEY"))
    assert bd._get_kv(text, "INVIDIOUS_HMAC_KEY") == LIVE_HMAC
    good = f"INVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\nINVIDIOUS_HMAC_KEY={LIVE_HMAC}\n"
    assert bd._ensure_invidious_keys(good) == good


def test_brand_defaults_rotates_a_published_value(published):
    text = bd._ensure_invidious_keys(f"INVIDIOUS_COMPANION_KEY={PUBLISHED}\nINVIDIOUS_HMAC_KEY={LIVE_HMAC}\n")
    assert bd._get_kv(text, "INVIDIOUS_COMPANION_KEY") != PUBLISHED
