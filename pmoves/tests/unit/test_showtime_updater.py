"""Pure-logic unit tests for the showtime updater.

Run with::

    python -m pytest pmoves/tests/unit/test_showtime_updater.py -q --noconftest

``--noconftest`` is used because the repo conftest imports ``pytest_asyncio``
which may be absent. These tests are intentionally dependency-free (stdlib +
pytest only) and load ``updater.py`` by file path (its directory,
``services/showtime-api``, is not an importable package).
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType

import pytest

UPDATER_PATH = (
    Path(__file__).resolve().parents[2]
    / "services"
    / "showtime-api"
    / "updater.py"
)


def _load_updater() -> ModuleType:
    spec = importlib.util.spec_from_file_location("showtime_updater_under_test", UPDATER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


updater = _load_updater()


# ---------------------------------------------------------------------------
# Gate — both factors must hold
# ---------------------------------------------------------------------------
class TestGate:
    def test_both_factors_present_unlocks(self) -> None:
        env = {"CHIT_PASSPHRASE": "s3cret-pass", "GOOGLE_SESSION_TOKEN": "ya29.tok"}
        result = updater.evaluate_gate(env)
        assert result["unlocked"] is True
        assert result["chit_ok"] is True
        assert result["google_ok"] is True

    def test_chit_only_stays_locked(self) -> None:
        env = {"CHIT_PASSPHRASE": "s3cret-pass"}
        result = updater.evaluate_gate(env)
        assert result["unlocked"] is False
        assert result["google_ok"] is False
        assert "Google session" in result["reason"]

    def test_google_only_stays_locked(self) -> None:
        env = {"GOOGLE_SESSION_TOKEN": "ya29.tok"}
        result = updater.evaluate_gate(env)
        assert result["unlocked"] is False
        assert result["chit_ok"] is False
        assert "CHIT" in result["reason"]

    def test_placeholder_passphrase_is_locked(self) -> None:
        env = {"CHIT_PASSPHRASE": "changeme", "GOOGLE_SESSION_TOKEN": "ya29.tok"}
        result = updater.evaluate_gate(env)
        assert result["unlocked"] is False
        assert result["chit_ok"] is False

    def test_empty_env_fails_closed(self) -> None:
        result = updater.evaluate_gate({})
        assert result["unlocked"] is False

    def test_skip_chit_param_bypasses_chit_factor(self) -> None:
        env = {"GOOGLE_SESSION_TOKEN": "ya29.tok"}  # no CHIT passphrase
        result = updater.evaluate_gate(env, skip_chit=True)
        assert result["unlocked"] is True
        assert result["skip_chit"] is True

    def test_skip_chit_still_requires_google(self) -> None:
        result = updater.evaluate_gate({}, skip_chit=True)
        assert result["unlocked"] is False
        assert result["google_ok"] is False

    def test_skip_chit_via_env_flag(self) -> None:
        env = {"GOOGLE_SESSION_TOKEN": "ya29.tok", "SHOWTIME_UPDATER_SKIP_CHIT": "1"}
        result = updater.evaluate_gate(env)
        assert result["unlocked"] is True
        assert result["skip_chit"] is True

    def test_supabase_session_counts_as_google(self) -> None:
        env = {"CHIT_PASSPHRASE": "s3cret", "SUPABASE_SESSION": "sb-token"}
        result = updater.evaluate_gate(env)
        assert result["unlocked"] is True


# ---------------------------------------------------------------------------
# Blast-radius filtering
# ---------------------------------------------------------------------------
class TestBlastRadius:
    def test_filter_keeps_only_in_radius(self) -> None:
        candidates = ["loki", "agent-zero", "cipher-memory"]
        out = updater.filter_blast_radius(candidates, ["loki", "cipher-memory"])
        assert out == ["loki", "cipher-memory"]

    def test_filter_preserves_candidate_order(self) -> None:
        candidates = ["cipher-memory", "loki"]
        out = updater.filter_blast_radius(candidates, ["loki", "cipher-memory"])
        assert out == ["cipher-memory", "loki"]

    def test_run_update_acts_only_within_radius(self) -> None:
        result = updater.run_update(
            ["loki"],
            candidates=["loki", "open-notebook"],
            dirty_check=lambda: False,
            dry_run=True,
        )
        assert result["status"] == "ok"
        acted = [e["service"] for e in result["acted_on"]]
        assert acted == ["loki"]

    def test_run_update_rejects_agent_tier(self) -> None:
        result = updater.run_update(
            ["agent-zero"],
            dirty_check=lambda: False,
            dry_run=True,
        )
        assert result["status"] == "aborted"
        assert "agent-tier" in result["reason"]

    def test_run_update_rejects_global(self) -> None:
        result = updater.run_update(
            ["all"],
            dirty_check=lambda: False,
            dry_run=True,
        )
        assert result["status"] == "aborted"
        assert "global" in result["reason"]


# ---------------------------------------------------------------------------
# Safe-default radius
# ---------------------------------------------------------------------------
class TestSafeDefaultRadius:
    def test_default_radius_is_data_tier_only(self) -> None:
        # No agent-tier service may appear in the safe default.
        assert not (set(updater.SAFE_DEFAULT_BLAST_RADIUS) & updater.AGENT_TIER_SERVICES)

    def test_run_update_uses_safe_default_when_none(self) -> None:
        result = updater.run_update(
            None,
            dirty_check=lambda: False,
            dry_run=True,
        )
        assert result["used_default_radius"] is True
        assert result["blast_radius"] == list(updater.SAFE_DEFAULT_BLAST_RADIUS)
        assert result["status"] in {"ok", "noop"}

    def test_default_radius_never_touches_agents(self) -> None:
        result = updater.run_update(
            None,
            candidates=list(updater.KNOWN_UPDATABLE_SERVICES) + ["agent-zero"],
            dirty_check=lambda: False,
            dry_run=True,
        )
        acted = [e["service"] for e in result["acted_on"]]
        assert "agent-zero" not in acted


# ---------------------------------------------------------------------------
# Dirty-worktree abort
# ---------------------------------------------------------------------------
class TestDirtyWorktree:
    def test_dirty_worktree_aborts(self) -> None:
        result = updater.run_update(
            None,
            dirty_check=lambda: True,
            dry_run=True,
        )
        assert result["status"] == "aborted"
        assert "dirty" in result["reason"].lower()
        assert result["acted_on"] == []

    def test_clean_worktree_proceeds(self) -> None:
        result = updater.run_update(
            ["loki"],
            candidates=["loki"],
            dirty_check=lambda: False,
            dry_run=True,
        )
        assert result["status"] == "ok"

    def test_parse_worktree_paths(self) -> None:
        porcelain = (
            "worktree /repo/main\nHEAD abc123\nbranch refs/heads/main\n\n"
            "worktree /repo/feature\nHEAD def456\nbranch refs/heads/feat\n"
        )
        paths = updater.parse_worktree_paths(porcelain)
        assert paths == ["/repo/main", "/repo/feature"]


# ---------------------------------------------------------------------------
# Image-digest tolerance (docker may be absent)
# ---------------------------------------------------------------------------
class TestImageDigests:
    def test_tolerates_missing_docker(self) -> None:
        # Whatever the host state, this must return a dict and never raise.
        out = updater.check_image_digests(["loki"])
        assert "loki" in out
        assert set(out["loki"].keys()) >= {"digest", "expected", "match", "error"}


# ---------------------------------------------------------------------------
# check_git_rev — detached HEAD honesty (nit fix)
# ---------------------------------------------------------------------------
class TestCheckGitRevDetached:
    def test_detached_head_reports_behind_unknown(self, monkeypatch) -> None:
        import types

        calls = []

        def fake_run(cmd, cwd=None):
            calls.append(cmd)
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return types.SimpleNamespace(returncode=0, stdout="abc123\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return types.SimpleNamespace(returncode=0, stdout="HEAD\n")
            raise AssertionError(f"unexpected git call on detached HEAD: {cmd}")

        monkeypatch.setattr(updater, "_run", fake_run)
        out = updater.check_git_rev()
        assert out["branch"] == "HEAD"
        assert out["behind"] is None  # honest unknown, not a misleading bool
        assert out["ok"] is True
        assert "detached" in out["error"].lower()
        # ls-remote must NOT run on a detached HEAD
        assert not any(c[:2] == ["git", "ls-remote"] for c in calls)


# ---------------------------------------------------------------------------
# Skip-CHIT escape hatch is never silent (defense-in-depth)
# ---------------------------------------------------------------------------
class TestSkipChitWarns:
    def test_skip_logs_warning_when_dropping_chit(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="showtime.updater"):
            updater.evaluate_gate({"GOOGLE_SESSION_TOKEN": "x"}, skip_chit=True)
        assert any("bypass" in r.message.lower() for r in caplog.records)

    def test_no_warning_when_chit_present(self, caplog) -> None:
        env = {"CHIT_PASSPHRASE": "a-real-passphrase", "GOOGLE_SESSION_TOKEN": "x"}
        with caplog.at_level(logging.WARNING, logger="showtime.updater"):
            updater.evaluate_gate(env, skip_chit=True)
        assert not any("bypass" in r.message.lower() for r in caplog.records)


class TestPullFailureSummary:
    """run_update must NOT report ok when a service pull fails (Codex P2 on #1905)."""

    def test_failed_pull_yields_failed_status(self) -> None:
        result = updater.run_update(
            ["loki", "open-notebook"],
            candidates=["loki", "open-notebook"],
            dirty_check=lambda: False,
            executor=lambda svc: {"service": svc, "ok": svc != "open-notebook", "detail": ["x"]},
        )
        assert result["status"] == "failed"
        assert "open-notebook" in result["reason"]

    def test_all_ok_pull_yields_ok_status(self) -> None:
        result = updater.run_update(
            ["loki"],
            candidates=["loki"],
            dirty_check=lambda: False,
            executor=lambda svc: {"service": svc, "ok": True, "detail": ["x"]},
        )
        assert result["status"] == "ok"

    def test_executor_exception_yields_failed_status(self) -> None:
        def boom(svc: str) -> dict:
            raise RuntimeError("registry unreachable")

        result = updater.run_update(
            ["loki"],
            candidates=["loki"],
            dirty_check=lambda: False,
            executor=boom,
        )
        assert result["status"] == "failed"


class TestCanonicalServiceNames:
    """Default radius uses canonical compose service names (Codex P1 on #1905)."""

    def test_canonical_names_in_default_radius(self) -> None:
        assert "supabase-postgrest" in updater.SAFE_DEFAULT_BLAST_RADIUS
        # Non-canonical / legacy names must be gone.
        assert "supabase-rest" not in updater.SAFE_DEFAULT_BLAST_RADIUS
        assert "cipher-memory" not in updater.SAFE_DEFAULT_BLAST_RADIUS

    def test_cipher_api_is_forbidden_not_pulled(self) -> None:
        # cipher-api is agent-tier + build-only in compose: never in the pull radius,
        # and hard-forbidden (Codex follow-up on #1905).
        assert "cipher-api" not in updater.SAFE_DEFAULT_BLAST_RADIUS
        assert "cipher-api" not in updater.KNOWN_UPDATABLE_SERVICES
        assert "cipher-api" in updater.AGENT_TIER_SERVICES

    def test_default_radius_only_pullable_image_services(self) -> None:
        # Every default-radius service must be a registry-image (pullable) service.
        assert set(updater.SAFE_DEFAULT_BLAST_RADIUS) == {"loki", "open-notebook", "supabase-postgrest"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
