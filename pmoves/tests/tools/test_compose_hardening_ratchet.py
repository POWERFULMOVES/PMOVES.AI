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

  3. The tool read the overlay ALONE, so every service came back
     NO_RESOURCE_LIMITS -- a property the overlay carries for nobody, because
     sizing is declared in the base stack and merged at deploy time. All 28
     findings were FALSE. Fixing that by widening what is read can trivially
     produce a check that never fires, so the control for it is POSITIVE:
     `test_removing_a_real_base_limit_still_fails_and_names_the_service`
     strips a limit that only the base declares and requires the tool to flag
     that service BY NAME and exit 1. If that test ever passes-by-being-green,
     the fix has become blindness wearing the costume of a repair.

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
    """Run the tool, keeping tmp_path fixtures isolated from the real tree.

    A run that names its own `--file` gets `--no-base` unless it asked for a
    base, because the default base is the repository's six-file STACK_FILES
    chain. Merging that into a four-service fixture would make a unit test's
    verdict depend on the working tree -- the exact coupling this file's
    docstring refuses. `_run(capsys)` with no argv still exercises the real
    overlay against the real base, which is what the shipped-tree test wants.
    """
    argv = list(argv)
    if "--file" in argv and not {"--base", "--no-base"} & set(argv):
        argv.append("--no-base")
    code = chr_mod.main(["--json", *argv])
    return code, json.loads(capsys.readouterr().out)


# A service block carrying every hardening property EXCEPT sizing -- the shape
# the real overlay actually has, since `deploy:` lives in the base.
OVERLAY_ONLY_BLOCK = """
    read_only: true
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
"""


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


# =============================================================================
# Merged-config scope. The overlay says WHO is judged; the base stack it is
# deployed on says WHAT is read.
# =============================================================================


def _split_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """An overlay with no sizing and a base that has it -- the real shape.

    The base also declares a service the overlay does not, because the real
    base declares 111 services against the overlay's 28 and the merge must not
    let those extras become subjects.
    """
    overlay = _overlay(
        tmp_path,
        f"""services:
  svc-a:
    user: "65532:65532"{OVERLAY_ONLY_BLOCK}  svc-b:
    user: "65532:65532"{OVERLAY_ONLY_BLOCK}""",
    )
    base = tmp_path / "docker-compose.yml"
    base.write_text(
        """services:
  svc-a:
    image: example/a
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
  svc-b:
    image: example/b
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
  svc-not-hardened:
    image: example/c
""",
        encoding="utf-8",
    )
    return overlay, base


def test_a_property_declared_only_in_the_base_is_found(capsys, tmp_path):
    """The defect itself: 28 services flagged for limits they demonstrably had.

    Live on B850 while every one of them was a 'finding' --
    extract-worker Memory=536870912, archon Memory=2147483648,
    ffmpeg-whisper Memory=8589934592.
    """
    overlay, base = _split_fixture(tmp_path)
    code, out = _run(
        capsys,
        "--file",
        str(overlay),
        "--base",
        str(base),
        "--baseline",
        str(_baseline(tmp_path, [])),
    )
    assert code == chr_mod.EXIT_CLEAN
    limits = [r for r in out["records"] if r["property"] == "resource_limits"]
    assert len(limits) == 2
    assert {r["kind"] for r in limits} == {"PASS"}


def test_the_same_overlay_read_alone_reports_the_false_finding(capsys, tmp_path):
    """The before/after pair, in one assertion rather than two runs of prose.

    Identical overlay. `--no-base` is the pre-2026-09-21 scope, and it produces
    the false NO_RESOURCE_LIMITS for both services -- which is why the fix is
    scope and not a verdict change.
    """
    overlay, _ = _split_fixture(tmp_path)
    code, out = _run(
        capsys, "--file", str(overlay), "--baseline", str(_baseline(tmp_path, []))
    )
    assert code == chr_mod.EXIT_FINDINGS
    assert sorted(out["new"]) == ["NO_RESOURCE_LIMITS|svc-a", "NO_RESOURCE_LIMITS|svc-b"]


def test_removing_a_real_base_limit_still_fails_and_names_the_service(capsys, tmp_path):
    """POSITIVE CONTROL. The one test this whole change stands or falls on.

    Broadening scope to clear 28 false findings can trivially produce a check
    that never fires, and a check that never fires is indistinguishable from a
    clean tree in every summary line the tool prints. So: take a limit that
    ONLY the base declares, remove it, and require the tool to still exit 1 and
    to name the service -- not merely to go red, which a stale baseline entry
    would also do.
    """
    overlay, base = _split_fixture(tmp_path)
    sabotaged = base.read_text(encoding="utf-8").replace(
        """  svc-b:
    image: example/b
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
""",
        """  svc-b:
    image: example/b
""",
    )
    assert "svc-b" in sabotaged and 'memory: 1G' not in sabotaged
    base.write_text(sabotaged, encoding="utf-8")

    code, out = _run(
        capsys,
        "--file",
        str(overlay),
        "--base",
        str(base),
        "--baseline",
        str(_baseline(tmp_path, [])),
    )
    assert code == chr_mod.EXIT_FINDINGS
    assert out["new"] == ["NO_RESOURCE_LIMITS|svc-b"]
    verdict = next(
        r
        for r in out["records"]
        if r["service"] == "svc-b" and r["property"] == "resource_limits"
    )
    assert verdict["kind"] == "NO_RESOURCE_LIMITS"
    # svc-a is untouched: the control moved ONE service between buckets, it did
    # not turn the whole run red.
    assert out["passed"] + out["findings"] == out["evaluated"]
    assert out["findings"] == 1


def test_the_merge_does_not_enlarge_the_denominator(capsys, tmp_path):
    """The base declares services the overlay does not. They are NOT subjects.

    Widening the subject set would not be a fix for a false negative, it would
    be a different check under the same name -- and it would put the gate's
    denominator at the mercy of any file added to STACK_FILES.
    """
    overlay, base = _split_fixture(tmp_path)
    code, out = _run(
        capsys,
        "--file",
        str(overlay),
        "--base",
        str(base),
        "--baseline",
        str(_baseline(tmp_path, [])),
    )
    assert code == chr_mod.EXIT_CLEAN
    assert out["services"] == 2
    assert out["evaluated"] == 2 * len(chr_mod.PROPERTIES)
    assert not any(r["service"] == "svc-not-hardened" for r in out["records"])


def test_a_missing_base_file_is_could_not_measure_not_a_pass(tmp_path):
    """Fail closed. A base that cannot be read must not resolve to 'absent'.

    Silently skipping an unreadable input is how a property comes back unfound
    and reads as a finding, or how a whole stack goes unread and reads clean.
    """
    overlay, _ = _split_fixture(tmp_path)
    code = chr_mod.main(
        ["--file", str(overlay), "--base", str(tmp_path / "gone.yml")]
    )
    assert code == chr_mod.EXIT_CANNOT_MEASURE
    assert code != chr_mod.EXIT_CLEAN


def test_an_overlay_value_wins_over_the_base(capsys, tmp_path):
    """Merge direction. A base that runs as root must not survive the overlay."""
    overlay, base = _split_fixture(tmp_path)
    base.write_text(
        base.read_text(encoding="utf-8").replace(
            "  svc-a:\n    image: example/a\n",
            '  svc-a:\n    image: example/a\n    user: "0:0"\n    read_only: false\n',
        ),
        encoding="utf-8",
    )
    code, out = _run(
        capsys,
        "--file",
        str(overlay),
        "--base",
        str(base),
        "--baseline",
        str(_baseline(tmp_path, [])),
    )
    assert code == chr_mod.EXIT_CLEAN
    svc_a = {r["property"]: r["kind"] for r in out["records"] if r["service"] == "svc-a"}
    assert svc_a["user"] == "PASS"
    assert svc_a["read_only"] == "PASS"


def test_the_shipped_overlay_resolves_every_service_against_the_real_base(capsys):
    """The tree as committed, at the real scope the gate runs at.

    Named separately from the baseline test because they can fail for opposite
    reasons: that one goes red if the baseline rots, this one goes red if the
    merged resolution stops finding what the deployed stack actually declares.
    """
    code, out = _run(capsys)
    assert code == chr_mod.EXIT_CLEAN
    assert out["base"], "the gate must not be running at --no-base scope"
    limits = [r for r in out["records"] if r["property"] == "resource_limits"]
    assert len(limits) == out["services"]
    assert {r["kind"] for r in limits} == {"PASS"}
