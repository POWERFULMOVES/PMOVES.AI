"""Fleet ratchet: no text-mode file I/O may omit an explicit ``encoding=``.

WHY THIS FILE EXISTS
--------------------
Python's ``open()``/``Path.read_text()`` default to the LOCALE encoding when
``encoding`` is omitted. On a Windows host whose locale is cp1252, reading a
UTF-8 file raises ``UnicodeDecodeError`` -- so a test that only reads a compose
file can fail on Windows and pass on Linux CI, for a reason that has nothing
to do with what the test asserts.

That is not hypothetical. MEASURED 2026-11-01: 25 tests in
``pmoves/tests/smoke/test_compose_structure.py`` and
``pmoves/tests/smoke/test_port_conflicts.py`` failed on the operator's Windows
host with exactly that error, and ALL 27 passed with ``PYTHONUTF8=1`` --
which proves the failures were decoding, not logic. The same defect existed
in ``pmoves/scripts/validate_service_tools_packaging.py`` (the operator named
it) and in five other files.

WHAT THIS FILE ASSERTS
----------------------
1. the DETECTOR: text-mode ``open()``/``read_text()``/``write_text()``/
   ``Path.open()`` calls without ``encoding=`` are flagged, and calls with it
   are not;
2. the BINARY carve-out: a call that opens in binary mode is NOT flagged,
   because binary handles have no encoding -- and the mode is read from the
   correct SLOT for each signature (builtin ``open(file, mode, ...)`` takes
   the mode second, ``Path.open(mode, ...)`` takes it FIRST);
3. the NON-PATH carve-out: ``.open()`` on a known binary/media opener
   (``wave``, ``os``, ``Image`` ...) is not judged;
4. FAIL CLOSED: an unparseable or unreadable file is an instrument error, not
   a silent skip;
5. the BASELINE CONTRACT: a new gap fails, a count that rose fails, a count
   that fell fails as stale, a deleted file fails as orphaned;
6. the CLI, driven as a subprocess against a synthetic tree -- the gate really
   goes red on a new gap and really exits 2 when it cannot measure;
7. the LIVE tree: the files this lane fixed carry no gaps, and the gate is
   green against the committed baseline.

Points 6 and 7 matter more than they look. A test that re-types the
detector's own expression proves nothing about the detector; these drive the
shipped CLI.

Hermetic: no network, no docker, no NATS, no gh. It reads files in this repo
and runs the tool against pytest's tmp_path.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from pmoves.tools import windows_encoding_ratchet as ratchet

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
TOOL = PMOVES / "tools" / "windows_encoding_ratchet.py"
BASELINE = PMOVES / "configs" / "encoding_ratchet" / "_known_gaps.yaml"

# The files the carry-over lane fixed. Each one MUST carry zero gaps; if a
# later change re-introduces an undecoded read, the live gate turns red.
FIXED_FILES = [
    "tests/smoke/test_compose_structure.py",
    "tests/smoke/test_port_conflicts.py",
    "scripts/validate_service_tools_packaging.py",
    "scripts/port_allocator.py",
    "scripts/validate-ollama-inventory.py",
    "tools/inject_docker_hub_pat_from_cli.py",
    "services/channel-monitor/channel_monitor/config.py",
    "tools/keygen_cards.py",
]


def _gaps(source: str) -> list[dict]:
    gaps, _skipped = ratchet.find_gaps(source, "<snippet>")
    return gaps


# ---------------------------------------------------------------------------
# 1. the detector
# ---------------------------------------------------------------------------


def test_a_read_text_without_encoding_is_flagged():
    gaps = _gaps("data = p.read_text()\n")
    assert len(gaps) == 1
    assert gaps[0]["call"] == "read_text"


def test_a_read_text_with_encoding_is_not_flagged():
    assert _gaps('data = p.read_text(encoding="utf-8")\n') == []


def test_a_write_text_without_encoding_is_flagged():
    gaps = _gaps("p.write_text('x')\n")
    assert len(gaps) == 1
    assert gaps[0]["call"] == "write_text"


def test_a_builtin_open_without_encoding_is_flagged():
    gaps = _gaps("with open(path) as f:\n    pass\n")
    assert len(gaps) == 1
    assert gaps[0]["call"] == "open"


def test_a_builtin_open_with_encoding_is_not_flagged():
    assert _gaps('with open(path, encoding="utf-8") as f:\n    pass\n') == []


def test_a_path_open_without_encoding_is_flagged():
    gaps = _gaps("with path.open() as f:\n    pass\n")
    assert len(gaps) == 1
    assert gaps[0]["call"] == "Path.open"


def test_a_path_open_with_encoding_is_not_flagged():
    assert _gaps('with path.open("r", encoding="utf-8") as f:\n    pass\n') == []


def test_a_non_path_opener_is_not_judged():
    """`wave.open()` opens a binary audio handle; encoding is meaningless."""
    assert _gaps("with wave.open(path, 'rb') as f:\n    pass\n") == []
    assert _gaps("with os.open(path, os.O_RDONLY) as fd:\n    pass\n") == []
    assert _gaps("with Image.open(path) as im:\n    pass\n") == []


def test_an_encoding_keyword_is_not_mistaken_for_a_similar_name():
    """A kwarg named something else must not be read as the encoding."""
    assert _gaps("p.read_text(errors='ignore')\n") != []


# ---------------------------------------------------------------------------
# 2. the binary carve-out -- and the mode SLOT
# ---------------------------------------------------------------------------


def test_a_binary_builtin_open_is_not_flagged():
    assert _gaps("with open(path, 'rb') as f:\n    pass\n") == []


def test_a_binary_path_open_is_not_flagged():
    assert _gaps("with p.open('rb') as f:\n    pass\n") == []


def test_the_binary_mode_is_read_from_the_second_slot_for_builtin_open():
    """builtin open(file, mode, ...) -- the mode is the SECOND argument.

    Reading the FIRST slot would see the filename and miss the binary mode.
    """
    tree = ast.parse("with open(path, 'rb') as f:\n    pass\n")
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    mode = ratchet._mode_argument(call, path_open=False)
    assert isinstance(mode, ast.Constant) and mode.value == "rb"


def test_the_binary_mode_is_read_from_the_first_slot_for_path_open():
    """Path.open(mode, ...) -- the mode is the FIRST argument.

    Reading the SECOND slot would see nothing and flag a binary call.
    """
    tree = ast.parse("with p.open('rb') as f:\n    pass\n")
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    mode = ratchet._mode_argument(call, path_open=True)
    assert isinstance(mode, ast.Constant) and mode.value == "rb"


def test_a_text_path_open_is_still_flagged():
    gaps = _gaps("with p.open('r') as f:\n    pass\n")
    assert len(gaps) == 1


def test_a_mode_keyword_is_honoured_for_both_signatures():
    assert _gaps("with open(path, mode='rb') as f:\n    pass\n") == []
    assert _gaps("with p.open(mode='rb') as f:\n    pass\n") == []


# ---------------------------------------------------------------------------
# 3. fail closed
# ---------------------------------------------------------------------------


def test_an_unparseable_file_is_an_instrument_error():
    with pytest.raises(ratchet.InstrumentError):
        ratchet.find_gaps("def broken(:\n", "broken.py")


def test_a_missing_root_is_an_instrument_error():
    with pytest.raises(ratchet.InstrumentError):
        ratchet.scan(Path("no-such-directory-anywhere"))


def test_a_tree_with_no_python_files_is_an_instrument_error(tmp_path):
    with pytest.raises(ratchet.InstrumentError):
        ratchet.scan(tmp_path)


def test_an_unreadable_file_is_reported_not_skipped(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    counts, errors, _oos = ratchet.scan(tmp_path)
    assert errors == []
    assert counts == {}


# ---------------------------------------------------------------------------
# 4. the baseline contract
# ---------------------------------------------------------------------------


def test_a_file_absent_from_the_baseline_is_a_new_gap():
    diff = ratchet.compare({"a.py": 1}, {}, Path("."))
    assert [g["file"] for g in diff["new_gaps"]] == ["a.py"]


def test_a_count_that_rose_is_a_new_gap():
    diff = ratchet.compare({"a.py": 3}, {"a.py": 1}, Path("."))
    assert len(diff["new_gaps"]) == 1
    assert diff["new_gaps"][0]["baseline_count"] == 1


def test_a_count_that_fell_is_stale():
    diff = ratchet.compare({"a.py": 1}, {"a.py": 3}, Path("."))
    assert diff["new_gaps"] == []
    assert len(diff["stale_gaps"]) == 1
    assert "fell below" in diff["stale_gaps"][0]["reason"]


def test_a_file_with_no_gaps_left_is_stale(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    diff = ratchet.compare({}, {"a.py": 2}, tmp_path)
    assert len(diff["stale_gaps"]) == 1
    assert "no gaps left" in diff["stale_gaps"][0]["reason"]


def test_a_deleted_file_is_orphaned(tmp_path):
    diff = ratchet.compare({}, {"gone.py": 2}, tmp_path)
    assert len(diff["orphan_gaps"]) == 1
    assert diff["orphan_gaps"][0]["file"] == "gone.py"


def test_a_matching_population_produces_no_findings(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    diff = ratchet.compare({"a.py": 2}, {"a.py": 2}, tmp_path)
    assert diff["new_gaps"] == []
    assert diff["stale_gaps"] == []
    assert diff["orphan_gaps"] == []


def test_a_missing_baseline_reads_as_an_empty_baseline(tmp_path):
    assert ratchet.load_baseline(tmp_path / "nope.yaml") == {}


def test_a_baseline_entry_without_an_integer_count_is_an_instrument_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("known_gaps:\n  a.py:\n    reason: no count\n", encoding="utf-8")
    with pytest.raises(ratchet.InstrumentError):
        ratchet.load_baseline(bad)


# ---------------------------------------------------------------------------
# 5. the CLI, driven as a subprocess against a synthetic tree
# ---------------------------------------------------------------------------


def _run_cli(root: Path, baseline: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--root",
            str(root),
            "--baseline",
            str(baseline),
            "--json",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_cli_passes_on_a_clean_tree(tmp_path):
    root = tmp_path / "pmoves"
    root.mkdir()
    (root / "a.py").write_text('x = p.read_text(encoding="utf-8")\n', encoding="utf-8")
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text("known_gaps: {}\n", encoding="utf-8")
    proc = _run_cli(root, baseline)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["new_gaps"] == []


def test_the_cli_fails_on_a_new_gap_in_a_synthetic_tree(tmp_path):
    """The gate must actually go RED when a gap appears."""
    root = tmp_path / "pmoves"
    root.mkdir()
    (root / "a.py").write_text("data = p.read_text()\n", encoding="utf-8")
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text("known_gaps: {}\n", encoding="utf-8")
    proc = _run_cli(root, baseline)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert [g["file"] for g in payload["new_gaps"]] == ["a.py"]


def test_the_cli_fails_closed_when_a_file_cannot_be_parsed(tmp_path):
    """An unparseable file must NOT be skipped -- the gate must not pass.

    The house exit-code split (mirroring `image_staleness_ratchet.py`): exit 2
    is reserved for a scan that could not START; a per-file instrument error
    is reported in `problems` and fails the gate with exit 1. Either way the
    run is non-zero -- the point is that a broken file can never yield a
    green gate.
    """
    root = tmp_path / "pmoves"
    root.mkdir()
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text("known_gaps: {}\n", encoding="utf-8")
    proc = _run_cli(root, baseline)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["problems"], "the unparseable file must be named in the payload"
    assert payload["problems"][0]["file"] == "broken.py"


def test_the_cli_exits_two_when_the_tree_is_empty(tmp_path):
    """A scan that cannot START exits 2, not 0."""
    root = tmp_path / "pmoves"
    root.mkdir()
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text("known_gaps: {}\n", encoding="utf-8")
    proc = _run_cli(root, baseline)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "INSTRUMENT ERROR" in proc.stderr


# ---------------------------------------------------------------------------
# 6. the LIVE tree
# ---------------------------------------------------------------------------


def test_the_committed_baseline_exists_and_is_well_formed():
    assert BASELINE.exists(), f"missing baseline: {BASELINE}"
    data = yaml.safe_load(BASELINE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    known = data["known_gaps"]
    assert isinstance(known, dict) and known, "the baseline must not be empty"
    for name, entry in known.items():
        assert isinstance(entry, dict), name
        assert isinstance(entry.get("count"), int), name
        assert isinstance(entry.get("reason"), str) and entry["reason"], name


def test_every_file_the_lane_fixed_carries_no_gaps():
    counts, errors, _oos = ratchet.scan(PMOVES)
    assert errors == []
    for rel in FIXED_FILES:
        assert counts.get(rel, 0) == 0, f"{rel} still has an undecoded file read"


def test_the_live_gate_is_green_against_the_committed_baseline():
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--baseline", str(BASELINE), "--json"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["new_gaps"] == []
    assert payload["stale_gaps"] == []
    assert payload["orphan_gaps"] == []
    assert payload["problems"] == []


def test_the_baseline_covers_every_scanned_file_with_gaps():
    """The baseline must not be a SUBSET -- an unbaselined file is a new gap."""
    counts, errors, _oos = ratchet.scan(PMOVES)
    assert errors == []
    baseline = ratchet.load_baseline(BASELINE)
    assert set(counts) == set(baseline)
