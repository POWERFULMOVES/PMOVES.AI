"""Unit tests for pmoves.services.common.branch_trail (AGNOTE4482 §9.4)."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from pmoves.services.common import branch_trail


# -----------------------------------------------------------------------
# encode_subject
# -----------------------------------------------------------------------


class TestEncodeSubject:
    def test_simple_branch(self) -> None:
        assert branch_trail.encode_subject("main") == "branch.main.trail.v1"

    def test_slash_to_dot(self) -> None:
        assert (
            branch_trail.encode_subject("feat/w6-bpm-nats")
            == "branch.feat.w6-bpm-nats.trail.v1"
        )

    def test_multiple_slashes(self) -> None:
        # `chore/codex/parity` → `branch.chore.codex.parity.trail.v1`
        assert (
            branch_trail.encode_subject("chore/codex/parity")
            == "branch.chore.codex.parity.trail.v1"
        )

    def test_dashes_and_underscores_pass_through(self) -> None:
        assert (
            branch_trail.encode_subject("fix/agent-zero_pyreqwest-pin")
            == "branch.fix.agent-zero_pyreqwest-pin.trail.v1"
        )

    @pytest.mark.parametrize(
        "bad",
        [
            "",  # empty
            "/leading-slash",  # starts with slash
            ".dotfile",  # starts with dot
            "branch with spaces",
            "branch*wildcard",  # NATS wildcard char
            "branch>terminator",  # NATS terminator char
            "branch\nnewline",
            "feat/",
            "feat//branch",
            "feat..branch",
            "feat/.branch",
        ],
    )
    def test_rejects_invalid(self, bad: str) -> None:
        with pytest.raises(ValueError, match="disallowed"):
            branch_trail.encode_subject(bad)

    def test_max_length(self) -> None:
        # 255-char branch name OK; 256-char rejected
        ok = "a" * 255
        too_long = "a" * 256
        assert branch_trail.encode_subject(ok).startswith("branch.")
        with pytest.raises(ValueError):
            branch_trail.encode_subject(too_long)


# -----------------------------------------------------------------------
# build_branch_event
# -----------------------------------------------------------------------


class TestBuildBranchEvent:
    def test_minimal(self) -> None:
        ev = branch_trail.build_branch_event("main", "create")
        assert ev["branch_name"] == "main"
        assert ev["event"] == "create"
        assert ev["ecosystem"] == "github"
        assert isinstance(ev["ts"], float)
        assert ev["pr_url"] is None
        assert ev["committer"] is None
        assert ev["sha"] is None
        assert ev["runner"] is None

    def test_full(self) -> None:
        ev = branch_trail.build_branch_event(
            "feat/x",
            "merge",
            pr_url="https://github.com/foo/bar/pull/1",
            committer="DARKXSIDE",
            sha="abc1234",
            ecosystem="gitlab",
            runner="self-hosted-z890",
            ts=1700000000.0,
        )
        assert ev["pr_url"] == "https://github.com/foo/bar/pull/1"
        assert ev["committer"] == "DARKXSIDE"
        assert ev["sha"] == "abc1234"
        assert ev["ecosystem"] == "gitlab"
        assert ev["runner"] == "self-hosted-z890"
        assert ev["ts"] == 1700000000.0

    @pytest.mark.parametrize("event", ["created", "PR", "deleted", "", "MERGE"])
    def test_rejects_unknown_event(self, event: str) -> None:
        with pytest.raises(ValueError, match="event must be one of"):
            branch_trail.build_branch_event("main", event)

    def test_rejects_unknown_ecosystem(self) -> None:
        with pytest.raises(ValueError, match="ecosystem must be one of"):
            branch_trail.build_branch_event("main", "create", ecosystem="azure-devops")

    def test_rejects_invalid_branch_name_early(self) -> None:
        # Should fail-fast before signing, not after
        with pytest.raises(ValueError, match="disallowed"):
            branch_trail.build_branch_event("invalid branch", "create")

    @pytest.mark.parametrize("event", ["link_pr", "merge"])
    @pytest.mark.parametrize("pr_url", [None, "", "   "])
    def test_rejects_pr_events_without_pr_url(
        self, event: str, pr_url: str | None
    ) -> None:
        with pytest.raises(ValueError, match="pr_url is required"):
            branch_trail.build_branch_event("main", event, pr_url=pr_url)

    def test_all_event_types_valid(self) -> None:
        for ev in branch_trail.EVENT_TYPES:
            kwargs = {}
            if ev in {"link_pr", "merge"}:
                kwargs["pr_url"] = "https://github.com/foo/bar/pull/1"
            out = branch_trail.build_branch_event("main", ev, **kwargs)
            assert out["event"] == ev


# -----------------------------------------------------------------------
# build_payload
# -----------------------------------------------------------------------


class TestBuildPayload:
    def test_unsigned_warns_but_returns_payload(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        with caplog.at_level("WARNING", logger="pmoves.services.common.branch_trail"):
            payload = branch_trail.build_payload(
                "feat/test", "create", "claude-opus"
            )
        assert "unsigned" in caplog.text.lower()
        assert payload["spec"] == "chit.cgp.v0.2"
        assert payload["type"] == "branch.lifecycle.v1"
        assert payload["branch_event"]["branch_name"] == "feat/test"
        assert payload["branch_event"]["event"] == "create"
        assert "agent_id" in payload  # from sign_trail.build_payload
        # No sig field when unsigned
        assert "sig" not in payload

    def test_signed_with_passphrase_param(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        payload = branch_trail.build_payload(
            "feat/test",
            "merge",
            "claude-opus",
            pr_url="https://example.com/pr/1",
            passphrase="test-passphrase-not-for-prod",
        )
        assert payload["sig"]["alg"] == "HMAC-SHA256"
        assert "hmac" in payload["sig"]
        assert payload["branch_event"]["pr_url"] == "https://example.com/pr/1"

    def test_signed_with_env_signing_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CHIT_SIGNING_KEY", "env-sourced-key")
        monkeypatch.delenv("CHIT_PASSPHRASE", raising=False)
        payload = branch_trail.build_payload("main", "create", "claude-opus")
        assert "sig" in payload

    def test_signed_with_env_legacy_passphrase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CHIT_SIGNING_KEY", raising=False)
        monkeypatch.setenv("CHIT_PASSPHRASE", "legacy-key")
        payload = branch_trail.build_payload("main", "create", "claude-opus")
        assert "sig" in payload

    def test_passphrase_param_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CHIT_SIGNING_KEY", "env-key")
        # Both produce sigs; we just verify passphrase=... wins by signing with
        # different keys and asserting the HMACs differ.
        env_signed = branch_trail.build_payload("main", "create", "claude-opus")
        param_signed = branch_trail.build_payload(
            "main", "create", "claude-opus", passphrase="different-key"
        )
        assert env_signed["sig"]["hmac"] != param_signed["sig"]["hmac"]

    def test_summary_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHIT_SIGNING_KEY", "k")
        payload = branch_trail.build_payload(
            "feat/foo",
            "merge",
            "claude-opus",
            pr_url="https://github.com/foo/bar/pull/1",
        )
        # Reuses sign_trail's payload skeleton — summary is the human-readable label
        assert payload["summary"] == "branch.lifecycle.merge on feat/foo"


# -----------------------------------------------------------------------
# emit (async, mocks publish_cgp)
# -----------------------------------------------------------------------


class TestEmit:
    def test_emit_calls_publish_cgp_with_encoded_subject(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CHIT_SIGNING_KEY", "k")
        monkeypatch.setenv("NATS_URL", "nats://test:4222")

        captured: dict[str, Any] = {}

        async def fake_publish_cgp(
            cgp_packet: dict, subject: str, nats_url: str = ""
        ) -> bool:
            captured["packet"] = cgp_packet
            captured["subject"] = subject
            captured["nats_url"] = nats_url
            return True

        with patch(
            "pmoves.services.common.nats_client.publish_cgp",
            side_effect=fake_publish_cgp,
        ):
            ok = asyncio.run(
                branch_trail.emit(
                    "feat/test-9-4",
                    "create",
                    "claude-opus",
                    committer="DARKXSIDE",
                    sha="abc1234",
                )
            )
        assert ok is True
        assert captured["subject"] == "branch.feat.test-9-4.trail.v1"
        assert captured["packet"]["type"] == "branch.lifecycle.v1"
        assert captured["packet"]["branch_event"]["committer"] == "DARKXSIDE"
        assert captured["packet"]["branch_event"]["sha"] == "abc1234"

    def test_emit_returns_false_on_publish_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CHIT_SIGNING_KEY", "k")

        async def fake_publish_cgp(*_args: Any, **_kwargs: Any) -> bool:
            return False

        with patch(
            "pmoves.services.common.nats_client.publish_cgp",
            side_effect=fake_publish_cgp,
        ):
            ok = asyncio.run(
                branch_trail.emit("main", "delete", "claude-opus")
            )
        assert ok is False

    def test_emit_passes_nats_url_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CHIT_SIGNING_KEY", "k")
        captured: dict[str, Any] = {}

        async def fake_publish_cgp(
            cgp_packet: dict, subject: str, nats_url: str = ""
        ) -> bool:
            captured["nats_url"] = nats_url
            return True

        with patch(
            "pmoves.services.common.nats_client.publish_cgp",
            side_effect=fake_publish_cgp,
        ):
            asyncio.run(
                branch_trail.emit(
                    "main",
                    "create",
                    "claude-opus",
                    nats_url="nats://override:4222",
                )
            )
        assert captured["nats_url"] == "nats://override:4222"

    def test_emit_fails_fast_on_invalid_branch(self) -> None:
        with pytest.raises(ValueError, match="disallowed"):
            asyncio.run(
                branch_trail.emit("invalid name", "create", "claude-opus")
            )

    def test_emit_fails_fast_on_invalid_event(self) -> None:
        with pytest.raises(ValueError, match="event must be one of"):
            asyncio.run(
                branch_trail.emit("main", "exploded", "claude-opus")
            )


# -----------------------------------------------------------------------
# Round-trip: subject → consumer can wildcard-match
# -----------------------------------------------------------------------


class TestSubjectRoundtrip:
    def test_wildcard_matches_all_branches(self) -> None:
        # Document the wildcard pattern that downstream consumers use
        for branch in ("main", "feat/x", "fix/y/z", "chore/a/b/c"):
            subject = branch_trail.encode_subject(branch)
            # Subject token count: ['branch', ...path_segments..., 'trail', 'v1']
            tokens = subject.split(".")
            assert tokens[0] == "branch"
            assert tokens[-2] == "trail"
            assert tokens[-1] == "v1"
            # At least one segment between branch. and .trail.v1
            assert len(tokens) >= 4

    def test_path_segments_match_slash_count(self) -> None:
        # `feat/x/y` → 3 path segments → 6 dot-tokens total
        # (`branch` prefix + 3 path segments + `trail` + `v1`)
        assert (
            len(branch_trail.encode_subject("feat/x/y").split("."))
            == 1 + 3 + 2
        )

    def test_subject_is_not_lossless_documented(self) -> None:
        # When a branch name contains `.`, the subject is ambiguous —
        # consumers must use payload `branch_event.branch_name` for the
        # canonical lossless name. Subject is for routing/wildcard only.
        # `feat/9.4-test` and `feat/9/4-test` produce the same subject form.
        assert branch_trail.encode_subject("feat/9.4-test") == "branch.feat.9.4-test.trail.v1"
        assert branch_trail.encode_subject("feat/9/4-test") == "branch.feat.9.4-test.trail.v1"
