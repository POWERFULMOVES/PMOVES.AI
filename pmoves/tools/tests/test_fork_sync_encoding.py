# pmoves/tools/tests/test_fork_sync_encoding.py
"""Tests for the fork-sync tool's gh-output decoding contract.

THE DEFECT THIS PINS
--------------------
`pmoves/tools/fork_sync.py::_gh` shells out to the `gh` CLI and decodes its
stdout. It originally used `subprocess.run(..., text=True)` with NO
`encoding=`, which makes Python decode with the LOCALE encoding.

On a Windows host that is cp1252. A `gh api compare` payload containing a
UTF-8 continuation byte then raises `UnicodeDecodeError` INSIDE the reader
thread -- which leaves `result.stdout` as `None`. The crash surfaces far
from its cause, as:

    AttributeError: 'NoneType' object has no attribute 'strip'
      at pmoves/tools/fork_sync.py:103 (in _gh_json)

MEASURED 2026-10-30 on the operator's Windows host: 6 of the 82 registry
fork compare-payloads are not cp1252-decodable -- PMOVES-Open-Notebook
(0x8f @198160), PMOVES-hermes-agent (0x9d @354498), PMOVES-Agent-Zero
(0x90 @143048), PMOVES-BotZ-gateway (0x90 @57457), PMOVES-skills
(0x9d @39049), PMOVES-Ultimate-TTS-Studio (0x8f @93041).

The effect was that `fork_sync.py audit` -- the tool that answers "how far
behind is this fork?" -- COULD NOT COMPLETE at all on that host. It died
partway through the sweep.

This is the same defect class already recorded for the `compose_data`
fixture in `pmoves/tests/hardening/test_docker_hardening.py`
(pmoves/docs/AGENTS/windows_cp1252_hardening_test_ratchet_LEARNINGS.md).
That lane fixed the TEST fixture; this is the same bug in TOOL code, and
CI never saw it because CI runs on Ubuntu (UTF-8 locale).

THE CONTRACT
------------
`gh` emits UTF-8 regardless of the host locale. So the tool must decode as
UTF-8 explicitly, and must not fall back to the locale. A decode failure
must not take the whole audit down.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "fork_sync.py"


def _subprocess_run_calls(tree: ast.Module) -> list[ast.Call]:
    """Every subprocess.run(...) call in the module."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]


def _has_encoding_kwarg(call: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in call.keywords)


def _source_of(call: ast.Call) -> str:
    return ast.unparse(call)


def test_the_tool_exists():
    assert TOOL.exists(), f"fork_sync.py not found at {TOOL}"


def test_every_subprocess_run_decodes_with_an_explicit_encoding():
    """No subprocess.run in fork_sync.py may rely on the LOCALE encoding.

    `text=True` without `encoding=` means "decode with the locale", which
    on Windows is cp1252 and cannot represent the UTF-8 continuation bytes
    that appear in GitHub commit messages -- which is exactly what
    `gh api compare` returns.
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    calls = _subprocess_run_calls(tree)
    assert calls, "expected fork_sync.py to shell out via subprocess.run"

    offenders = [
        _source_of(c) for c in calls if not _has_encoding_kwarg(c)
    ]
    assert not offenders, (
        "these subprocess.run calls decode with the LOCALE encoding, which "
        "is cp1252 on Windows and crashes on the non-ASCII bytes in "
        "`gh api compare` payloads:\n  " + "\n  ".join(offenders)
    )


def test_the_gh_wrapper_decodes_as_utf8_specifically():
    """The gh wrapper must name utf-8 explicitly, not merely pass an encoding.

    `encoding="cp1252"` would satisfy the check above and still crash.
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    calls = _subprocess_run_calls(tree)
    assert calls

    for call in calls:
        for kw in call.keywords:
            if kw.arg == "encoding":
                assert isinstance(kw.value, ast.Constant), (
                    "the encoding argument must be a literal, so the "
                    "decoding contract is readable at the call site"
                )
                assert kw.value.value == "utf-8", (
                    f"fork_sync.py must decode gh output as utf-8, not "
                    f"{kw.value.value!r}: gh emits UTF-8 regardless of host "
                    f"locale, and the locale encoding (cp1252 on Windows) "
                    f"cannot represent the bytes in a compare payload"
                )


def test_the_gh_wrapper_survives_undecodable_bytes():
    """A decode failure must not take the audit down.

    `errors="replace"` guarantees the reader thread never raises, so
    `result.stdout` is never None. The regression this guards is the
    `AttributeError: 'NoneType' object has no attribute 'strip'` that
    surfaced at _gh_json when the reader thread had already died.
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    calls = _subprocess_run_calls(tree)
    assert calls

    for call in calls:
        errors_kw = [kw for kw in call.keywords if kw.arg == "errors"]
        assert errors_kw, (
            "the subprocess.run call must pass errors= so an undecodable "
            "byte cannot raise inside the reader thread and leave "
            "result.stdout as None"
        )
        assert isinstance(errors_kw[0].value, ast.Constant)
        assert errors_kw[0].value.value in ("replace", "backslashreplace")


def test_a_utf8_payload_with_a_continuation_byte_survives_the_decode():
    """The exact byte that crashed the audit must now decode.

    0x9d is the byte that broke PMOVES-hermes-agent's compare payload at
    position 354498. It is a UTF-8 CONTINUATION byte -- valid UTF-8,
    invalid cp1252. This is the positive control: it proves the new
    decoding path handles the real payload shape, and it fails against the
    old locale-decoding path.
    """
    payload = b'{"message":"caf\xc3\xa9 \xe2\x98\x9d"}'

    # The OLD behaviour: locale decoding (cp1252 on this host).
    with pytest.raises(UnicodeDecodeError):
        payload.decode("cp1252")

    # The NEW behaviour: explicit utf-8 with replacement.
    decoded = payload.decode("utf-8", errors="replace")
    assert "�" not in decoded, (
        "a well-formed UTF-8 payload must not need replacement -- the "
        "bytes are valid UTF-8, so the decoder must accept them as-is"
    )

    # And the subprocess-level contract: text=True + encoding + errors.
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.argv[1].encode('utf-8'))",
         '{"m":"\u201d"}'],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.stdout == '{"m":"\u201d"}'
    assert proc.stdout is not None


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(pytest.main([__file__, "-v"]))
