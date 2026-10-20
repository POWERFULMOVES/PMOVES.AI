"""Static ratchet: every hi-rag-gateway-v2 Dockerfile must package the `pmoves.chit` AND `pmoves.tools` namespaces.

The 2026-10-15 YouTube ingest gap root cause: `pmoves-yt /yt/emit` calls
`POST /geometry/event` on the hi-rag-gateway-v2 GPU container, which
returns 503. The handler returns 503 because `shape_store is None` --
and `shape_store is None` because `services.common.shape_store`
imports `from pmoves.chit import CGP_SPEC_VERSION` at module top, and
the GPU image's `Dockerfile.gpu` did NOT copy the `chit/` directory
into `/app/pmoves/`. The CPU `Dockerfile` had this since 30efedfb77f
("fix(docker): add pmoves.chit namespace to Hi-RAG gateway containers")
but the GPU sibling Dockerfile was missed.

PR #3382 closed that gap (commit `e38c3a1`). On 2026-10-17 the
follow-up verification surfaced a SECOND missing namespace --
`pmoves.tools` -- imported by:
  - tools/chit_security.py:25  (`from pmoves.tools.chit_common import canon`)
  - services/common/geometry_decoder.py:75-76  (`from pmoves.tools.chit_common`,
    `from pmoves.tools.chit_security import verify_cgp, decrypt_anchors, ...`)
  - services/common/branch_trail.py:146-147  (`from pmoves.tools.sign_trail`,
    `from pmoves.tools.chit_security`)
  - services/common/model_fitness.py:22  (`from pmoves.tools.chit_security`)
Without `pmoves.tools`, `/geometry/event` returns 500 (`ModuleNotFoundError:
No module named 'pmoves.tools'`) and `cgp_ok` degrades to `false`.

A future sibling Dockerfile (e.g. `Dockerfile.cpu-amd`) that follows
the same shape -- packages the service but forgets a `pmoves.*`
namespace -- would re-introduce the same 503/500 silently. The ratchet
pins BOTH namespaces.

The runtime test that depends on this ratchet is
`pmoves/tests/test_yt_emit_cgp_ok.py` -- that test calls `POST /yt/emit`
on a fresh video and asserts `cgp_ok: true`. It cannot pass unless the
ShapeStore is initialized AND the geometry_decoder / chit_security
imports resolve.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


HI_RAG_DIR = Path(__file__).resolve().parents[1] / "services" / "hi-rag-gateway-v2"


def _dockerfiles() -> list[Path]:
    """Every `Dockerfile*` in pmoves/services/hi-rag-gateway-v2/."""
    return sorted(HI_RAG_DIR.glob("Dockerfile*"))


@pytest.mark.parametrize("dockerfile", _dockerfiles(), ids=lambda p: p.name)
def test_dockerfile_packages_pmoves_chit(dockerfile: Path) -> None:
    """Every hi-rag-gateway-v2 Dockerfile must:
    1. Create `/app/pmoves/__init__.py` (so the namespace package is real).
    2. Copy `chit/` into `/app/pmoves/chit` (so `pmoves.chit.CGP_SPEC_VERSION`
       is importable inside the container).

    The ratchet is a regex over the Dockerfile source. A future
    contributor who removes either line sees the failure here before
    they push -- and before CI builds a stale-image container.
    """
    source = dockerfile.read_text(encoding="utf-8")

    # 1. Must mkdir the namespace and create __init__.py.
    init_pattern = re.compile(
        r"mkdir\s+-p\s+(\S*/pmoves)\s+"
        r"(?:&&|;|\\\s*\n\s+)\s*"
        r".*?"
        r"(\S*/pmoves)/__init__\.py",
        re.DOTALL,
    )
    assert init_pattern.search(source), (
        f"{dockerfile.name} does not create /app/pmoves/__init__.py. "
        f"ShapeStore init will fail at runtime with 'No module named pmoves'."
    )

    # 2. Must COPY chit into /app/pmoves/chit.
    copy_pattern = re.compile(
        r"^COPY\s+chit\s+(\S*/pmoves)/chit\b",
        re.MULTILINE,
    )
    assert copy_pattern.search(source), (
        f"{dockerfile.name} does not COPY chit /app/pmoves/chit. "
        f"`from pmoves.chit import CGP_SPEC_VERSION` will fail at module import."
    )


@pytest.mark.parametrize("dockerfile", _dockerfiles(), ids=lambda p: p.name)
def test_dockerfile_packages_pmoves_tools(dockerfile: Path) -> None:
    """Every hi-rag-gateway-v2 Dockerfile must also package the
    `pmoves.tools` namespace (the 2026-10-17 follow-up). The minimal
    set is `__init__.py` + `chit_common.py` + `chit_security.py` +
    `sign_trail.py` (the latter via COPY because shape_store /
    geometry_decoder / branch_trail / model_fitness import from it).

    A future `from pmoves.tools.<x>` that adds a new module should
    extend this ratchet (or, better, broaden it to "COPY tools/*.py
    into /app/pmoves/tools/"). The ratchet is regex-based for the
    same reason as the chit ratchet: catches regressions at authoring
    time, not at CI build time.
    """
    source = dockerfile.read_text(encoding="utf-8")

    # 1. Must mkdir the pmoves/tools namespace and create __init__.py.
    tools_init_pattern = re.compile(
        r"mkdir\s+-p\s+(\S*/pmoves)/tools\s+"
        r"(?:&&|;|\\\s*\n\s+)\s*"
        r".*?"
        r"(\S*/pmoves)/tools/__init__\.py",
        re.DOTALL,
    )
    assert tools_init_pattern.search(source), (
        f"{dockerfile.name} does not create /app/pmoves/tools/__init__.py. "
        f"`from pmoves.tools.chit_common import canon` (and friends) will "
        f"fail with 'No module named pmoves.tools'."
    )

    # 2. Must COPY the three required tools modules into /app/pmoves/tools.
    for module in ("chit_common.py", "chit_security.py", "sign_trail.py"):
        pattern = re.compile(
            rf"^COPY\s+tools/{re.escape(module)}\s+(\S*/pmoves)/tools/{re.escape(module)}\b",
            re.MULTILINE,
        )
        assert pattern.search(source), (
            f"{dockerfile.name} does not COPY tools/{module} "
            f"/app/pmoves/tools/{module}. The chit_security / branch_trail / "
            f"geometry_decoder / model_fitness imports will fail at module load."
        )


def test_pmoves_chit_in_cpu_dockerfile_unchanged() -> None:
    """The CPU `Dockerfile` (non-GPU) has the chit namespace copy since
    30efedfb77f. A regression in the CPU path is a separate, louder
    failure; this is the historical baseline pinned as a sibling check
    so the ratchet does not have to enumerate BOTH paths implicitly.

    The pmoves.tools namespace is the 2026-10-17 follow-up; the CPU
    Dockerfile has the same gap and is pinned by this single check
    rather than a separate `pmoves.tools` baseline test.
    """
    cpu = HI_RAG_DIR / "Dockerfile"
    if not cpu.exists():
        pytest.skip("CPU Dockerfile not present on this branch")
    source = cpu.read_text(encoding="utf-8")
    assert "/app/pmoves/chit" in source, (
        f"{cpu.name} lost the chit namespace copy that 30efedfb77f added. "
        f"This is the historical baseline; if you are intentionally removing "
        f"it, also update pmoves/services/common/shape_store.py to not import "
        f"`from pmoves.chit import CGP_SPEC_VERSION` at module top."
    )
    assert "/app/pmoves/tools" in source, (
        f"{cpu.name} is missing the pmoves.tools namespace packaging that "
        f"tools/chit_security.py + services/common/{'{geometry_decoder,branch_trail,model_fitness}'}.py "
        f"require. PR #3382 closed the chit gap but missed the tools gap; the "
        f"2026-10-17 follow-up added it to Dockerfile.gpu but the CPU sibling "
        f"needs the same update."
    )
