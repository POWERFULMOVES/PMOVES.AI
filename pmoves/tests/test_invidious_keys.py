"""Invidious keys: vendor format, no public literal, published values rotate out.

Until fix/invidious-required-keys, ``INVIDIOUS_HMAC_KEY`` and
``INVIDIOUS_COMPANION_KEY`` shipped as literal hex defaults in the public compose
files, so every node that never set them ran on published keys. Three properties
keep that from coming back:

1. The bootstrap registry mints each key in the format the vendor requires. The
   companion key must be EXACTLY 16 alphanumeric characters: Invidious exits
   unless ``invidious_companion_key.size == 16`` (iv-org/invidious
   src/invidious/config.cr) and the companion's schema is
   ``z.string().length(16).regex(/^[a-zA-Z0-9]+$/)`` (iv-org/invidious-companion
   src/lib/helpers/config.ts). The registry used to say 64.
2. A value that was published (``KNOWN_PUBLIC_SECRET_SHA256``) counts as
   unprovisioned everywhere the funnel asks "is this slot filled?": ensure,
   ensure-dry-run, harvest and the runtime hydrate. Otherwise the funnel would
   harvest the public key back out of a running container and defend it.
3. No compose file carries a credential-shaped secret default
   (``validate_composes.py`` rule ``literal-secret-default``).

Fixture values below are INVENTED. The real published values are never written
into this repo again; the denylist holds their SHA-256 digests only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PMOVES = Path(__file__).resolve().parents[1]
REGISTRY = PMOVES / "bootstrap" / "registry.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


be = _load("bootstrap_env_invidious_under_test", PMOVES / "scripts" / "bootstrap_env.py")
sh = _load("secrets_harvest_invidious_under_test", PMOVES / "tools" / "secrets_harvest.py")
rsh = _load("runtime_hydrate_invidious_under_test", PMOVES / "tools" / "runtime_secrets_hydrate.py")
import pmoves.tools._secrets_common as common  # noqa: E402  (path set by bootstrap_env)

# The companion's own validator, transcribed from invidious-companion
# src/lib/helpers/config.ts at fcb0456ad5bd (2026-10-18).
COMPANION_KEY_RE = re.compile(r"^[a-zA-Z0-9]{16}$")

FAKE_PUBLIC = "0123456789abcdef"  # stands in for a published companion key
FAKE_LIVE = "a1b2c3d4e5f60718"  # stands in for a private, live companion key


@pytest.fixture
def published(monkeypatch):
    """Pretend FAKE_PUBLIC was published, without touching the real digests."""
    digest = hashlib.sha256(FAKE_PUBLIC.encode()).hexdigest()
    monkeypatch.setattr(
        common, "KNOWN_PUBLIC_SECRET_SHA256", common.KNOWN_PUBLIC_SECRET_SHA256 | {digest}
    )
    return FAKE_PUBLIC


def _specs():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {
        v["key"]: v
        for s in data.get("services", [])
        for v in s.get("variables", [])
    }


def _env(tmp_path: Path, text: str) -> Path:
    p = tmp_path / ("env." + "shared")
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. Vendor format
# ---------------------------------------------------------------------------


def test_companion_key_generator_is_exactly_16_alphanumeric():
    spec = _specs()["INVIDIOUS_COMPANION_KEY"]["generate"]
    assert spec == {"type": "random_hex", "length": 16}
    for _ in range(50):
        assert COMPANION_KEY_RE.fullmatch(be.generate_value(spec))


def test_hmac_key_generator_is_a_long_random_string():
    # Vendor: mandatory, random, `pwgen 20 1` suggested. 64 hex clears that.
    spec = _specs()["INVIDIOUS_HMAC_KEY"]["generate"]
    assert spec["type"] == "random_hex" and spec["length"] >= 20


def test_both_keys_are_sourced_from_the_funnel_source_file():
    specs = _specs()
    for key in ("INVIDIOUS_HMAC_KEY", "INVIDIOUS_COMPANION_KEY"):
        assert specs[key]["file"] == "pmoves/env." + "shared"
        assert specs[key]["required"] is True


def test_runtime_hydrate_mint_satisfies_the_companion_schema():
    updates = rsh.hydrate_runtime_labels({}, status_values={}, containers=[])
    assert COMPANION_KEY_RE.fullmatch(updates["INVIDIOUS_COMPANION_KEY"])


def test_funnel_ensures_both_keys():
    """Compose interpolates every service, profiled or not -> every node mints."""
    text = (PMOVES / "mk" / "codex.mk").read_text(encoding="utf-8")
    block = text.split("SECRETS_ENSURE_KEYS ?=", 1)[1].split("\n\n", 1)[0]
    assert "INVIDIOUS_HMAC_KEY" in block
    assert "INVIDIOUS_COMPANION_KEY" in block


# ---------------------------------------------------------------------------
# 2. Published values are unprovisioned
# ---------------------------------------------------------------------------


def test_denylist_holds_digests_not_values():
    assert len(common.KNOWN_PUBLIC_SECRET_SHA256) >= 2
    for digest in common.KNOWN_PUBLIC_SECRET_SHA256:
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_published_value_is_a_placeholder(published):
    assert common.is_known_public(published)
    assert common.is_known_public(f'"{published}"')  # quoted in an env file
    assert common.is_placeholder(published)
    assert not common.is_placeholder(FAKE_LIVE)


def test_slot_is_filled_rejects_published_values(published):
    assert not be.slot_is_filled(None)
    assert not be.slot_is_filled("")
    assert not be.slot_is_filled(published)
    assert be.slot_is_filled(FAKE_LIVE)


def test_ensure_replaces_a_published_value(tmp_path, published):
    env = _env(tmp_path, f"OTHER=keep\nINVIDIOUS_COMPANION_KEY={published}\n")
    generated, reason = be.ensure_secret(
        "INVIDIOUS_COMPANION_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert generated, reason
    assert "published" in reason
    value = be.read_env_value("INVIDIOUS_COMPANION_KEY", env)
    assert value != published and COMPANION_KEY_RE.fullmatch(value)
    assert be.read_env_value("OTHER", env) == "keep"


def test_ensure_never_touches_a_private_value(tmp_path, published):
    env = _env(tmp_path, f"INVIDIOUS_COMPANION_KEY={FAKE_LIVE}\n")
    generated, _ = be.ensure_secret(
        "INVIDIOUS_COMPANION_KEY", env_path=env, registry_path=str(REGISTRY)
    )
    assert not generated
    assert be.read_env_value("INVIDIOUS_COMPANION_KEY", env) == FAKE_LIVE


def test_ensure_dry_run_reports_published_value_unprovisioned(tmp_path, monkeypatch, capsys, published):
    env = _env(tmp_path, f"INVIDIOUS_COMPANION_KEY={published}\n")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    rc = be.main(["--ensure", "INVIDIOUS_COMPANION_KEY", "--ensure-dry-run", "--registry", str(REGISTRY)])
    out = capsys.readouterr()
    assert rc == 1
    assert "published" in out.out + out.err
    assert published not in out.out + out.err


class _Probe:
    def __init__(self, containers):
        self._c = containers

    def available(self):
        return True

    def container_envs(self):
        return dict(self._c)

    def volumes(self):
        return []


def test_harvest_does_not_recover_a_published_value_from_a_container(tmp_path, published):
    env = _env(tmp_path, "OTHER=keep\n")
    probe = _Probe({"pmoves-invidious-1": {"INVIDIOUS_COMPANION_KEY": published}})
    plan = sh.build_plan(["INVIDIOUS_COMPANION_KEY"], env_path=env, probe=probe, registry_path=str(REGISTRY))
    assert plan[0].state == sh.STATE_MINT


def test_harvest_still_recovers_a_private_live_value(tmp_path, published):
    env = _env(tmp_path, "OTHER=keep\n")
    probe = _Probe({"pmoves-invidious-1": {"INVIDIOUS_COMPANION_KEY": FAKE_LIVE}})
    plan = sh.build_plan(["INVIDIOUS_COMPANION_KEY"], env_path=env, probe=probe, registry_path=str(REGISTRY))
    assert plan[0].state == sh.STATE_HARVEST


def test_harvest_treats_a_published_env_value_as_unset(tmp_path, published):
    env = _env(tmp_path, f"INVIDIOUS_COMPANION_KEY={published}\n")
    plan = sh.build_plan(["INVIDIOUS_COMPANION_KEY"], env_path=env, probe=_Probe({}), registry_path=str(REGISTRY))
    assert plan[0].state == sh.STATE_MINT


def test_runtime_hydrate_replaces_a_published_value(published):
    env_values = {"INVIDIOUS_COMPANION_KEY": published}
    updates = rsh.hydrate_runtime_labels(env_values, status_values={}, containers=[])
    assert updates["INVIDIOUS_COMPANION_KEY"] != published


# ---------------------------------------------------------------------------
# 3. No compose file ships a credential-shaped secret default
# ---------------------------------------------------------------------------


def test_no_compose_file_ships_a_literal_secret_default():
    """The regression gate: re-adding `${INVIDIOUS_HMAC_KEY:-<hex>}` fails here."""
    r = subprocess.run(
        [sys.executable, str(PMOVES / "tools" / "validate_composes.py"), "--json"],
        capture_output=True, text=True,
    )
    out = json.loads(r.stdout)
    literal = [p for p in out["problems"] if p["kind"] == "literal-secret-default"]
    assert out["files_total"] > 0
    assert literal == [], "\n".join(f"{p['file']}:{p['line']} {p['detail']}" for p in literal)


def test_invidious_compose_keys_are_required():
    # Report variable names and counts only. Never let pytest introspect the
    # matched text: on main it IS the published key, and CI logs are public.
    bad = []
    for name in ("docker-compose.yml", "docker-compose.ui.yml"):
        text = (PMOVES / name).read_text(encoding="utf-8")
        for var in ("INVIDIOUS_HMAC_KEY", "INVIDIOUS_COMPANION_KEY"):
            tails = re.findall(r"\$\{" + var + r"([^}]*)\}", text)
            if not tails:
                bad.append(f"{name}: no reference to {var}")
            loose = sum(1 for tail in tails if not tail.startswith(":?"))
            if loose:
                bad.append(f"{name}: {loose} reference(s) to {var} are not ${{{var}:?...}}")
    assert not bad, "; ".join(bad)
