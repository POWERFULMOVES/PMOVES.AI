"""Tests for the compose-hardening ratchet.

The property under test is not "does it find things". It is the pair of
defects the tool replaces, because both were invisible in the old check's
output:

  1. A subject could fall through every branch and increment NO counter, so
     `112 passed, 43 warnings, 0 errors` under-reported its own denominator
     and a reader could not tell "all evaluated" from "some fell through".
     Asserted here as an EQUATION: passed + findings == services x properties.

  2. The only way to fail was the literal string `user: "0:0"`. A service with
     no `user:` at all, and a service whose `user:` is a name, both scored as
     not-a-failure. Both now fail, and the test names WHICH BUCKET each lands
     in rather than only that the totals look clean -- a bucket meaning "not
     applicable" is exactly what made the old instrument look fixed.

The fixtures are written to tmp_path, not to the real overlay: a test that
asserts against `pmoves/docker-compose.hardened.yml` changes its verdict every
time someone hardens a service, which is the opposite of a control.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "compose_hardening_ratchet.py"

spec = importlib.util.spec_from_file_location("compose_hardening_ratchet", MODULE)
assert spec and spec.loader
chr_mod = importlib.util.module_from_spec(spec)
sys.modules["compose_hardening_ratchet"] = chr_mod
spec.loader.exec_module(chr_mod)


HARDENED_BLOCK = """
    read_only: true
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
"""


def _overlay(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "docker-compose.hardened.yml"
    # NOT dedented: the hardened block is interpolated at its own indent,
    # and textwrap.dedent computes a common prefix across all lines, which
    # silently reflows the fixture into invalid YAML.
    path.write_text(body, encoding="utf-8")
    return path


def _baseline(tmp_path: Path, entries) -> Path:
    path = tmp_path / "baseline.yaml"
    lines = ["known_gaps:"] + [f'  - "{e}"' for e in entries]
    path.write_text("\n".join(lines) + "\n" if entries else "known_gaps: []\n", encoding="utf-8")
    return path


def _run(capsys, *argv) -> tuple[int, dict]:
    code = chr_mod.main(["--json", *argv])
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture()
def fixture_overlay(tmp_path: Path) -> Path:
    return _overlay(
        tmp_path,
        f"""services:
  svc-no-user:
    image: example/a{HARDENED_BLOCK}  svc-named-user:
    image: example/b
    user: nginx{HARDENED_BLOCK}  svc-root-user:
    image: example/c
    user: "0:0"{HARDENED_BLOCK}  svc-good:
    image: example/d
    user: "65532:65532"{HARDENED_BLOCK}secrets:
  a_secret_name:
    file: ./secret.txt
""",
    )


def test_a_secret_name_is_not_a_service(capsys, fixture_overlay, tmp_path):
    """M5: the overlay declares 4 services and 1 secret. Only 4 are subjects.

    The old discovery removed the top-level KEYS `services`/`secrets` by name
    and then validated their CHILDREN, so three secret names were scored for a
    missing `user:` and `read_only:`.
    """
    _, out = _run(capsys, "--file", str(fixture_overlay), "--baseline", str(_baseline(tmp_path, [])))
    assert out["services"] == 4
    assert not any(r["service"] == "a_secret_name" for r in out["records"])


def test_every_subject_lands_in_exactly_one_bucket(capsys, fixture_overlay, tmp_path):
    """The direct test for the silent fall-through.

    `svc-named-user` is the service the old regex dropped: it printed four
    lines where every other service printed five, and incremented nothing for
    the fifth.
    """
    _, out = _run(capsys, "--file", str(fixture_overlay), "--baseline", str(_baseline(tmp_path, [])))
    expected = out["services"] * out["properties"]
    assert out["evaluated"] == expected == 20
    assert out["passed"] + out["findings"] == expected
    pairs = {(r["service"], r["property"]) for r in out["records"]}
    assert len(pairs) == expected
    assert ("svc-named-user", "user") in pairs


@pytest.mark.parametrize(
    "service,kind",
    [
        ("svc-no-user", "NO_USER"),
        ("svc-named-user", "USER_NOT_NUMERIC"),
        ("svc-root-user", "ROOT_USER"),
    ],
)
def test_each_user_defect_fails_and_names_its_bucket(
    capsys, fixture_overlay, tmp_path, service, kind
):
    """Assert the BUCKET, not merely that the run went red.

    Under the old script only `svc-root-user` failed, and it failed only
    because its user was the literal string `0:0`.
    """
    code, out = _run(
        capsys, "--file", str(fixture_overlay), "--baseline", str(_baseline(tmp_path, []))
    )
    assert code == chr_mod.EXIT_FINDINGS
    assert f"{kind}|{service}" in out["new"]
    verdict = next(
        r for r in out["records"] if r["service"] == service and r["property"] == "user"
    )
    assert verdict["kind"] == kind


def test_a_fully_hardened_service_passes_every_property(capsys, fixture_overlay, tmp_path):
    _, out = _run(capsys, "--file", str(fixture_overlay), "--baseline", str(_baseline(tmp_path, [])))
    good = [r for r in out["records"] if r["service"] == "svc-good"]
    assert len(good) == len(chr_mod.PROPERTIES)
    assert {r["kind"] for r in good} == {"PASS"}


def test_baselined_findings_do_not_fail(capsys, fixture_overlay, tmp_path):
    baseline = _baseline(
        tmp_path,
        ["NO_USER|svc-no-user", "USER_NOT_NUMERIC|svc-named-user", "ROOT_USER|svc-root-user"],
    )
    code, out = _run(capsys, "--file", str(fixture_overlay), "--baseline", str(baseline))
    assert code == chr_mod.EXIT_CLEAN
    assert out["findings"] == 3 and out["baselined"] == 3 and out["new"] == []


def test_a_fixed_service_still_listed_is_STALE_and_fails(capsys, fixture_overlay, tmp_path):
    """Without this the baseline rots into a permanent allowlist."""
    baseline = _baseline(
        tmp_path,
        [
            "NO_USER|svc-no-user",
            "USER_NOT_NUMERIC|svc-named-user",
            "ROOT_USER|svc-root-user",
            "NO_READ_ONLY|svc-good",
        ],
    )
    code, out = _run(capsys, "--file", str(fixture_overlay), "--baseline", str(baseline))
    assert code == chr_mod.EXIT_FINDINGS
    assert out["stale"] == ["NO_READ_ONLY|svc-good"]


def test_an_entry_for_a_service_not_in_this_file_is_reported_not_failed(
    capsys, fixture_overlay, tmp_path
):
    """A baseline shared across branches must not fail on absent services."""
    baseline = _baseline(
        tmp_path,
        [
            "NO_USER|svc-no-user",
            "USER_NOT_NUMERIC|svc-named-user",
            "ROOT_USER|svc-root-user",
            "NO_USER|svc-not-declared-here",
        ],
    )
    code, out = _run(capsys, "--file", str(fixture_overlay), "--baseline", str(baseline))
    assert code == chr_mod.EXIT_CLEAN
    assert out["not_in_file"] == ["NO_USER|svc-not-declared-here"]
    assert out["stale"] == []


def test_compose_merge_tags_do_not_break_the_parse(tmp_path):
    """The real overlay uses `!override`; yaml.safe_load refuses it outright.

    That refusal is part of why the original check reached for grep, so a
    regression here would quietly push the tool back to exit 3.
    """
    path = _overlay(
        tmp_path,
        """services:
  svc:
    image: example/a
    user: "65532:65532"
    cap_drop: !override ["ALL"]
    read_only: true
    security_opt: ["no-new-privileges:true"]
""",
    )
    services = chr_mod.load_services(path)
    assert list(services) == ["svc"]
    assert chr_mod._verdict_cap_drop(services["svc"])[0] == ""


def test_a_missing_overlay_is_could_not_measure_not_a_pass(capsys, tmp_path):
    code = chr_mod.main(["--file", str(tmp_path / "nope.yml")])
    assert code == chr_mod.EXIT_CANNOT_MEASURE
    assert code != chr_mod.EXIT_CLEAN


def test_a_dropped_verdict_is_could_not_measure_not_a_smaller_pass(fixture_overlay):
    """The guard that makes the counter trustworthy.

    Simulated the way the defect actually occurs: a branch emits no verdict
    for one (service, property) pair. Reconcile must refuse rather than print
    a tidy, smaller summary -- which is precisely what the old script did.
    """
    services = chr_mod.load_services(fixture_overlay)
    records = chr_mod.evaluate(services)
    chr_mod.reconcile(services, records)  # intact: no raise
    with pytest.raises(chr_mod.CouldNotMeasure):
        chr_mod.reconcile(services, records[:-1])


def test_a_duplicated_verdict_is_also_could_not_measure(fixture_overlay):
    """Same count, wrong coverage: one pair twice and another not at all."""
    services = chr_mod.load_services(fixture_overlay)
    records = chr_mod.evaluate(services)
    doctored = records[:-1] + [dict(records[0])]
    assert len(doctored) == len(records)
    with pytest.raises(chr_mod.CouldNotMeasure):
        chr_mod.reconcile(services, doctored)


def test_the_shipped_baseline_has_no_new_and_no_stale_entries(capsys):
    """The tree as committed must be clean, or the workflow is red on arrival."""
    code, out = _run(capsys)
    assert out["new"] == []
    assert out["stale"] == []
    assert out["passed"] + out["findings"] == out["evaluated"]
    assert code == chr_mod.EXIT_CLEAN


def test_a_targeted_run_on_an_undeclared_service_is_could_not_measure(fixture_overlay):
    """The old script's answer to this was `0 passed, 0 warnings, 0 errors`,
    exit 0 -- a clean pass for a subject it never looked at. It is also the
    example invocation in pmoves/docs/operations/SCRIPTS_AND_TESTS_GUIDE.md,
    whose named service is not in the overlay at all.
    """
    code = chr_mod.main(["--file", str(fixture_overlay), "svc-does-not-exist"])
    assert code == chr_mod.EXIT_CANNOT_MEASURE


def test_a_targeted_run_does_not_call_other_services_missing(capsys, fixture_overlay, tmp_path):
    """Out-of-scope is its own bucket.

    Reporting "NOT IN THIS FILE" for a service that IS in the file would be
    the wrong-subject defect this tool exists to remove, re-entering through
    the baseline.
    """
    baseline = _baseline(
        tmp_path,
        ["NO_USER|svc-no-user", "USER_NOT_NUMERIC|svc-named-user", "ROOT_USER|svc-root-user"],
    )
    code, out = _run(
        capsys, "--file", str(fixture_overlay), "--baseline", str(baseline), "svc-good"
    )
    assert code == chr_mod.EXIT_CLEAN
    assert out["services"] == 1
    assert out["not_in_file"] == []
    assert out["stale"] == []
    assert sorted(out["out_of_scope"]) == [
        "NO_USER|svc-no-user",
        "ROOT_USER|svc-root-user",
        "USER_NOT_NUMERIC|svc-named-user",
    ]
