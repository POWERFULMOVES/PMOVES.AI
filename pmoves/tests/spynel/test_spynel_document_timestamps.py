"""Ratchet: timestamps in Spynel task and goal documents are well-formed UTC instants.

Guards the contract stated in `.spynel/tasks/AGENTS.md` § "Schema reference".

Deliberately NOT asserted: that timestamps are *quoted*. Spynel's own writes are not
uniformly quoted (measured 2026-09-21: three `created_at` values are bare, so PyYAML
resolves them to `datetime` rather than `str`), and both forms denote the same instant.
The doc states quoting as the convention; this test asserts the instant-level invariant
that actually breaks dispatch when violated.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SPYNEL_ROOTS = (REPO_ROOT / ".spynel" / "tasks", REPO_ROOT / ".spynel" / "goals")

# RFC 3339, explicit Z, second precision (optional fractional seconds).
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def _documents() -> list[Path]:
    return sorted(
        p
        for root in SPYNEL_ROOTS
        if root.is_dir()
        for p in root.rglob("*.md")
        if p.name != "AGENTS.md"
    )


def _front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        pytest.fail(f"{path}: no YAML front matter")
    end = text.find("\n---", 3)
    if end == -1:
        pytest.fail(f"{path}: unterminated YAML front matter")
    data = yaml.safe_load(text[4:end])
    if not isinstance(data, dict):
        pytest.fail(f"{path}: front matter is not a mapping")
    return data


def _timestamp_fields(node, prefix: str = ""):
    """Yield (dotted_name, value) for every key ending in `_at`, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            name = f"{prefix}{key}"
            if str(key).endswith("_at"):
                yield name, value
            yield from _timestamp_fields(value, f"{name}.")


def _instant(name: str, value, path: Path) -> dt.datetime:
    """Normalize a timestamp to an aware UTC datetime, or fail with the offending value."""
    if isinstance(value, dt.datetime):
        # Unquoted in YAML. Accepted, but it must still carry an explicit UTC offset.
        if value.tzinfo is None or value.utcoffset() != dt.timedelta(0):
            pytest.fail(f"{path}: {name}={value!r} lacks an explicit UTC (Z) offset")
        return value
    if isinstance(value, str):
        if not RFC3339_Z.match(value):
            pytest.fail(
                f"{path}: {name}={value!r} is not RFC 3339 with an explicit Z UTC offset"
            )
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    pytest.fail(f"{path}: {name}={value!r} is not a timestamp")


if not _documents():
    pytestmark = pytest.mark.skip(
        reason="no .spynel/ task or goal documents in this checkout (.spynel/ is untracked)"
    )


@pytest.mark.parametrize("path", _documents(), ids=lambda p: p.name)
def test_timestamps_are_rfc3339_utc(path: Path) -> None:
    front_matter = _front_matter(path)
    fields = list(_timestamp_fields(front_matter))
    assert fields, f"{path}: front matter carries no timestamp field"
    for name, value in fields:
        _instant(name, value, path)


@pytest.mark.parametrize("path", _documents(), ids=lambda p: p.name)
def test_no_timestamp_postdates_updated_at(path: Path) -> None:
    front_matter = _front_matter(path)
    assert "updated_at" in front_matter, f"{path}: missing required `updated_at`"
    updated_at = _instant("updated_at", front_matter["updated_at"], path)
    for name, value in _timestamp_fields(front_matter):
        if name in ("updated_at", "wake_at", "next_review_at"):
            continue  # wake_at / next_review_at are deliberately future-dated
        assert _instant(name, value, path) <= updated_at, (
            f"{path}: {name}={value!r} postdates updated_at={front_matter['updated_at']!r}"
        )


@pytest.mark.parametrize("path", _documents(), ids=lambda p: p.name)
def test_direct_completion_completed_at_matches_updated_at(path: Path) -> None:
    front_matter = _front_matter(path)
    summary = front_matter.get("completion_summary")
    if not isinstance(summary, dict) or summary.get("verdict") != "completed":
        pytest.skip("not a direct-completion summary")
    if front_matter.get("status") != "done":
        # The contract attaches this equality to the `working -> done` move. A file still
        # in flight may carry a drafted summary while `updated_at` keeps advancing.
        pytest.skip("direct-completion summary not yet terminal (status != done)")
    assert "completed_at" in summary, f"{path}: `completed` verdict without `completed_at`"
    assert _instant(
        "completion_summary.completed_at", summary["completed_at"], path
    ) == _instant("updated_at", front_matter["updated_at"], path), (
        f"{path}: completion_summary.completed_at must equal updated_at exactly"
    )
