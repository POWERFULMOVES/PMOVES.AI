"""Pytest suite for pmoves.tools.secrets_funnel_populate.

Covers the fix-forward rewrite (2026-07-10): validation layer, deprecated-alias
migration, local.env merge delivery, and CGP bundle verification against the
real pmoves.chit codec (round-trip, no mocked bundle format).
"""

from pathlib import Path

import pytest

from pmoves.tools.secrets_funnel_populate import (
    DEPRECATED_ALIASES,
    KeyEntry,
    KeyStatus,
    ProviderCatalog,
    discover_keys,
    merge_into_local_env,
    validate_all,
    validate_key,
    verify_bundle,
)


def _entry(name: str, value: str) -> KeyEntry:
    return KeyEntry(name=name, value=value)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateKey:
    def test_valid_hf_token(self):
        e = validate_key(_entry("HF_TOKEN", "hf_" + "a" * 34))
        assert e.status == KeyStatus.ACTIVE
        assert e.error_message is None

    def test_invalid_format(self):
        e = validate_key(_entry("GROQ_API_KEY", "not-a-groq-key"))
        assert e.status == KeyStatus.INVALID
        assert "GROQ_API_KEY" in (e.error_message or "")

    def test_sentinel_value(self):
        e = validate_key(_entry("Z_AI_API_KEY", "unset-pending-key"))
        assert e.status == KeyStatus.EMPTY

    def test_missing_value(self):
        e = validate_key(_entry("MINIMAX_API_KEY", ""))
        assert e.status == KeyStatus.MISSING

    def test_deprecated_alias_with_value_migrates(self):
        e = validate_key(_entry("HUGGINGFACE_TOKEN", "hf_" + "b" * 34))
        assert e.name == "HF_TOKEN"
        assert e.status == KeyStatus.ACTIVE
        assert e.canonical_name == "HF_TOKEN"

    def test_deprecated_alias_empty_flags_canonical(self):
        e = validate_key(_entry("KIMI_API_KEY", ""))
        assert e.status == KeyStatus.EMPTY
        assert "MOONSHOT_API_KEY" in (e.error_message or "")

    def test_redaction_never_exposes_middle(self):
        secret = "sk-" + "z" * 40
        e = _entry("MOONSHOT_API_KEY", secret)
        red = e.redacted_value()
        assert secret not in red
        assert len(red) < len(secret)


class TestValidateAll:
    def test_reports_expected_keys_missing_from_source(self):
        validated = validate_all({})
        assert set(validated) == set(ProviderCatalog.all_expected_keys())
        assert all(e.status == KeyStatus.MISSING for e in validated.values())

    def test_alias_migration_lands_under_canonical_name(self):
        entries = {"ZAI_API_KEY": _entry("ZAI_API_KEY", "x" * 24)}
        validated = validate_all(entries)
        assert validated["Z_AI_API_KEY"].status == KeyStatus.ACTIVE
        assert "ZAI_API_KEY" not in validated


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverKeys:
    def test_reads_only_provider_keys(self, tmp_path: Path):
        src = tmp_path / "filled.env"
        src.write_text(
            "# comment\n"
            "HF_TOKEN=hf_" + "c" * 34 + "\n"
            "RANDOM_OTHER_VAR=hello\n"
            "GROQ_API_KEY=gsk_" + "d" * 30 + "\n"
        )
        entries = discover_keys(src)
        assert set(entries) == {"HF_TOKEN", "GROQ_API_KEY"}

    def test_missing_source_returns_empty(self, tmp_path: Path):
        assert discover_keys(tmp_path / "nope.env") == {}


# ---------------------------------------------------------------------------
# Delivery: local.env merge
# ---------------------------------------------------------------------------

class TestMergeIntoLocalEnv:
    def _active(self, name: str, value: str) -> KeyEntry:
        e = _entry(name, value)
        e.status = KeyStatus.ACTIVE
        return e

    def test_appends_new_key_and_preserves_other_lines(self, tmp_path: Path):
        target = tmp_path / "local.env"
        target.write_text("# keep me\nEXISTING=1\n")
        entries = {"HF_TOKEN": self._active("HF_TOKEN", "hf_" + "e" * 34)}
        results = merge_into_local_env(entries, local_env=target)
        assert results["HF_TOKEN"] is True
        content = target.read_text()
        assert "# keep me" in content
        assert "EXISTING=1" in content
        assert "HF_TOKEN=hf_" in content

    def test_updates_existing_key_in_place(self, tmp_path: Path):
        target = tmp_path / "local.env"
        target.write_text("HF_TOKEN=old-placeholder\nOTHER=x\n")
        entries = {"HF_TOKEN": self._active("HF_TOKEN", "hf_" + "f" * 34)}
        merge_into_local_env(entries, local_env=target)
        content = target.read_text()
        assert "old-placeholder" not in content
        assert content.count("HF_TOKEN=") == 1

    def test_drops_superseded_alias_line(self, tmp_path: Path):
        target = tmp_path / "local.env"
        target.write_text("HUGGINGFACE_TOKEN=hf_old\n")
        entries = {"HF_TOKEN": self._active("HF_TOKEN", "hf_" + "g" * 34)}
        merge_into_local_env(entries, local_env=target)
        content = target.read_text()
        assert "HUGGINGFACE_TOKEN" not in content
        assert "HF_TOKEN=hf_" in content

    def test_dry_run_writes_nothing(self, tmp_path: Path):
        target = tmp_path / "local.env"
        entries = {"HF_TOKEN": self._active("HF_TOKEN", "hf_" + "h" * 34)}
        results = merge_into_local_env(entries, local_env=target, dry_run=True)
        assert results["HF_TOKEN"] is True
        assert not target.exists()

    def test_skips_non_active_entries(self, tmp_path: Path):
        target = tmp_path / "local.env"
        bad = _entry("GROQ_API_KEY", "nope")
        bad.status = KeyStatus.INVALID
        results = merge_into_local_env({"GROQ_API_KEY": bad}, local_env=target)
        assert results["GROQ_API_KEY"] is False
        assert not target.exists()

    def test_written_file_is_owner_only(self, tmp_path: Path):
        target = tmp_path / "local.env"
        entries = {"HF_TOKEN": self._active("HF_TOKEN", "hf_" + "i" * 34)}
        merge_into_local_env(entries, local_env=target)
        assert (target.stat().st_mode & 0o777) == 0o600


# ---------------------------------------------------------------------------
# Verification: real CGP round-trip
# ---------------------------------------------------------------------------

class TestVerifyBundle:
    def test_round_trip_against_real_codec(self, tmp_path: Path):
        chit = pytest.importorskip("pmoves.chit")
        bundle = tmp_path / "env.cgp.json"
        payload = chit.encode_secret_map(
            {
                "HF_TOKEN": "hf_" + "j" * 34,
                "GROQ_API_KEY": "",  # present but empty -> not set
            }
        )
        chit.save_cgp(payload, bundle)
        results = verify_bundle(
            ["HF_TOKEN", "GROQ_API_KEY", "MOONSHOT_API_KEY"],
            bundle_path=bundle,
        )
        assert results["HF_TOKEN"] is True
        assert results["GROQ_API_KEY"] is False
        assert results["MOONSHOT_API_KEY"] is False

    def test_missing_bundle_reports_all_false(self, tmp_path: Path):
        results = verify_bundle(["HF_TOKEN"], bundle_path=tmp_path / "absent.json")
        assert results == {"HF_TOKEN": False}
