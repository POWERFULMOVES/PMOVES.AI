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
      at _gh_json in pmoves/tools/fork_sync.py

The measured forensics -- which payloads, which bytes, at which offsets --
live in `pmoves/docs/services/PIPECAT_FORK_PROVENANCE_AUDIT_2026-10-30.md`
(Gap 4). They are deliberately NOT duplicated here: a MEASUREMENT belongs in
the doc, a load-bearing fact belongs in the code.

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

THE RATCHET
-----------
The checks below are AST-based on the tool's own source, so they are
hermetic: they never shell out to `gh` and never touch the network.

A ratchet that can only assert absence cannot say no, so this one carries a
positive control: the matcher is exercised against synthetic sources that
spell the subprocess call every way a future refactor might spell it. If the
matcher goes blind it must SAY SO -- "the matcher went blind" and "the tool
stopped shelling out" are different failures and must not read alike.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "fork_sync.py"

# The subprocess callable this ratchet governs. `gh` is invoked through
# `run`; a deliberate switch to check_output/Popen must be a decision, not a
# silent hole -- the loud-failure path below is what catches that.
_TARGET = "run"


def _subprocess_bindings(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Names in *tree* that resolve to the subprocess module, and to its `run`.

    Returns (module_aliases, direct_call_names):
      module_aliases    -- "subprocess", "sp"   for `import subprocess [as sp]`
      direct_call_names -- "run", "_run"        for `from subprocess import run [as _run]`

    WHY both: a matcher that only recognises the `subprocess.run` attribute
    form goes blind the moment someone writes `from subprocess import run`,
    and a blind matcher fails in a way that reads like the tool stopped
    shelling out. `from subprocess import *` is not statically resolvable --
    the loud-failure path is what catches that.
    """
    module_aliases: set[str] = set()
    direct_call_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root == "subprocess":
                    module_aliases.add(alias.asname or root)
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name == _TARGET:
                    direct_call_names.add(alias.asname or alias.name)
    return module_aliases, direct_call_names


def _run_calls(tree: ast.Module) -> list[ast.Call]:
    """Every subprocess.run(...) call, under either import style."""
    module_aliases, direct_call_names = _subprocess_bindings(tree)
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == _TARGET
            and isinstance(func.value, ast.Name)
            and func.value.id in module_aliases
        ):
            calls.append(node)
        elif isinstance(func, ast.Name) and func.id in direct_call_names:
            calls.append(node)
    return calls


def _require_calls(tree: ast.Module) -> list[ast.Call]:
    """Return the tool's subprocess.run calls, failing LOUDLY if there are none.

    "No calls found" has two causes that must not read the same:
      (a) the tool stopped shelling out -- the decoding contract is void;
      (b) the matcher went blind -- the tool still shells out, but under an
          import shape this matcher does not resolve.
    (b) is a bug in THIS file, so the message has to name it as such.
    """
    calls = _run_calls(tree)
    if calls:
        return calls
    module_aliases, direct_call_names = _subprocess_bindings(tree)
    if module_aliases or direct_call_names:
        raise AssertionError(
            "MATCHER WENT BLIND: fork_sync.py imports subprocess "
            f"(module aliases {sorted(module_aliases)}, direct bindings "
            f"{sorted(direct_call_names)}) but no subprocess.{_TARGET} call "
            "was matched. That is a bug in this ratchet, NOT the tool "
            "stopping shelling out -- teach _subprocess_bindings the import "
            "style in use before trusting this file."
        )
    raise AssertionError(
        f"expected fork_sync.py to shell out via subprocess.{_TARGET} -- no "
        "subprocess import and no call found. If the tool deliberately "
        "stopped shelling out, retire this ratchet; if not, the shell-out "
        "moved and this ratchet must follow it."
    )


def _has_encoding_kwarg(call: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in call.keywords)


def _source_of(call: ast.Call) -> str:
    return ast.unparse(call)


def test_the_tool_exists():
    assert TOOL.exists(), f"fork_sync.py not found at {TOOL}"


# ---------------------------------------------------------------------------
# Positive control -- the matcher has to SEE the call, under either style.
# Without this the ratchet could pass by finding nothing at all.
# ---------------------------------------------------------------------------

MODULE_STYLE = '''
import subprocess


def _gh():
    return subprocess.run(["gh", "api"], capture_output=True, text=True)
'''

FROM_STYLE = '''
from subprocess import run


def _gh():
    return run(["gh", "api"], capture_output=True, text=True)
'''

ALIASED_MODULE_STYLE = '''
import subprocess as sp


def _gh():
    return sp.run(["gh", "api"], capture_output=True, text=True)
'''

ALIASED_FROM_STYLE = '''
from subprocess import run as _run


def _gh():
    return _run(["gh", "api"], capture_output=True, text=True)
'''


@pytest.mark.parametrize(
    "src",
    [MODULE_STYLE, FROM_STYLE, ALIASED_MODULE_STYLE, ALIASED_FROM_STYLE],
)
def test_the_matcher_finds_the_call_under_either_import_style(src: str) -> None:
    """POSITIVE CONTROL: the matcher must SEE the subprocess call.

    The matcher used to recognise only the `subprocess.run` attribute form.
    One `from subprocess import run` away, it found nothing -- and the
    failure read like the tool stopped shelling out rather than like the
    matcher went blind.
    """
    assert len(_run_calls(ast.parse(src))) == 1, src


def test_a_source_with_no_subprocess_call_matches_nothing() -> None:
    """The other half of the control: the matcher does not invent calls."""
    src = "def _gh():\n    return None\n"
    assert _run_calls(ast.parse(src)) == []


def test_zero_candidates_says_the_matcher_went_blind() -> None:
    """A blind matcher must announce itself, not impersonate a missing call.

    This ratchet can only assert a property of calls it can SEE. If it sees
    none while the module still imports subprocess, the honest report is
    "the matcher went blind" -- the tool may well be shelling out fine,
    just under a shape this matcher does not resolve.
    """
    blind = ast.parse(
        "import subprocess\n\n\ndef _gh():\n    return subprocess.Popen(['gh'])\n"
    )
    with pytest.raises(AssertionError) as exc:
        _require_calls(blind)
    message = str(exc.value)
    assert "MATCHER WENT BLIND" in message
    assert "bug in this ratchet" in message


def test_zero_candidates_without_a_subprocess_import_says_the_tool_stopped() -> None:
    """The other failure mode gets its own message: the tool stopped shelling out."""
    with pytest.raises(AssertionError) as exc:
        _require_calls(ast.parse("def _gh():\n    return None\n"))
    assert "stopped shelling out" in str(exc.value)


def test_every_subprocess_run_decodes_with_an_explicit_encoding():
    """No subprocess.run in fork_sync.py may rely on the LOCALE encoding.

    `text=True` without `encoding=` means "decode with the locale", which
    on Windows is cp1252 and cannot represent the UTF-8 continuation bytes
    that appear in GitHub commit messages -- which is exactly what
    `gh api compare` returns.
    """
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    calls = _require_calls(tree)

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
    calls = _require_calls(tree)

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
    calls = _require_calls(tree)

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
    position 354498. It is a UTF-8 CONTINUATION byte -- valid UTF-8 only
    as part of the multi-byte sequence E2 98 9D (U+261D), and with no
    cp1252 mapping at all. This is the positive control: it proves the new
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
