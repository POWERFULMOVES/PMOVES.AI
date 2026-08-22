"""Every service requirements.txt line must survive CI's dependency collector.

python-tests.yml builds one `pip install` argv from every
`pmoves/services/*/requirements.txt`. It extracted the package name by splitting
on `[>=<[!~]` -- none of which appear in an UNVERSIONED line carrying an inline
comment:

    nats-py              # NATS bus integration

so the whole line became the package name and pip refused:

    Invalid requirement: 'nats-py              # NATS bus integration'

That took the REQUIRED python-tests gate down for every open PR at once. It
survived until then because a versioned line is truncated at its specifier
before the hash ever matters, so only that one shape triggers it.

This guards the data side: the workflow fix stops the collector mangling
comments, and this stops a requirements line arriving in a shape the collector
cannot render into a valid spec.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SERVICES = Path(__file__).resolve().parents[1] / "services"


# Mirrors python-tests.yml. `preserve_specs` there keeps the full spec; every
# other line is reduced to its bare NAME, which is why a `--hash=` line is fine
# in a requirements file and still lands on the pip argv as just the package.
PRESERVE = {"pyreqwest-impersonate"}


def _collect(text: str) -> list[str]:
    """Return the argv entries python-tests.yml would hand to `pip install`."""
    out = []
    for raw in text.splitlines():
        line = re.split(r"\s+#", raw.strip(), maxsplit=1)[0].strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[>=<\[!~]", line)[0].strip()
        if name.lower().replace("-", "_") in {
            s.lower().replace("-", "_") for s in PRESERVE
        }:
            out.append(line.split(" #", 1)[0].strip())
        else:
            out.append(name)
    return out


def _requirement_files() -> list[Path]:
    return sorted(SERVICES.glob("*/requirements.txt"))


def test_there_are_requirement_files_to_check():
    """A glob that silently matches nothing would make every test below vacuous."""
    assert _requirement_files(), f"no requirements.txt found under {SERVICES}"


@pytest.mark.parametrize(
    "req_file", _requirement_files(), ids=lambda p: p.parent.name
)
def test_every_line_yields_a_valid_requirement(req_file: Path):
    packaging = pytest.importorskip("packaging.requirements")
    bad = []
    for spec in _collect(req_file.read_text(encoding="utf-8")):
        try:
            packaging.Requirement(spec)
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{spec!r}: {exc}")
    assert not bad, (
        f"{req_file.relative_to(SERVICES.parent)} has lines CI cannot install:\n  "
        + "\n  ".join(bad)
    )


def test_the_collector_strips_an_inline_comment_from_an_unversioned_line():
    """The exact shape that broke it, pinned."""
    assert _collect("nats-py              # NATS bus integration") == ["nats-py"]
    assert _collect("requests   # why") == ["requests"]


def test_a_versioned_line_is_reduced_to_its_name():
    """CI deliberately drops pins so pip can resolve across services."""
    assert _collect("ruamel.yaml==0.19.1  # pinned") == ["ruamel.yaml"]


def test_a_hash_pinned_line_is_reduced_to_its_name():
    """`--hash=` is valid pip syntax but not a valid Requirement; the collector
    reduces it to the bare name, so it never reaches pip in that form."""
    assert _collect("prometheus-client==0.23.1 --hash=sha256:deadbeef") == [
        "prometheus-client"
    ]


def test_a_url_fragment_is_not_mistaken_for_a_comment():
    """pip needs whitespace before `#`, so an `egg=` fragment must survive the
    comment strip -- it is only the NAME split that trims it afterwards."""
    line = "pkg @ https://example.invalid/a.tar.gz#egg=pkg"
    assert re.split(r"\s+#", line, maxsplit=1)[0] == line


def test_full_line_comments_and_pip_options_are_skipped():
    assert _collect("# a note\n-r other.txt\n\npkg\n") == ["pkg"]


def test_the_workflow_itself_still_strips_inline_comments():
    """The tests above mirror the collector; they cannot catch it being re-broken.

    So assert directly on the workflow. A mirrored-logic test guards the DATA
    shape (a requirements line CI could not install); this guards the CODE. Both
    are needed -- the original bug was in the collector, and every test that
    reimplements it would have kept passing while CI stayed red.
    """
    wf = (
        Path(__file__).resolve().parents[2]
        / ".github" / "workflows" / "python-tests.yml"
    ).read_text(encoding="utf-8")
    assert r"re.split(r'\s+#', raw.strip(), maxsplit=1)" in wf, (
        "python-tests.yml must strip the inline comment BEFORE extracting the "
        "package name, or an unversioned dependency carrying a comment takes the "
        "required gate down for every open PR"
    )
