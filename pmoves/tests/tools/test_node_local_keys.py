"""Node-local address labels: never Prod's value, never deleted, fail closed.

#3188 review P1. Operator direction (2026-09-26): each node's NATS_URL and
friends point at that node's OWN services via its Tailscale name (TS_B850 on
Knuckles), not at whatever GitHub Prod holds. Addresses in this file are from
TEST-NET-1 (192.0.2.0/24, RFC 5737), never a real tailnet address.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from pmoves.tools import node_local_keys as nl
from pmoves.tools import secrets_local_hydrate as hydrate_mod
from pmoves.tools import secrets_sync

REPO_ROOT = nl.REPO_ROOT
PS1 = REPO_ROOT / "deploy" / "provision" / "claude-pmoves.ps1"
FAKE_TS = "192.0.2.10"  # RFC 5737 TEST-NET-1
CGNAT = re.compile(r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b")

# Files this change owns. The CGNAT guard scans these plus whatever git can
# list as changed against origin/main, so it still runs on a shallow clone.
OWNED = [
    "pmoves/config/node_local_keys.yaml",
    "pmoves/tools/node_local_keys.py",
    "pmoves/tools/secrets_sync.py",
    "pmoves/tools/secrets_local_hydrate.py",
    "pmoves/tools/secrets_bundle_map_gap.py",
    "pmoves/tests/tools/test_node_local_keys.py",
    "pmoves/tests/tools/test_secrets_bundle_map_gap.py",
    ".github/workflows/sync-secrets-local.yml",
]


def _entry(label, *files):
    return secrets_sync.Entry(
        id=label.lower(),
        label=label,
        required=True,
        targets=[secrets_sync.Target(file=f, key=label) for f in (files or ("env.tier-agent",))],
    )


def _ok():
    return FAKE_TS, "stub"


def _unresolved():
    return None, "TS_B850 is empty (stub)"


# -- declaration -------------------------------------------------------------


def test_declaration_is_the_eight_labels_and_templates_hold_names_only():
    decl = nl.load_node_local()
    assert set(decl) == {
        "NATS_URL", "NATS_URL_TAILNET", "SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL",
        "POSTGRES_HOSTNAME", "POSTGRES_DB", "OLLAMA_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL",
    }
    # POSTGRES_DB is a database name, not an address: never templated.
    assert decl["POSTGRES_DB"] is None
    for label, template in decl.items():
        if template is None:
            continue
        assert "${TS_SELF}" in template, label
        # Names only: no dotted-quad, no literal host, no literal credential.
        assert not re.search(r"\d+\.\d+\.\d+\.\d+", template), label
        assert re.sub(r"\$\{[A-Z_]+\}", "", template).count("@") <= 1


def test_load_node_local_refuses_an_empty_declaration(tmp_path):
    bad = tmp_path / "node_local_keys.yaml"
    bad.write_text("keys: {}\n")
    with pytest.raises(ValueError):
        nl.load_node_local(bad)


# -- one resolver: the .sh table is read, the .ps1 twin must agree ------------


def _ps1_table():
    text = PS1.read_text(encoding="utf-8")
    exact = dict(re.findall(r"'(pmoves-[A-Za-z0-9-]+)'\s*=\s*'(TS_[A-Z0-9_]+)'", text))
    for pattern, var in re.findall(r"-like\s+'(pmoves-[^']+)'\)\s*\{\s*\$var\s*=\s*'(TS_[A-Z0-9_]+)'", text):
        exact[pattern] = var
    return exact


def test_sh_and_ps1_resolvers_share_one_table():
    sh = dict(nl.hostname_table())
    ps1 = _ps1_table()
    assert len(sh) == 8, sh
    assert sh == ps1, {"sh_only": set(sh.items()) - set(ps1.items()),
                       "ps1_only": set(ps1.items()) - set(sh.items())}


def test_self_ts_var_follows_node_identity():
    var, why = nl.self_ts_var(env={"PMOVES_NODE_ID": "pmoves-b850"})
    assert var == "TS_B850", why
    var, why = nl.self_ts_var(env={"PMOVES_NODE_ID": "pmoves-4090"})
    assert var == "TS_4090", why
    var, why = nl.self_ts_var(env={}, hostname="not-a-pmoves-node")
    assert var is None and "unresolved" in why


def test_resolve_ts_self_uses_the_resolver_and_fails_closed():
    env = {"PMOVES_NODE_ID": "pmoves-b850"}
    value, _ = nl.resolve_ts_self(env=env, resolve_vars=lambda names, e: {"TS_B850": FAKE_TS})
    assert value == FAKE_TS
    value, why = nl.resolve_ts_self(env=env, resolve_vars=lambda names, e: {"TS_B850": ""})
    assert value is None and "TS_B850 is empty" in why
    value, why = nl.resolve_ts_self(env=env, resolve_vars=lambda names, e: {"TS_B850": "a b/c"})
    assert value is None and "refusing" in why


def test_resolve_ts_self_reuses_the_shared_helper_route(monkeypatch):
    seen = {}

    def fake(names, env):
        seen["names"] = names
        return {n: FAKE_TS for n in names}

    from pmoves.tools import crush_configurator

    monkeypatch.setattr(crush_configurator, "_resolve_ts_vars", fake)
    value, _ = nl.resolve_ts_self(env={"PMOVES_NODE_ID": "pmoves-b850"})
    assert value == FAKE_TS and seen["names"] == ["TS_B850"]


# -- secrets_sync -------------------------------------------------------------


def test_rendered_nats_url_uses_this_nodes_tailnet_address(monkeypatch):
    monkeypatch.delenv("NATS_USER", raising=False)
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    bundle = {
        "NATS_URL": "nats://prod-value",  # Prod's value: must be ignored
        "NATS_USER": "fake-user",
        "NATS_PASSWORD": "fake-pass",
    }
    outputs, missing = secrets_sync.build_outputs(
        bundle, [_entry("NATS_URL", "env.tier-agent", ".env.generated")],
        strict=False, ts_self=_ok,
    )
    want = f"nats://fake-user:fake-pass@{FAKE_TS}:4222"
    assert outputs["env.tier-agent"]["NATS_URL"] == want
    assert outputs[".env.generated"]["NATS_URL"] == want
    assert missing == []


def test_unresolvable_ts_leaves_key_untouched_and_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    (tmp_path / "env.tier-agent").write_text("NATS_URL=nats://node-own-value\nOTHER=1\n")
    rejected: dict = {}
    outputs, missing = secrets_sync.build_outputs(
        {"NATS_URL": "nats://prod-value", "NATS_USER": "u", "NATS_PASSWORD": "p"},
        [_entry("NATS_URL")], strict=False, rejected_out=rejected, ts_self=_unresolved,
    )
    err = capsys.readouterr().err
    assert "NATS_URL" not in outputs.get("env.tier-agent", {})
    assert rejected == {} and missing == []
    assert "node-local key(s) NOT written" in err and "NATS_URL" in err
    assert "TS_SELF" in err
    assert FAKE_TS not in err and "prod-value" not in err
    secrets_sync.write_env_files(outputs, merge=True, remove=rejected)
    assert "NATS_URL=nats://node-own-value" in (tmp_path / "env.tier-agent").read_text()


def test_unresolved_credential_placeholder_also_fails_closed(monkeypatch, capsys):
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    outputs, _ = secrets_sync.build_outputs(
        {"NATS_USER": "u"}, [_entry("NATS_URL")], strict=False, ts_self=_ok,
    )
    assert "NATS_URL" not in outputs.get("env.tier-agent", {})
    assert "NATS_PASSWORD" in capsys.readouterr().err


def test_untemplated_labels_never_take_the_bundle_value():
    labels = ["SUPABASE_URL", "POSTGRES_DB", "OLLAMA_BASE_URL", "POSTGRES_HOSTNAME"]
    bundle = {label: f"prod-{label.lower()}" for label in labels}
    rejected: dict = {}
    outputs, missing = secrets_sync.build_outputs(
        bundle, [_entry(label, "env.tier-data") for label in labels],
        strict=True, rejected_out=rejected, ts_self=_ok,
    )
    assert outputs.get("env.tier-data", {}) == {}
    assert rejected == {} and missing == []


@pytest.mark.parametrize("merge", [True, False])
def test_node_local_keys_survive_a_sync_that_lacks_them(tmp_path, monkeypatch, merge):
    monkeypatch.setattr(secrets_sync, "PROJECT_ROOT", tmp_path)
    tier = tmp_path / "env.tier-data"
    tier.write_text("POSTGRES_DB=node_db\nSUPABASE_URL=http://node-own\nSTALE=x\n")
    entries = [_entry("POSTGRES_DB", "env.tier-data"), _entry("SUPABASE_URL", "env.tier-data"),
               _entry("SOME_KEY", "env.tier-data")]
    rejected: dict = {}
    outputs, _ = secrets_sync.build_outputs(
        {"SOME_KEY": "v"}, entries, strict=False, rejected_out=rejected, ts_self=_ok,
    )
    # Defence in depth: even an explicit removal request cannot delete them.
    rejected.setdefault("env.tier-data", set()).update({"POSTGRES_DB", "SUPABASE_URL"})
    secrets_sync.write_env_files(outputs, merge=merge, remove=rejected)
    text = tier.read_text()
    assert "POSTGRES_DB=node_db" in text
    assert "SUPABASE_URL=http://node-own" in text
    assert "SOME_KEY=v" in text


# -- hydrate --------------------------------------------------------------------


def test_hydrate_force_skips_node_local_keys(tmp_path):
    local_env = tmp_path / "local.env"
    shared = tmp_path / "env.shared"
    cleared = tmp_path / "cleared.yaml"
    cleared.write_text("cleared: []\n")
    local_env.write_text(
        "NATS_URL=nats://prod-value\nSUPABASE_URL=http://prod\nPOSTGRES_DB=prod_db\n"
        "SOME_API_KEY=rotated-value-123456\n"
    )
    shared.write_text("NATS_URL=nats://node-own\nSOME_API_KEY=old-value-123456\n")
    updates = hydrate_mod.hydrate(local_env, shared, force=True, cleared_keys_path=cleared)
    assert set(updates) == {"SOME_API_KEY"}
    text = shared.read_text()
    assert "NATS_URL=nats://node-own" in text
    assert "SUPABASE_URL" not in text and "POSTGRES_DB" not in text


# -- no tailnet (CGNAT, RFC 6598) address in anything this change touches ------


def _changed_files():
    files = set(OWNED)
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
        if out.returncode == 0:
            files |= {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(files)


def test_no_tailnet_address_in_changed_files():
    hits = []
    scanned = 0
    for rel in _changed_files():
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        scanned += 1
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if CGNAT.search(line):
                hits.append(f"{rel}:{n}")
    assert scanned >= len(OWNED), scanned
    assert not hits, f"CGNAT (RFC 6598) tailnet address committed: {hits}"
