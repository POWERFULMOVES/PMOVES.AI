"""Static ratchet: every hi-rag-gateway-v2 Dockerfile must package the pmoves.chit namespace.

The 2026-10-15 YouTube ingest gap root cause: `pmoves-yt /yt/emit` calls
`POST /geometry/event` on the hi-rag-gateway-v2 GPU container, which
returns 503. The handler returns 503 because `shape_store is None` --
and `shape_store is None` because `services.common.shape_store`
imports `from pmoves.chit import CGP_SPEC_VERSION` at module top, and
the GPU image's `Dockerfile.gpu` did NOT copy the `chit/` directory
into `/app/pmoves/`. The CPU `Dockerfile` had this since 30efedfb77f
("fix(docker): add pmoves.chit namespace to Hi-RAG gateway containers")
but the GPU sibling Dockerfile was missed.

A future sibling Dockerfile (e.g. `Dockerfile.cpu-amd`) that follows
the same shape -- packages the service but forgets the chit namespace --
would re-introduce the same 503 silently. The ratchet pins the shape.

The runtime test that depends on this ratchet is
`pmoves/tests/test_yt_emit_cgp_ok.py` -- that test calls `POST /yt/emit`
on a fresh video and asserts `cgp_ok: true`. It cannot pass unless the
ShapeStore is initialized, which cannot happen unless the chit
namespace is packaged.
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


def test_pmoves_chit_in_cpu_dockerfile_unchanged() -> None:
    """The CPU `Dockerfile` (non-GPU) has the namespace copy since
    30efedfb77f. A regression in the CPU path is a separate, louder
    failure; this is the historical baseline pinned as a sibling check
    so the ratchet does not have to enumerate BOTH paths implicitly.
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
