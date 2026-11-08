"""Global pytest fixture bridge for per-service test runs.

CI executes service suites in isolation (one pytest invocation per path). Import
only the shared fixtures needed by service tests to avoid path-collision side
effects from autouse helpers in the broader test conftest.
"""

from pathlib import Path

from pmoves.tests.conftest import load_service_module, stub_external_modules  # noqa: F401
from pmoves.tests import mutation_backup

# REPAIR AT COLLECTION
# --------------------
# A mutation harness proves a fix by mutating a tracked source file in the
# live tree. Its restore lives in a ``finally``, so a KILLED harness -- and
# the repo's pytest RATCHET kills a chunk that overruns its wall-clock
# budget -- can leave the tree mutated. The next session then imports the
# mutated file and reports a defect that does not exist.
#
# MEASURED on CI, 2026-11-02 (branch fix/carry-over-closure, head
# 346fa264a9a): a killed chunk left pmoves/tools/windows_encoding_ratchet.py
# mutated, and the sibling live-tree test failed against it.
#
# This runs at conftest IMPORT time, which is during COLLECTION -- before any
# test module is imported and therefore before any test module can import a
# mutated source file. The primary fix is the allowance in
# pmoves/configs/pytest_ratchet/_slow_files.yaml, which stops the kill from
# happening; this is the defence in depth behind it.
#
# The restore is deliberately a no-op unless a backup is actually outstanding,
# so the common case costs one directory listing and nothing else.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_RESTORED = mutation_backup.restore_outstanding(_REPO_ROOT)
if _RESTORED:
    print(
        "pmoves/conftest.py: restored a tree left mutated by a killed "
        "mutation harness: " + ", ".join(_RESTORED),
        flush=True,
    )
