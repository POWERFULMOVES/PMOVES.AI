"""Shape rules are pydantic models over a tracked file, enforced at delivery.

Every credential-looking value in this file is FABRICATED here: the body is the
word FAKE plus zeros. None resembles, derives from, or was checked against a
real key. Bodies carry digits on purpose -- an all-letter body after `hf_` is
the shape GitHub push protection scans for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pmoves.tools import secret_shape_rules as rules_mod
from pmoves.tools import secrets_sync
from pmoves.tools.secret_shape_rules import (
    ManifestShape,
    RulesFileError,
    ShapeRule,
    load_rules,
    parse_rules,
)

FILE = "env.tier-llm"

WELL_FORMED = {
    "HF_TOKEN": "hf_FAKE" + "0" * 30,
    "ANTHROPIC_API_KEY": "sk-ant-api03-FAKE-" + "0" * 60,
    "OPENAI_API_KEY": "sk-proj-FAKE-" + "0" * 40,
    "GEMINI_API_KEY": "AIzaFAKE" + "0" * 31,
    "GITHUB_PAT": "github_pat_FAKE_" + "0" * 60,
    "GH_TOKEN": "gho_FAKE" + "0" * 32,
    "GHCR_TOKEN": "ghp_FAKE" + "0" * 32,
    "TAILSCALE_API_KEY": "tskey-api-FAKE-" + "0" * 30,
}


def _entry(label: str, *, required: bool = False, min_length: int = 0, prefix: str = ""):
    return secrets_sync.Entry(
        id=label.lower(),
        label=label,
        required=required,
        targets=[secrets_sync.Target(file=FILE, key=label)],
        min_length=min_length,
        prefix=prefix,
    )


def _windows(value: str, width: int = 6):
    return {value[i:i + width] for i in range(len(value) - width + 1)}


# ── The tracked rules file ───────────────────────────────────────────────────


def test_tracked_rules_file_loads_and_covers_the_rotated_providers():
    rules = load_rules()
    assert set(WELL_FORMED) <= set(rules), sorted(set(WELL_FORMED) - set(rules))


def test_every_rule_cites_an_https_doc():
    for label, rule in load_rules().items():
        assert rule.docs, f"{label} has no doc citation"
        assert all(url.startswith("https://") for url in rule.docs)


def test_no_rule_invents_an_exact_length():
    """No provider in the set publishes one; the model only admits documented ones."""
    assert all(rule.exact_length is None for rule in load_rules().values())


@pytest.mark.parametrize("label", sorted(WELL_FORMED))
def test_a_well_formed_fabricated_value_passes_its_rule(label):
    """Positive control for every rule, so a withheld value below means withheld."""
    assert load_rules()[label].check(WELL_FORMED[label]) == []


# GitHub's documented user/app token forms. gho_ is what `gh auth token` yields
# after the default browser login; the stateless installation token form
# (ghs_APPID_JWT) carries JWT punctuation and is not 40 characters.
GH_OAUTH = "gho_FAKE" + "0" * 32
GH_APP_USER = "ghu_FAKE" + "0" * 32
GH_INSTALLATION_STATELESS = "ghs_123456_FAKEhdr0.FAKEpayload0-0000.FAKEsig_0000"


@pytest.mark.parametrize("value", [GH_OAUTH, GH_APP_USER])
def test_github_pat_admits_the_gh_cli_token_forms(value):
    assert load_rules()["GITHUB_PAT"].check(value) == []


@pytest.mark.parametrize(
    "value", [GH_OAUTH, GH_APP_USER, GH_INSTALLATION_STATELESS, WELL_FORMED["GITHUB_PAT"]]
)
@pytest.mark.parametrize("label", ["GHCR_TOKEN", "GH_TOKEN"])
def test_ghcr_and_gh_token_admit_every_github_token_form(label, value):
    """The prefix catches corruption; read:packages (provider-verify) decides GHCR."""
    assert load_rules()[label].check(value) == []


def test_a_github_token_missing_its_prefix_is_still_withheld():
    finding = load_rules()["GITHUB_PAT"].check(GH_OAUTH[1:])
    assert finding and "prefix-match no" in finding[0]


def test_the_rules_file_holds_no_value_shaped_string():
    """Rules only. A prefix followed by a long token body would be a pasted key."""
    text = rules_mod.DEFAULT_RULES_PATH.read_text()
    import re

    prefixes = [p for rule in load_rules().values() for p in rule.prefixes]
    for prefix in prefixes:
        assert not re.search(re.escape(prefix) + r"[A-Za-z0-9_-]{16,}", text), prefix


# ── Malformed rules -> exit 3 ────────────────────────────────────────────────

MALFORMED = {
    "unknown_field": "version: 1\nrules:\n  - label: HF_TOKEN\n    value: hf_FAKE0000\n",
    "invented_exact_length": (
        "version: 1\nrules:\n  - label: HF_TOKEN\n    exact_length: 37\n"
        "    length_source: floor\n"
    ),
    "length_without_source": "version: 1\nrules:\n  - label: HF_TOKEN\n    min_length: 30\n",
    "bad_regex": "version: 1\nrules:\n  - label: HF_TOKEN\n    charset: '^[A-Z'\n",
    "charset_not_a_single_class": (
        "version: 1\nrules:\n  - label: HF_TOKEN\n    charset: '^hf_[A-Za-z0-9]+$'\n"
    ),
    "duplicate_label": "version: 1\nrules:\n  - label: HF_TOKEN\n  - label: HF_TOKEN\n",
    "bool_min_length": (
        "version: 1\nrules:\n  - label: HF_TOKEN\n    min_length: true\n"
        "    length_source: floor\n"
    ),
    "http_doc": "version: 1\nrules:\n  - label: HF_TOKEN\n    docs: ['http://example.com']\n",
    "wrong_version": "version: 2\nrules: []\n",
    "not_yaml": "version: 1\nrules: [\n",
    "not_a_mapping": "- just\n- a list\n",
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_a_malformed_rules_file_exits_3(tmp_path, name, capsys):
    path = tmp_path / "secret_shapes.yaml"
    path.write_text(MALFORMED[name])
    assert rules_mod.main(["--rules", str(path)]) == 3
    assert "COULD-NOT-MEASURE" in capsys.readouterr().err


def test_a_missing_rules_file_exits_3(tmp_path):
    assert rules_mod.main(["--rules", str(tmp_path / "absent.yaml")]) == 3


def test_the_funnel_stops_with_exit_3_before_decoding_when_rules_are_malformed(monkeypatch, capsys):
    """Rules load FIRST: a malformed file must stop secrets_sync before the manifest."""

    def broken(*_a, **_k):
        raise RulesFileError("synthetic: rules file fails the model")

    def must_not_run(*_a, **_k):
        raise AssertionError("manifest read after a rules failure")

    monkeypatch.setattr(secrets_sync, "load_rules", broken)
    monkeypatch.setattr(secrets_sync, "load_manifest", must_not_run)
    assert secrets_sync.main(["report"]) == 3
    assert "COULD-NOT-MEASURE" in capsys.readouterr().err


def test_good_rules_parse_and_describe_public_facts_only():
    ruleset = parse_rules(
        "version: 1\nrules:\n  - label: HF_TOKEN\n    prefixes: ['hf_']\n"
        "    min_length: 30\n    length_source: floor\n"
        "    docs: ['https://huggingface.co/docs/hub/security-tokens']\n"
    )
    rule = ruleset.by_label()["HF_TOKEN"]
    assert rule.expected() == "prefix 'hf_'; >= 30 chars (floor)"


def test_exact_length_is_admitted_only_when_documented():
    assert ShapeRule(label="X", exact_length=40, length_source="documented").exact_length == 40
    with pytest.raises(ValueError):
        ShapeRule(label="X", exact_length=40, length_source="example")


# ── Enforcement at delivery ──────────────────────────────────────────────────

HF_LEADING_TRUNCATION = WELL_FORMED["HF_TOKEN"][1:]       # 'f_...', the E2B shape
HF_TRAILING_TRUNCATION = WELL_FORMED["HF_TOKEN"][:20]     # prefix intact, short


@pytest.mark.parametrize("value", [HF_LEADING_TRUNCATION, HF_TRAILING_TRUNCATION])
def test_a_truncated_value_is_withheld_removed_and_named(value, capsys):
    rejected: dict = {}
    outputs, missing = secrets_sync.build_outputs(
        {"HF_TOKEN": value}, [_entry("HF_TOKEN", required=True)],
        strict=False, rejected_out=rejected,
    )
    assert "HF_TOKEN" not in outputs.get(FILE, {})
    assert "HF_TOKEN" in rejected[FILE], "merge mode must DELETE it, not leave it"
    assert missing == ["HF_TOKEN"]

    err = capsys.readouterr().err
    assert "HF_TOKEN: expected prefix 'hf_'" in err
    assert f"observed {len(value)} chars" in err
    expect_prefix = "no" if value is HF_LEADING_TRUNCATION else "yes"
    assert f"prefix-match {expect_prefix}" in err
    leaked = sorted(w for w in _windows(value) if w in err and "0000" not in w)
    assert not leaked, f"operator message leaks value fragment(s) {leaked}"


def test_a_well_formed_value_is_delivered():
    outputs, missing = secrets_sync.build_outputs(
        {"HF_TOKEN": WELL_FORMED["HF_TOKEN"]}, [_entry("HF_TOKEN", required=True)], strict=True
    )
    assert outputs[FILE]["HF_TOKEN"] == WELL_FORMED["HF_TOKEN"]
    assert missing == []


def test_charset_mismatch_reports_position_not_character(capsys):
    value = WELL_FORMED["HF_TOKEN"][:10] + "." + WELL_FORMED["HF_TOKEN"][11:]
    secrets_sync.build_outputs({"HF_TOKEN": value}, [_entry("HF_TOKEN")], strict=False)
    err = capsys.readouterr().err
    assert "charset-match no (first mismatch at position 11)" in err


def test_the_manifest_rule_and_the_file_rule_both_apply():
    """Neither loosens the other: a manifest floor above the file floor still withholds."""
    value = WELL_FORMED["HF_TOKEN"]  # passes the file rule, 37 chars
    outputs, _ = secrets_sync.build_outputs(
        {"HF_TOKEN": value}, [_entry("HF_TOKEN", min_length=64)], strict=False
    )
    assert "HF_TOKEN" not in outputs.get(FILE, {})


def test_labels_without_a_rule_are_untouched():
    outputs, _ = secrets_sync.build_outputs(
        {"SOME_UNRULED_LABEL": "tiny"}, [_entry("SOME_UNRULED_LABEL")], strict=True
    )
    assert outputs[FILE]["SOME_UNRULED_LABEL"] == "tiny"


def test_explicit_rules_override_the_tracked_file():
    outputs, _ = secrets_sync.build_outputs(
        {"HF_TOKEN": HF_LEADING_TRUNCATION}, [_entry("HF_TOKEN")], strict=False, rules={}
    )
    assert outputs[FILE]["HF_TOKEN"] == HF_LEADING_TRUNCATION


# ── The manifest's own fields go through the model too ──────────────────────


def test_manifest_shape_rejects_a_bool_min_length(tmp_path):
    manifest = tmp_path / "m.yaml"
    manifest.write_text(
        "version: 1\ncgp_file: x.cgp\nentries:\n"
        "  - id: e\n    source: {type: cgp, label: E}\n"
        "    targets: [{file: env.tier-x, key: E}]\n    min_length: true\n"
    )
    with pytest.raises(ValueError, match="non-integer min_length"):
        secrets_sync.load_manifest(manifest)


def test_manifest_shape_becomes_the_same_rule_type():
    rule = ManifestShape(min_length=40, prefix="e2b_").as_rule("E2B_API_KEY")
    assert isinstance(rule, ShapeRule)
    assert rule.violations("b_" + "0" * 40) == frozenset({"prefix"})
    assert ManifestShape().as_rule("X") is None


def test_pydantic_is_declared_where_the_funnel_gate_probes_for_it():
    """env-bootstrap-check reads requirements-lite.txt; undeclared = unprobed."""
    lite = Path(rules_mod.__file__).with_name("requirements-lite.txt").read_text()
    assert any(line.strip().startswith("pydantic") for line in lite.splitlines())


def test_charset_position_is_exact_for_a_class_with_escapes():
    rule = ShapeRule(label="X", charset=r"^[A-Za-z0-9_\-]+$")
    assert "first mismatch at position 3" in rule.check("ab.c")[0]


# ── The gh-CLI injector -> funnel path (review P1 on #3432) ──────────────────


def test_a_gho_token_from_the_gh_cli_injector_reaches_the_tier_file(tmp_path, monkeypatch):
    """`make gha-token-refresh`: injector writes `gh auth token`, then the funnel runs.

    After `gh auth login`'s browser flow that token is gho_. A GITHUB_PAT rule
    admitting only ghp_/github_pat_ withheld it, and github-runner-ctl lost its
    credential at the next refresh. Exercise the real injector, then the real
    funnel, on the same fabricated value.
    """
    from pmoves.tools import inject_github_pat_from_gh_cli as injector

    stored_at = tmp_path / "injected_pat.txt"
    monkeypatch.setattr(injector, "get_gh_token", lambda: GH_OAUTH)
    monkeypatch.setattr(injector, "validate_token_behaviorally", lambda token, repo: True)
    with pytest.raises(SystemExit) as refreshed:
        injector.refresh_if_stale(stored_at, "owner/repo", True)
    assert refreshed.value.code == injector.EXIT_REFRESHED

    delivered = injector.read_stored_pat(stored_at)
    assert delivered == GH_OAUTH

    rejected: dict = {}
    outputs, missing = secrets_sync.build_outputs(
        {"GITHUB_PAT": delivered},
        [_entry("GITHUB_PAT", required=True)],
        strict=True,
        rejected_out=rejected,
    )
    assert outputs[FILE]["GITHUB_PAT"] == GH_OAUTH
    assert missing == [] and rejected == {}


# ── Manifest fields are model-owned: label, required (review P2/P3) ─────────


def _manifest(tmp_path, entry_yaml: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        "version: 1\ncgp_file: x.cgp\nentries:\n" + entry_yaml
    )
    return path


DASHED_LABEL = (
    "  - id: dashed\n    source: {type: cgp, label: SOME-LABEL}\n"
    "    targets: [{file: env.tier-x, key: SOME_LABEL}]\n"
)
QUOTED_FALSE = (
    "  - id: quoted\n    source: {type: cgp, label: SOME_LABEL}\n"
    "    targets: [{file: env.tier-x, key: SOME_LABEL}]\n    required: 'false'\n"
)


def test_a_label_that_is_not_an_env_var_name_is_refused_at_load(tmp_path):
    with pytest.raises(ValueError, match="not an env-var name"):
        secrets_sync.load_manifest(_manifest(tmp_path, DASHED_LABEL))


def test_a_quoted_false_required_is_refused_not_read_as_true(tmp_path):
    with pytest.raises(ValueError, match="non-boolean required"):
        secrets_sync.load_manifest(_manifest(tmp_path, QUOTED_FALSE))


def test_a_real_bool_required_still_parses(tmp_path):
    body = QUOTED_FALSE.replace("required: 'false'", "required: false")
    _, entries = secrets_sync.load_manifest(_manifest(tmp_path, body))
    assert entries[0].required is False


@pytest.mark.parametrize("body", [DASHED_LABEL, QUOTED_FALSE])
def test_the_funnel_exits_3_with_a_message_on_a_malformed_manifest(tmp_path, body, capsys):
    """Not exit 1 with a traceback from deep inside build_outputs."""
    path = _manifest(tmp_path, body)
    assert secrets_sync.main(["report", "--manifest", str(path)]) == 3
    assert "COULD-NOT-MEASURE" in capsys.readouterr().err


def test_inspect_value_no_longer_builds_a_model_from_the_label():
    """A hand-built Entry with an odd label must not crash the charset scan."""
    from pmoves.tools.secret_shape import inspect_value

    verdict = inspect_value("odd-label.x", "b_" + "0" * 40, prefix="e2b_")
    assert len(verdict.withhold) == 1


@pytest.mark.parametrize("command", ["status", "generate"])
def test_onboarding_helper_exits_3_on_a_rules_failure(monkeypatch, command, capsys):
    from pmoves.tools import onboarding_helper

    def broken(*_a, **_k):
        raise RulesFileError("synthetic: rules file fails the model")

    monkeypatch.setattr(onboarding_helper, "cmd_status", broken)
    monkeypatch.setattr(onboarding_helper, "cmd_generate", broken)
    assert onboarding_helper.main([command]) == 3
    assert "COULD-NOT-MEASURE" in capsys.readouterr().err
