"""Tests for the silent-handler sweep behind the instrument-trust audit.

The sweep exists because `docs/audit/INSTRUMENT_TRUST_AUDIT_2026-08-15.md` published a
157/60/6/4 funnel produced by a script that was then thrown away. These tests pin the
predicate so the replacement cannot quietly drift the way the number did.

Two of them exist specifically because the first draft got the predicate wrong in a way
that would have excluded the finding that motivated the whole sweep.
"""

import ast

import pytest

from tools.silent_handler_sweep import (
    _is_broad,
    _is_pass_only,
    _is_silent,
    _legacy_has_import,
    _legacy_is_broad,
    _legacy_is_silent,
    sweep,
)


def _handler(src: str) -> ast.ExceptHandler:
    """Parse a single try/except and return its first handler."""
    tree = ast.parse(src)
    node = tree.body[0]
    assert isinstance(node, ast.Try)
    return node.handlers[0]


# --------------------------------------------------------------------------------
# Stage 1 — broad or bare
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "clause",
    ["except:", "except Exception:", "except BaseException:", "except (ValueError, Exception):"],
)
def test_broad_handlers_are_detected(clause):
    assert _is_broad(_handler(f"try:\n    import x\n{clause}\n    pass\n"))


@pytest.mark.parametrize("clause", ["except ImportError:", "except (ValueError, KeyError):"])
def test_narrow_handlers_are_not_broad(clause):
    """A specific handler is a deliberate guard, not the shape being counted."""
    assert not _is_broad(_handler(f"try:\n    import x\n{clause}\n    pass\n"))


# --------------------------------------------------------------------------------
# Stage 2 — silent
# --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "    logger.exception('boom')",
        "    logging.warning('boom')",
        "    print('boom')",
        "    sys.stderr.write('boom')",
        "    raise",
    ],
)
def test_audible_handlers_are_not_silent(body):
    assert not _is_silent(_handler(f"try:\n    import x\nexcept Exception:\n{body}\n"))


def test_returning_a_default_is_silent_not_audible():
    """`except Exception: return _FALLBACK` IS finding #7.

    The first draft of the sweep treated any `Return` as audible, which would have
    excluded the exact defect the audit was written about — and dropped stage 2 from
    69 to 7. Widening 'audible' until the alarming number goes away is the same move
    as trusting a status code.
    """
    assert _is_silent(_handler("try:\n    import yaml\nexcept Exception:\n    return _FALLBACK\n"))


def test_setting_a_degraded_flag_is_silent_at_stage_2():
    """`_CRYPTO_OK = False` (chit_security.py) says nothing AT the moment of failure.

    It is correct code — it records the failure where a caller can read it — but it is
    cleared at stage 3 (handler is not `pass`), not at stage 2. Treating assignment as
    audible collapses the funnel and hides the shape being counted.
    """
    assert _is_silent(_handler("try:\n    import cryptography\nexcept Exception:\n    _CRYPTO_OK = False\n"))


# --------------------------------------------------------------------------------
# Stage 3 — fully pass
# --------------------------------------------------------------------------------


@pytest.mark.parametrize("body", ["    pass", "    ..."])
def test_pass_only_handlers(body):
    assert _is_pass_only(_handler(f"try:\n    import x\nexcept Exception:\n{body}\n"))


def test_handler_with_work_is_not_pass_only():
    assert not _is_pass_only(_handler("try:\n    import x\nexcept Exception:\n    _OK = False\n"))


# --------------------------------------------------------------------------------
# Regression — the four sites fixed in #2572 must not come back
# --------------------------------------------------------------------------------

# (path, what it was) — each returned a complete-looking result built from nothing.
FIXED_IN_2572 = {
    "pmoves/tools/sign_trail.py": "substituted the whole agent identity in silence",
    "pmoves/services/hi-rag-gateway-v2/routes/geometry.py": "dropped every live subscriber, returned ok:true",
    # hf-mcp-server also holds a CORRECT pass-only handler (the registry->catalog
    # fallback at :564), so this file is asserted on below by line, not by path.
}


def test_fixed_sites_no_longer_appear_at_stage_3():
    """The sweep is a regression check on its own findings, not a one-time count."""
    stage3 = [s for s in sweep(["pmoves/tools", "pmoves/services"]) if s.silent and s.pass_only]
    offenders = [s for s in stage3 if s.path in FIXED_IN_2572]
    assert not offenders, (
        "a handler fixed in #2572 has regressed to silent-pass: "
        + ", ".join(f"{s.path}:{s.handler_lineno}" for s in offenders)
    )


def test_hf_mcp_gguf_publish_handler_still_logs():
    """The `hf.model.gguf.converted.v1` publish must not go back to silent-pass.

    Asserted by file rather than line so it survives edits above it — the audit's own
    `geometry.py:583` citation rotted into pointing at the opposite of its claim.
    """
    main = "pmoves/services/hf-mcp-server/main.py"
    stage3 = [
        s
        for s in sweep(["pmoves/services"])
        if s.path == main and s.silent and s.pass_only
    ]
    # Exactly one pass-only handler is expected here: the registry -> static-catalog
    # fallback, which is CORRECT because the result is stamped `"source": "catalog"`.
    assert len(stage3) <= 1, (
        "more silent-pass handlers in hf-mcp-server than the one known-good catalog "
        "fallback: " + ", ".join(str(s.handler_lineno) for s in stage3)
    )


# --------------------------------------------------------------------------------
# Legacy predicate — kept runnable so the audit's middle column stays regenerable
# --------------------------------------------------------------------------------


def test_legacy_misses_nested_imports():
    """The original required the import to be a DIRECT child of the try body.

    `retro_flightcheck.py` puts `import winsound` inside `if os.name == 'nt':`, which
    is why the two sweeps disagree by 2 at stage 3.
    """
    src = "try:\n    if flag:\n        import winsound\nexcept Exception:\n    pass\n"
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.Try)
    assert not _legacy_has_import(node)


def test_legacy_substring_rule_misreads_an_unrelated_identifier():
    """`ast.dump(handler)` contains every identifier, so `catalog` reads as `log`.

    This is the defect that makes the legacy predicate a text grep in AST clothing —
    inside a sweep whose headline is that text greps cannot see a handler's shape.
    """
    handler = _handler("try:\n    import x\nexcept Exception:\n    catalog = {}\n")
    assert _legacy_is_silent(handler) is False  # wrongly "audible"
    assert _is_silent(handler) is True  # correctly silent


def test_legacy_misses_tuple_handlers():
    handler = _handler("try:\n    import x\nexcept (ValueError, Exception):\n    pass\n")
    assert not _legacy_is_broad(handler)
    assert _is_broad(handler)


def test_counterexamples_are_not_flagged_as_pass_only():
    """chit_security's degraded flag must reach stage 2 and stop there."""
    sites = [s for s in sweep(["pmoves/tools"]) if s.path == "pmoves/tools/chit_security.py"]
    assert sites, "expected the crypto import guard to be detected at stage 1"
    assert not any(s.pass_only for s in sites)
