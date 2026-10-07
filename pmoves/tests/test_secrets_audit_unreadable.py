"""secrets_hardening_audit must not crash on a file it cannot read.

A root-owned file under the walked tree (measured: a Hugging Face cache entry
under pmoves/data/models/hub written by a container) raised PermissionError and
aborted `make secrets-funnel` at its final gate, after the tier files were
already written. Unreadable files are skipped and counted instead.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[2] / "pmoves" / "tools" / "secrets_hardening_audit.py"


def _load():
    name = "secrets_hardening_audit_unreadable"
    spec = importlib.util.spec_from_file_location(name, _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # @dataclass resolves its module via sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read mode-000 files")
def test_unreadable_file_is_skipped_and_recorded(tmp_path):
    audit = _load()
    blocked = tmp_path / "blocked.json"
    blocked.write_text("{}", encoding="utf-8")
    blocked.chmod(0)
    try:
        assert audit.read_text(blocked) == ""
        assert blocked in audit.UNREADABLE
    finally:
        blocked.chmod(0o600)


def test_readable_file_still_read(tmp_path):
    audit = _load()
    ok = tmp_path / "ok.md"
    ok.write_text("hello", encoding="utf-8")
    assert audit.read_text(ok) == "hello"
    assert ok not in audit.UNREADABLE
