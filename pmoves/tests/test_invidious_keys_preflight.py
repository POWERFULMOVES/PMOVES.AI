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
# One owner. brand_defaults used to mint these with token_urlsafe (~40% of
# companion keys carried '-'/'_' and the companion refused to start), and its
# value then satisfied --ensure, so the registry generator never ran.
# ---------------------------------------------------------------------------


def test_preflight_rejects_placeholders_and_short_hmacs(tmp_path):
    env = _env(tmp_path, "INVIDIOUS_HMAC_KEY=localhack\nINVIDIOUS_COMPANION_KEY=your_companion_key_here\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert _usable(env)
    env = _env(tmp_path, f"INVIDIOUS_HMAC_KEY={'s' * 20}\nINVIDIOUS_COMPANION_KEY={LIVE_COMPANION}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert len(_read(env, "INVIDIOUS_HMAC_KEY")) == 64


def test_brand_defaults_no_longer_owns_the_invidious_keys():
    assert "INVIDIOUS_HMAC_KEY" not in bd.DEFAULTS
    assert "INVIDIOUS_COMPANION_KEY" not in bd.DEFAULTS
    src = (PMOVES / "tools" / "brand_defaults.py").read_text(encoding="utf-8")
    assert '_set_kv(text, "INVIDIOUS_' not in src


TEMPLATE = (
    "OTHER=keep\n"
    # What a node carries today: the 16-char token_urlsafe brand_defaults wrote
    # (with a '-', which the companion rejects) and a 32-char urlsafe HMAC.
    "INVIDIOUS_COMPANION_KEY=ab-def_123456789\n"
    "INVIDIOUS_HMAC_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz012345\n"
)


def _real_ensure_env_shared(tmp_path, text):
    """Run the REAL ensure-env-shared step: ensure_env_shared.py -> brand_defaults -> preflight."""
    import subprocess

    env = _env(tmp_path, text)
    template = tmp_path / "template.example"
    template.write_text("", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(PMOVES / "tools" / "ensure_env_shared.py"),
         "--env-file", str(env), "--template", str(template)],
        capture_output=True, text=True, env=_hermetic_env(),
    )
    return env, r


def _hermetic_env():
    """No INVIDIOUS_* exports, and NO DOCKER.

    The real preflight harvests a live key from any running container. On a
    developer node that would copy a real secret into the test's tmp file (and
    into an assertion message) -- observed once while writing this test. Point
    the docker CLI at a socket that does not exist so the probe sees no holders.
    """
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith(("INVIDIOUS_", "DOCKER_"))}
    env["DOCKER_HOST"] = "unix:///nonexistent/pmoves-test-no-docker.sock"
    return env


def test_funnel_path_repairs_a_dashed_companion_and_keeps_a_valid_hmac(tmp_path):
    """secrets-ensure-generated = ensure-env-shared prerequisite, then harvest + --ensure."""
    env, r = _real_ensure_env_shared(tmp_path, TEMPLATE)
    assert r.returncode == 0, r.stdout + r.stderr
    companion = _read(env, "INVIDIOUS_COMPANION_KEY") or ""
    repaired = bool(COMPANION_RE.fullmatch(companion)) and companion != "ab-def_123456789"
    assert repaired, "dashed companion key was not repaired"
    assert _read(env, "INVIDIOUS_HMAC_KEY") == "AbCdEfGhIjKlMnOpQrStUvWxYz012345"  # valid: kept
    assert "ab-def_123456789" not in r.stdout + r.stderr and companion not in r.stdout + r.stderr
    # The rest of the funnel step: harvest, then --ensure. Both now see a valid slot.
    plan = pf._sh.build_plan(list(pf.KEYS), env_path=env, probe=Probe(), registry_path=REGISTRY)
    assert {d.state for d in plan} == {pf._sh.STATE_SATISFIED}
    for key in pf.KEYS:
        assert pf._be.ensure_secret(key, env_path=env, registry_path=REGISTRY) == (False, "already set")
    assert _usable(env)


def test_funnel_path_mints_registry_format_on_a_virgin_node(tmp_path):
    env, r = _real_ensure_env_shared(tmp_path, "OTHER=keep\n")
    assert r.returncode == 0, r.stdout + r.stderr
    # Booleans only: never let pytest introspect a key into the failure output.
    minted_companion = bool(re.fullmatch(r"[0-9a-f]{16}", _read(env, "INVIDIOUS_COMPANION_KEY") or ""))
    minted_hmac = bool(re.fullmatch(r"[0-9a-f]{64}", _read(env, "INVIDIOUS_HMAC_KEY") or ""))
    assert minted_companion, "companion key is not the registry's random_hex 16"
    assert minted_hmac, "HMAC key is not the registry's random_hex 64"


def test_funnel_path_rotates_a_published_value(tmp_path, monkeypatch):
    """Published digests are patched in-process only, so drive the preflight directly."""
    table = {k: set(v) for k, v in common.KNOWN_PUBLIC_SECRET_DIGESTS.items()}
    table.setdefault(len(PUBLISHED), set()).add(common.known_public_digest(PUBLISHED))
    monkeypatch.setattr(common, "KNOWN_PUBLIC_SECRET_DIGESTS", {k: frozenset(v) for k, v in table.items()})
    env = _env(tmp_path, f"INVIDIOUS_COMPANION_KEY={PUBLISHED}\nINVIDIOUS_HMAC_KEY={LIVE_HMAC}\n")
    assert pf.run(env, check=False, registry=REGISTRY, probe=Probe()) == 0
    assert _read(env, "INVIDIOUS_COMPANION_KEY") != PUBLISHED
