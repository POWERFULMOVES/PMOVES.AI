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


def _emit_declined_for_archived_video(payload: object, status_code: int) -> bool:
    """Did ``/yt/emit`` decline to exercise the CGP path because the
    video is already in the download archive?

    The service reports this two ways, and the ratchet must catch BOTH:

    - a 404 whose detail says ``transcript not found`` -- the transcript
      could not be produced because yt-dlp refused to re-download an
      archived video, so no CGP was ever built;
    - a 200 whose body mentions the archive skip.

    The original check was ``"already in download archive" in r.text``:
    a case-SENSITIVE substring sniff against the raw response text, with
    no status-code check. It missed the 404 path entirely and would miss
    a message whose capitalisation differed.

    REVIEW FIX (2026-10-30): the check is now case-insensitive, checks
    the status code, and covers the 404 transcript-not-found shape that
    the substring sniff could never see.
    """
    if status_code == 404:
        detail = ""
        if isinstance(payload, dict):
            detail = str(payload.get("detail", "")).lower()
        if "transcript not found" in detail:
            return True
    if status_code != 200:
        return False
    try:
        text = str(payload).lower()
    except Exception:  # pragma: no cover -- defensive
        return False
    return "already in download archive" in text


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

    r = requests.post(
        f"{PMOVES_YT_URL}/yt/emit",
        json={"video_id": PROBE_VIDEO_ID, "topic": "ingest.transcript.ready.v1"},
        timeout=30,
    )
    try:
        payload = r.json()
    except ValueError:
        payload = {"raw": r.text}

    # REVIEW FIX (2026-10-30): the archive skip is now detected from the
    # EMIT RESPONSE, not from a mutating pre-probe. The original code
    # POSTed to /yt/download (which DOWNLOADS the video when it is not
    # already archived) and sniffed the response text case-sensitively.
    # The emit response is the authoritative answer to "was the CGP path
    # actually exercised", and it covers the 404 transcript-not-found
    # shape the old substring sniff could never see.
    if _emit_declined_for_archived_video(payload, r.status_code):
        pytest.skip(
            f"probe video {PROBE_VIDEO_ID!r} is already in the download "
            f"archive; CGP emit was skipped, not exercised"
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
