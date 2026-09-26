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
import shutil
import subprocess

import pytest

from pmoves.tools import secrets_bundle_map_gap as gap

# Rows added 2026-09-26 (plus #2888's COMPOSIO_API_KEY). Deleting any of them
# re-opens the gap for that name on every node.
ROWS_ADDED = {
    "ACTIVEPIECES_API_KEY", "CF_AI_GATEWAY_TOKEN", "CF_SSH_PUB", "CI_GHCR_NAMESPACE",
    "GHCR_APP_CLIENT_ID", "GHCR_APP_SEC", "GH_DARKXSIDE", "GH_PAT_PUBLISH",
    "N8N_API_KEY", "N8N_RUNNERS_AUTH_TOKEN", "NATS_URL", "NATS_URL_TAILNET",
    "NEXT_PUBLIC_BACKEND_API_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_URL", "NGC_KEY", "OLLAMA_BASE_URL",
    "OPENAI_COMPATIBLE_BASE_URL", "POSTGRES_DB", "POSTGRES_HOSTNAME",
    "SERVICE_PASSWORD_ADMIN", "SERVICE_PASSWORD_POSTGRES", "SERVICE_USER_ADMIN",
    "SUPABASE_KEY", "SUPABASE_URL", "SURREAL_PASS", "SURREAL_USER",
    "TAILSCALE_WEBHOOK", "TELEGRAM_BOT_NAME", "TS_TAILNET",
    "COMPOSIO_API_KEY",
}


@pytest.fixture(scope="module")
def bmap():
    return gap.load_map()


def test_map_parses_from_the_real_workflow(bmap):
    # Guards the parser: a silently empty map would make every check vacuous.
    assert len(bmap.rows) >= 130, len(bmap.rows)
    assert len(bmap.sources) >= 130, len(bmap.sources)
    assert bmap.skip_prefixes, "skip_prefixes not parsed"
    assert (bmap.environment or "").lower() == "prod"


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


def test_no_new_skip_prefix_collisions(bmap):
    rep = gap.analyse(bmap, bmap.sources)
    assert rep.new_prefix_collisions == [], (
        "a mapped secret row is dropped by the step's skip_prefixes: "
        f"{rep.new_prefix_collisions}"
    )
    assert rep.known_prefix_collisions == ["CI_GHCR_NAMESPACE"]


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
    rep = gap.analyse(bmap, registered)
    sizes = {k: len(v) for k, v in scopes.items()}
    assert rep.uncovered == [], f"inputs {sizes}; unmapped GitHub secrets: {rep.uncovered}"
