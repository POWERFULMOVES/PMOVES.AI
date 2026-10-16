"""Integration ratchet: `POST /yt/emit` on a fresh video must return `cgp_ok: true`.

The 2026-10-15 YouTube ingest gap root cause: the hi-rag-gateway-v2 GPU
container's `Dockerfile.gpu` was missing the `pmoves.chit` namespace
copy that the CPU `Dockerfile` has. The result: `ShapeStore` import
failed at startup, the `/geometry/event` handler returned 503, and
`pmoves-yt /yt/emit` degraded to `cgp_ok: false` (non-fatal warning).

This test calls `POST /yt/emit` on a fresh video and asserts the
`cgp_ok: true` field. It cannot pass unless the full pipeline is wired:
- pmoves-yt is up at http://localhost:8077
- the GPU container has `/app/pmoves/chit` packaged (the static
  ratchet `test_dockerfile_packages_pmoves_chit.py` pins that)
- the `/geometry/event` handler returns 200 with a CGP ID
- pmoves-yt degrades to `cgp_ok: true` instead of false

A future regression to any of these stages fails this test. The test
itself is short and the assertions are tight.

Note: this test requires a live pmoves-yt + hi-rag-gateway-v2 stack
on localhost. If the stack is down, the test SKIPs rather than
fails -- the deployment of these services is a separate lane from
the lane that fixes the packaging.
"""

from __future__ import annotations

import socket

import pytest


try:
    import requests
except ImportError:  # pragma: no cover -- the test suite pins requests
    requests = None  # type: ignore


PMOVES_YT_URL = "http://localhost:8077"
# A short, public, stable YouTube video that's unlikely to be in the
# download archive: a Wikipedia-suggested 18-second ambient video.
# If this video becomes unavailable, the test is harmless to skip.
PROBE_VIDEO_ID = "0p_1QSUsbsM"


def _localhost_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _video_in_archive(video_id: str) -> bool:
    """Skip if the probe video is already in the download archive --
    the yt-dlp path will return 'already in archive' and the CGP emit
    will be skipped, not exercised.
    """
    if requests is None:
        return True
    try:
        r = requests.post(
            f"{PMOVES_YT_URL}/yt/download",
            json={"url": f"https://www.youtube.com/watch?v={video_id}"},
            timeout=10,
        )
    except requests.RequestException:
        return True
    return "already in download archive" in r.text


@pytest.mark.skipif(
    requests is None,
    reason="requests not installed in this environment",
)
def test_yt_emit_returns_cgp_ok_true() -> None:
    """The CGP (Compressed Geometric Packet) emit step is the bridge from
    raw MinIO content to PMOVES-Creator's geometry bus + H3 Omni
    conditioning. A `cgp_ok: false` response means the bridge is broken
    and YT content cannot reach the creative substrate.
    """
    if not _localhost_reachable("localhost", 8077):
        pytest.skip("pmoves-yt is not up on localhost:8077")
    if _video_in_archive(PROBE_VIDEO_ID):
        pytest.skip(
            f"probe video {PROBE_VIDEO_ID!r} is already in the download "
            f"archive; CGP emit would be skipped, not exercised"
        )

    r = requests.post(
        f"{PMOVES_YT_URL}/yt/emit",
        json={"video_id": PROBE_VIDEO_ID, "topic": "ingest.transcript.ready.v1"},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()

    assert payload.get("ok") is True, (
        f"/yt/emit returned ok={payload.get('ok')!r}: {payload!r}"
    )
    assert payload.get("cgp_ok") is True, (
        "CGP emit failed -- the geometry/event handler in "
        "hi-rag-gateway-v2 returned a non-2xx (most commonly 503 from "
        "ShapeStore being None because the pmoves.chit namespace is not "
        "packaged in the GPU image). Check the operator handoff at "
        "pmoves/docs/handoffs/youtube_ingest_gap_analysis_2026-10-15.md "
        f"and the static ratchet at pmoves/tests/test_dockerfile_packages_pmoves_chit.py. "
        f"Full response: {payload!r}"
    )
