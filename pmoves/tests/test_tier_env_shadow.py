"""Behavioural tests for the shadow half of tools/check_tier_envs.py.

The shadow check exists because Compose resolves interpolation from the process
environment BEFORE any --env-file, so an export outranks the whole secrets
pipeline. To say that truthfully it has to agree with Compose on two things it
originally did not:

  * WHICH FILES compose is actually reading (pmoves/Makefile:97-134). Missing
    tiers fall back to `.example`, and three optional overlays load AFTER every
    tier, so they outrank them.
  * WHAT VALUE each line means. This repo deliberately emits quoted values --
    tools/brand_defaults.py:114-120 quotes anything containing whitespace or
    `#` precisely because "both consumers strip surrounding double quotes".
    Comparing the raw text against a shell value that has already been
    unquoted reports a shadow that does not exist.

And the summary must never contradict the lines above it, in either half.

Every test runs against a tmp_path fixture directory. Nothing here reads or
writes the real env.shared or any real env.tier-* file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[2] / "pmoves" / "tools" / "check_tier_envs.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_tier_envs_under_test", CHECKER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mod = _load()

TIERS = mod.TIERS


@pytest.fixture()
def envdir(tmp_path, monkeypatch):
    """A fixture tree with every tier present, so tests opt in to absence."""
    for tier in TIERS:
        (tmp_path / f"env.tier-{tier}").write_text("PLACEHOLDER=1\n", encoding="utf-8")
        (tmp_path / f"env.tier-{tier}.example").write_text(
            "PLACEHOLDER=1\n", encoding="utf-8"
        )
    (tmp_path / "env.shared").write_text("PLACEHOLDER=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # The Makefile default. Tests that care set it themselves.
    monkeypatch.setenv("SUPABASE_RUNTIME", "compose")
    monkeypatch.delenv("INCLUDE_ENV_LOCAL_IN_COMPOSE", raising=False)
    return tmp_path


# --- dotenv value semantics ----------------------------------------------


class TestParseDotenvValue:
    def test_strips_surrounding_double_quotes(self):
        assert mod.parse_dotenv_value('"PMOVES Mesh"') == "PMOVES Mesh"

    def test_strips_surrounding_single_quotes(self):
        assert mod.parse_dotenv_value("'PMOVES Mesh'") == "PMOVES Mesh"

    def test_keeps_a_hash_inside_quotes(self):
        """A `#` in a quoted value is data, not a comment."""
        assert mod.parse_dotenv_value('"pa#ssword"') == "pa#ssword"

    def test_strips_an_inline_comment_from_an_unquoted_value(self):
        assert mod.parse_dotenv_value("plain   # trailing note") == "plain"

    def test_a_hash_with_no_leading_space_is_part_of_the_value(self):
        assert mod.parse_dotenv_value("pa#ss") == "pa#ss"

    def test_processes_escapes_only_inside_double_quotes(self):
        assert mod.parse_dotenv_value('"a\\"b"') == 'a"b'
        assert mod.parse_dotenv_value("'a\\\"b'") == 'a\\"b'

    def test_trims_surrounding_whitespace(self):
        assert mod.parse_dotenv_value("  spaced  ") == "spaced"

    def test_empty_value(self):
        assert mod.parse_dotenv_value("") == ""


class TestQuotedValueIsNotAShadow:
    def test_quoted_file_value_matching_unquoted_export_is_not_reported(
        self, envdir, monkeypatch
    ):
        """The false positive: brand_defaults quotes it, the shell unquotes it."""
        (envdir / "env.shared").write_text('BRAND_NAME="PMOVES Mesh"\n', encoding="utf-8")
        monkeypatch.setenv("BRAND_NAME", "PMOVES Mesh")
        assert mod.check_shadow() == [], (
            "an export that agrees with the file once both are read as dotenv "
            "is harmless and must not be reported"
        )

    def test_a_genuine_divergence_is_still_reported(self, envdir, monkeypatch):
        (envdir / "env.shared").write_text('BRAND_NAME="PMOVES Mesh"\n', encoding="utf-8")
        monkeypatch.setenv("BRAND_NAME", "Something Else")
        assert any("BRAND_NAME" in line for line in mod.check_shadow())

    def test_raw_quoted_export_is_reported_as_a_shadow(self, envdir, monkeypatch):
        """The inverse: exporting the raw spelling DOES change what compose sees."""
        (envdir / "env.shared").write_text('BRAND_NAME="PMOVES Mesh"\n', encoding="utf-8")
        monkeypatch.setenv("BRAND_NAME", '"PMOVES Mesh"')
        assert any("BRAND_NAME" in line for line in mod.check_shadow()), (
            "a literally-quoted export reaches the container with its quotes; "
            "comparing raw-to-raw made this compare equal"
        )


# --- the compose --env-file stack ----------------------------------------


class TestComposeEnvFiles:
    def test_missing_tier_falls_back_to_its_example(self, envdir):
        (envdir / "env.tier-llm").unlink()
        names = [p.name for p in mod.compose_env_files()]
        assert "env.tier-llm.example" in names
        assert "env.tier-llm" not in names

    def test_missing_primary_falls_back_to_its_example(self, envdir):
        (envdir / "env.shared").unlink()
        (envdir / "env.shared.example").write_text("A=1\n", encoding="utf-8")
        names = [p.name for p in mod.compose_env_files()]
        assert names[0] == "env.shared.example"

    def test_primary_is_first_and_tiers_follow_in_order(self, envdir):
        names = [p.name for p in mod.compose_env_files()]
        assert names[0] == "env.shared"
        assert names[1 : 1 + len(TIERS)] == [f"env.tier-{t}" for t in TIERS]

    def test_urlencoded_overlay_loads_after_every_tier(self, envdir):
        (envdir / "env.tier-supabase.urlencoded").write_text("A=1\n", encoding="utf-8")
        names = [p.name for p in mod.compose_env_files()]
        assert names[-1] == "env.tier-supabase.urlencoded"

    def test_env_local_is_opt_in_under_compose_runtime(self, envdir, monkeypatch):
        (envdir / ".env.local").write_text("A=1\n", encoding="utf-8")
        assert ".env.local" not in [p.name for p in mod.compose_env_files()]
        monkeypatch.setenv("INCLUDE_ENV_LOCAL_IN_COMPOSE", "1")
        assert ".env.local" in [p.name for p in mod.compose_env_files()]

    def test_env_local_loads_unconditionally_outside_compose_runtime(
        self, envdir, monkeypatch
    ):
        (envdir / ".env.local").write_text("A=1\n", encoding="utf-8")
        monkeypatch.setenv("SUPABASE_RUNTIME", "cli")
        assert ".env.local" in [p.name for p in mod.compose_env_files()]

    def test_supa_runtime_overlay_only_in_cli_runtime(self, envdir, monkeypatch):
        (envdir / "env.supa.runtime").write_text("A=1\n", encoding="utf-8")
        assert "env.supa.runtime" not in [p.name for p in mod.compose_env_files()]
        monkeypatch.setenv("SUPABASE_RUNTIME", "cli")
        assert "env.supa.runtime" in [p.name for p in mod.compose_env_files()]


class TestShadowUsesTheComposeStack:
    def test_export_shadowing_a_fallback_example_is_caught(self, envdir, monkeypatch):
        """A node that never ran secrets-funnel runs off the examples."""
        (envdir / "env.tier-llm").unlink()
        (envdir / "env.tier-llm.example").write_text("OLLAMA_HOST=a\n", encoding="utf-8")
        monkeypatch.setenv("OLLAMA_HOST", "b")
        report = mod.check_shadow()
        assert any("OLLAMA_HOST" in line for line in report), (
            "compose is reading the .example for this tier; an export "
            "shadowing it was invisible"
        )

    def test_divergence_from_an_overridden_tier_is_not_reported(
        self, envdir, monkeypatch
    ):
        """The overlay wins, so agreeing with the overlay is not a shadow."""
        (envdir / "env.tier-supabase").write_text("DB_URL=tier\n", encoding="utf-8")
        (envdir / "env.tier-supabase.urlencoded").write_text(
            "DB_URL=overlay\n", encoding="utf-8"
        )
        monkeypatch.setenv("DB_URL", "overlay")
        assert mod.check_shadow() == [], (
            "the export agrees with the file compose actually resolves last; "
            "reporting it would send the operator to unset a matching value"
        )

    def test_report_names_the_file_compose_resolves_last(self, envdir, monkeypatch):
        (envdir / "env.tier-supabase").write_text("DB_URL=tier\n", encoding="utf-8")
        (envdir / "env.tier-supabase.urlencoded").write_text(
            "DB_URL=overlay\n", encoding="utf-8"
        )
        monkeypatch.setenv("DB_URL", "shell")
        line = next(x for x in mod.check_shadow() if "DB_URL" in x)
        assert "env.tier-supabase.urlencoded" in line, (
            "naming a file the operator would then edit in vain"
        )


# --- the summary must not contradict the body -----------------------------


class TestSummaryHonesty:
    def _run(self, capsys, argv):
        rc = mod.main(argv)
        return rc, capsys.readouterr().out

    def test_drift_plus_shadow_does_not_claim_the_files_are_correct(
        self, envdir, monkeypatch, capsys
    ):
        """The reported defect: shadow_found won and denied the drift."""
        (envdir / "env.tier-api.example").write_text(
            "PLACEHOLDER=1\nMISSING_KEY=x\n", encoding="utf-8"
        )
        (envdir / "env.shared").write_text("SOME_KEY=filevalue\n", encoding="utf-8")
        monkeypatch.setenv("SOME_KEY", "shellvalue")

        rc, out = self._run(capsys, [])
        assert "MISSING_KEY" in out, "fixture did not produce drift -- test is stale"
        assert "SHADOWED" in out, "fixture did not produce shadow -- test is stale"
        assert "The files on disk are correct" not in out, (
            "the summary claims the files are correct immediately after listing "
            "a key missing from them"
        )
        assert "DRIFT" in out

    def test_shadow_only_still_says_the_files_are_correct(
        self, envdir, monkeypatch, capsys
    ):
        """That sentence is true when it is the ONLY finding, and stays."""
        (envdir / "env.shared").write_text("SOME_KEY=filevalue\n", encoding="utf-8")
        monkeypatch.setenv("SOME_KEY", "shellvalue")
        rc, out = self._run(capsys, [])
        assert "The files on disk are correct" in out

    def test_drift_only_summary_unchanged(self, envdir, capsys):
        (envdir / "env.tier-api.example").write_text(
            "PLACEHOLDER=1\nMISSING_KEY=x\n", encoding="utf-8"
        )
        rc, out = self._run(capsys, [])
        assert "DRIFT PRESENT" in out
        assert "no drift detected" not in out

    def test_clean_run_still_reports_clean(self, envdir, capsys):
        rc, out = self._run(capsys, [])
        assert rc == 0
        assert "no drift detected" in out

    def test_strict_fails_when_both_are_present(self, envdir, monkeypatch, capsys):
        (envdir / "env.tier-api.example").write_text(
            "PLACEHOLDER=1\nMISSING_KEY=x\n", encoding="utf-8"
        )
        (envdir / "env.shared").write_text("SOME_KEY=filevalue\n", encoding="utf-8")
        monkeypatch.setenv("SOME_KEY", "shellvalue")
        rc, out = self._run(capsys, ["--strict"])
        assert rc == 1
