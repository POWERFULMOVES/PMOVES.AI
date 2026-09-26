"""Regression guard: the bundle map covers every secret GitHub holds.

The CHIT bundle every node consumes (Linux runners and the Windows 4090/5090
alike) is built only from the env: block of sync-secrets-local.yml. PR #2888
found COMPOSIO_API_KEY registered everywhere except that block; on 2026-09-26
the same gap was measured at 32 names. Every node is a full copy of PMOVES.AI,
so the map must cover the full repo + Prod name set, not a runtime subset.

Offline tests run everywhere. ``test_live_full_coverage`` lists names with
``gh`` and skips (could-not-measure) where gh cannot list repository secrets,
e.g. in CI with the default token. Names only -- no value is ever read.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

from pmoves.tools import secrets_bundle_map_gap as gap

# Rows added 2026-09-26 (plus #2888's COMPOSIO_API_KEY). Deleting any of them
# re-opens the gap for that name on every node. The eight node-local address
# labels are deliberately NOT here: see test_node_local_labels_are_not_mapped.
ROWS_ADDED = {
    "ACTIVEPIECES_API_KEY", "CF_AI_GATEWAY_TOKEN", "CF_SSH_PUB", "CI_GHCR_NAMESPACE",
    "GHCR_APP_CLIENT_ID", "GHCR_APP_SEC", "GH_DARKXSIDE", "GH_PAT_PUBLISH",
    "N8N_API_KEY", "N8N_RUNNERS_AUTH_TOKEN",
    "NEXT_PUBLIC_BACKEND_API_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NGC_KEY",
    "SERVICE_PASSWORD_ADMIN", "SERVICE_PASSWORD_POSTGRES", "SERVICE_USER_ADMIN",
    "SUPABASE_KEY", "SURREAL_PASS", "SURREAL_USER",
    "TAILSCALE_WEBHOOK", "TELEGRAM_BOT_NAME", "TS_TAILNET",
    "COMPOSIO_API_KEY",
}

NODE_LOCAL = {
    "NATS_URL", "NATS_URL_TAILNET", "SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL",
    "POSTGRES_HOSTNAME", "POSTGRES_DB", "OLLAMA_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL",
}


@pytest.fixture(scope="module")
def bmap():
    return gap.load_map()


def test_map_parses_from_the_real_workflow(bmap):
    # Guards the parser: a silently empty map would make every check vacuous.
    assert len(bmap.rows) >= 130, len(bmap.rows)
    assert len(bmap.sources) >= 125, len(bmap.sources)
    assert (bmap.environment or "").lower() == "prod"


def test_stdlib_allowlist_parser_matches_yaml(bmap):
    # The workflow step builds its allowlist with declared_env_keys() (runner
    # Python may lack PyYAML). It must agree with the YAML parse exactly.
    assert gap.declared_env_keys() == set(bmap.rows)


def test_node_local_labels_are_not_mapped(bmap):
    # #3188 review P1: Prod's addresses must not ship to any node.
    assert set(gap.NODE_LOCAL) == NODE_LOCAL
    assert not NODE_LOCAL & set(bmap.rows), sorted(NODE_LOCAL & set(bmap.rows))
    for name in NODE_LOCAL:
        assert gap.EXCEPTIONS[name] == gap.NODE_LOCAL_REASON
    rep = gap.analyse(bmap, NODE_LOCAL | {"COMPOSIO_API_KEY"})
    assert rep.uncovered == [] and not rep.findings


def test_node_local_row_is_a_finding(bmap):
    fake = gap.BundleMap(dict(bmap.rows, NATS_URL={"NATS_URL"}), bmap.environment)
    rep = gap.analyse(fake, {"NATS_URL"})
    assert rep.node_local_mapped == ["NATS_URL"] and rep.findings


def test_node_local_tuple_matches_the_declaration():
    from pmoves.tools.node_local_keys import load_node_local

    assert set(load_node_local()) == set(gap.NODE_LOCAL)


def test_builder_is_an_allowlist_not_an_environ_walk():
    text = gap.WORKFLOW.read_text(encoding="utf-8")
    assert "skip_prefixes" not in text
    assert "for name in sorted(os.environ)" not in text
    assert "declared_env_keys(workflow) - NON_SECRET_ROWS" in text


def _builder_script() -> str:
    import yaml

    doc = yaml.safe_load(gap.WORKFLOW.read_text(encoding="utf-8"))
    _, step = gap._find_step(doc)
    body = step["run"].split("<< 'PYTHON_SCRIPT'\n", 1)[1].rsplit("PYTHON_SCRIPT", 1)[0]
    return textwrap.dedent(body)


def test_builder_bundles_declared_rows_only(tmp_path):
    """Run the step's real Python in a scratch workspace with fake values.

    Declared rows land (including CI_GHCR_NAMESPACE, which the old 'CI' skip
    prefix dropped); runner variables and node-local names do not.
    """
    wf = tmp_path / ".github" / "workflows" / "sync-secrets-local.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(gap.WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "builder.py"
    script.write_text(_builder_script(), encoding="utf-8")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(gap.REPO_ROOT),
        "GITHUB_WORKSPACE": str(tmp_path),
        "COMPOSIO_API_KEY": "fake-composio-value",
        "CI_GHCR_NAMESPACE": "fake-namespace",
        "ANTHROPIC_API_KEY": "",
        # Runner leakage the old os.environ walk let through:
        "HOSTNAME": "runner-container-id",
        "LABELS": "self-hosted,linux",
        "_": "/usr/bin/python3",
        "http_proxy": "http://fake-proxy",
        # Node-local: no row, so never bundled even when present:
        "SUPABASE_URL": "http://fake-prod-supabase",
    }
    out = subprocess.run([sys.executable, str(script)], env=env, cwd=tmp_path,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    bundled = set(gap.bundle_labels(tmp_path / "pmoves" / "data" / "chit" / "env.cgp.json"))
    assert bundled == {"COMPOSIO_API_KEY", "CI_GHCR_NAMESPACE"}, bundled
    local_env = (tmp_path / "pmoves" / "secrets" / "local.env").read_text()
    assert {ln.split("=", 1)[0] for ln in local_env.splitlines()} == bundled


def test_rows_added_are_present_and_self_named(bmap):
    missing = sorted(n for n in ROWS_ADDED if n not in bmap.rows.get(n, set()))
    assert not missing, f"map rows removed or renamed: {missing}"


def test_tailscale_reads_canonical_prod_secret_first(bmap):
    assert bmap.rows["TAILSCALE_API_KEY"] == {"TAILSCALE_API_KEY", "TAILSCALE_APIKEY"}
    text = gap.WORKFLOW.read_text(encoding="utf-8")
    assert "secrets.TAILSCALE_API_KEY || secrets.TAILSCALE_APIKEY" in text


def test_anthropic_label_kept_but_reads_no_secret(bmap):
    assert "ANTHROPIC_API_KEY" in bmap.rows
    assert bmap.rows["ANTHROPIC_API_KEY"] == set()
    assert "ANTHROPIC_API_KEY" in gap.EXCEPTIONS


def test_analyse_flags_unmapped_and_honours_exceptions(bmap):
    registered = {"COMPOSIO_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "BRAND_NEW_SECRET"}
    rep = gap.analyse(bmap, registered)
    assert rep.uncovered == ["BRAND_NEW_SECRET"]
    assert rep.findings


def test_analyse_bundle_reports_mapped_but_undelivered(bmap):
    rep = gap.analyse(bmap, {"COMPOSIO_API_KEY", "N8N_API_KEY"}, bundle={"COMPOSIO_API_KEY"})
    assert rep.not_in_bundle == ["N8N_API_KEY"]


def test_cli_exit_codes(tmp_path):
    clean = tmp_path / "clean.txt"
    clean.write_text("COMPOSIO_API_KEY\nANTHROPIC_API_KEY\n")
    dirty = tmp_path / "dirty.txt"
    dirty.write_text("COMPOSIO_API_KEY\nBRAND_NEW_SECRET\n")
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    assert gap.main(["--names-file", str(clean)]) == gap.EXIT_CLEAN
    assert gap.main(["--names-file", str(dirty)]) == gap.EXIT_FINDINGS
    # Zero names must not read as "clean".
    assert gap.main(["--names-file", str(empty)]) == gap.EXIT_COULD_NOT_MEASURE
    assert gap.main(["--names-file", str(tmp_path / "absent.txt")]) == gap.EXIT_COULD_NOT_MEASURE


def test_bundle_reader_uses_labels_only(tmp_path):
    bundle = tmp_path / "env.cgp.json"
    bundle.write_text(json.dumps({"points": [{"label": "A", "value": "x"}, {"label": "B"}]}))
    assert gap.bundle_labels(bundle) == {"A", "B"}


def test_gh_failure_is_could_not_measure(monkeypatch, tmp_path):
    def fake_run(*a, **k):
        return subprocess.CompletedProcess(a[0], 1, stdout="", stderr="HTTP 403")

    monkeypatch.setattr(gap.subprocess, "run", fake_run)
    assert gap.main(["--live"]) == gap.EXIT_COULD_NOT_MEASURE


def test_live_full_coverage(bmap):
    """The full repo + Prod name set, measured via gh (names only)."""
    if shutil.which("gh") is None:
        pytest.skip("COULD-NOT-MEASURE: gh not installed")
    try:
        scopes = gap.live_names(bmap.environment)
    except gap.CouldNotMeasure as exc:
        pytest.skip(f"COULD-NOT-MEASURE: {exc}")
    registered = set().union(*scopes.values())
    if not registered:
        # An empty listing must not read as "fully covered".
        pytest.skip("COULD-NOT-MEASURE: gh listed zero secret names")
    rep = gap.analyse(bmap, registered)
    sizes = {k: len(v) for k, v in scopes.items()}
    assert rep.uncovered == [], f"inputs {sizes}; unmapped GitHub secrets: {rep.uncovered}"
