#!/usr/bin/env python3
"""Read-only Invidious smoke: started, companion up, and both containers hold the funnel's key.

Exit doctrine: 0 clean / 1 findings / 3 could-not-measure. Note that
``make`` collapses every nonzero recipe exit to 2, so call this directly when
the distinction matters.

What each check proves (vendor behaviour, iv-org/invidious @1c4b41f9 and
iv-org/invidious-companion @fcb0456a, both read 2026-10-30):

1. Invidious ``GET /api/v1/stats`` answers 200 with JSON. Invidious exits at
   start-up when ``hmac_key`` is empty or ``invidious_companion_key`` is not
   exactly 16 characters (src/invidious/config.cr), so "it serves" proves the
   keys were present and well-formed at container creation.
2. Companion ``GET /healthz`` answers 200. The companion refuses to start when
   ``SERVER_SECRET_KEY`` is not 16 alphanumeric characters
   (src/lib/helpers/config.ts).
3. Key agreement. The companion guards ``<base>/youtubei/v1/*`` with bearer
   auth keyed on ``SERVER_SECRET_KEY`` (src/routes/index.ts). A GET there with a
   deliberately WRONG token must be 401 (negative control: locates the guarded
   path); the same GET with ``$INVIDIOUS_COMPANION_KEY`` must NOT be 401. No
   route answers GET there, so neither request reaches YouTube. A 401 on the
   real key means the running companion was created with a different value
   than the funnel now holds -- recreate with ``make -C pmoves up-invidious``.
4. Invidious <-> companion agreement. Check 3 only proves companion == funnel.
   If the companion was recreated and invidious was not, pages still load and
   playback fails. So read the key each RUNNING container was created with
   (``docker inspect``: invidious's INVIDIOUS_CONFIG -> invidious_companion_key,
   the companion's SERVER_SECRET_KEY) and compare them in-process. The values
   are never printed, logged or returned -- only the boolean.

Never prints the key. Pure stdlib.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

EXIT_CLEAN, EXIT_FINDINGS, EXIT_COULD_NOT_MEASURE = 0, 1, 3

# Current companion mounts its API under SERVER_BASE_PATH (default /companion);
# older pinned images served it at the root. Probe both; the negative control
# decides which one is real.
GUARDED_PATHS = ("/companion/youtubei/v1/player", "/youtubei/v1/player")


def _status(url: str, token: str | None = None, timeout: float = 8.0) -> int | None:
    req = urllib.request.Request(url, method="GET")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, OSError):
        return None


def _stats(url: str, timeout: float = 8.0) -> tuple[int | None, bool]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
            return int(resp.status), isinstance(body, dict) and "software" in body
    except urllib.error.HTTPError as exc:
        return int(exc.code), False
    except (urllib.error.URLError, OSError, ValueError):
        return None, False


CONFIG_COMPANION_KEY_RE = re.compile(r'^invidious_companion_key:\s*"?([^"\n]*)"?\s*$', re.M)


def _service_env(service: str) -> dict[str, str] | None:
    """Environment of the running container for a compose *service*; None if not measurable."""
    try:
        ids = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.service={service}"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        cid = ids.stdout.split()[0] if ids.returncode == 0 and ids.stdout.split() else None
        if cid is None:
            return None
        out = subprocess.run(
            ["docker", "inspect", "--format", "{{json .Config}}", cid],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if out.returncode != 0:
            return None
        entries = json.loads(out.stdout).get("Env") or []
        return {k: v for k, _, v in (str(e).partition("=") for e in entries) if k}
    except Exception:  # noqa: BLE001 - deliberate: see below
        # The data in flight here is secret (every env var of both containers).
        # Any exception -- including one whose message or traceback would quote a
        # value -- becomes "not measurable" with NO detail. The caller reports
        # COULD-NOT-MEASURE (exit 3), so the degradation is visible, not silent.
        return None


def containers_agree() -> bool | None:
    """True/False when both running containers' keys could be read, else None.

    Never raises: any failure is None (exit 3) with no detail, so no key can
    reach an exception message or a traceback.
    """
    try:
        inv, comp = _service_env("invidious"), _service_env("invidious-companion")
        if inv is None or comp is None:
            return None
        match = CONFIG_COMPANION_KEY_RE.search(str(inv.get("INVIDIOUS_CONFIG", "")))
        inv_key, comp_key = (match.group(1) if match else ""), str(comp.get("SERVER_SECRET_KEY", ""))
        if not inv_key or not comp_key:
            return None
        return hmac.compare_digest(inv_key.encode(), comp_key.encode())
    except Exception:  # noqa: BLE001 - same contract as _service_env
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--invidious-url",
        default=f"http://127.0.0.1:{os.environ.get('INVIDIOUS_PORT') or '3000'}",
    )
    parser.add_argument(
        "--companion-url",
        default=f"http://127.0.0.1:{os.environ.get('INVIDIOUS_COMPANION_PORT') or '8282'}",
    )
    args = parser.parse_args(argv)
    findings: list[str] = []

    code, is_stats = _stats(f"{args.invidious_url}/api/v1/stats")
    if code is None:
        print(f"COULD-NOT-MEASURE: invidious unreachable at {args.invidious_url}")
        return EXIT_COULD_NOT_MEASURE
    if code != 200 or not is_stats:
        findings.append(f"invidious /api/v1/stats -> {code} (stats JSON: {is_stats})")
    else:
        print("ok   invidious /api/v1/stats 200")

    code = _status(f"{args.companion_url}/healthz")
    if code is None:
        print(f"COULD-NOT-MEASURE: companion unreachable at {args.companion_url}")
        return EXIT_COULD_NOT_MEASURE
    if code != 200:
        findings.append(f"companion /healthz -> {code}")
    else:
        print("ok   companion /healthz 200")

    key = os.environ.get("INVIDIOUS_COMPANION_KEY", "")
    if not key:
        print("COULD-NOT-MEASURE: INVIDIOUS_COMPANION_KEY not in the environment (run via make invidious-smoke)")
        return EXIT_COULD_NOT_MEASURE
    wrong = "0" * 16 if key != "0" * 16 else "1" * 16
    guarded = [p for p in GUARDED_PATHS if _status(f"{args.companion_url}{p}", wrong) == 401]
    if not guarded:
        print("COULD-NOT-MEASURE: no companion path rejected a wrong bearer token; cannot test key agreement")
        return EXIT_COULD_NOT_MEASURE
    path = guarded[0]
    code = _status(f"{args.companion_url}{path}", key)
    if code == 401:
        findings.append(
            f"companion rejects the funnel's INVIDIOUS_COMPANION_KEY on {path} -- "
            "the container predates the current value; recreate: make -C pmoves up-invidious"
        )
    else:
        print(f"ok   companion accepts the funnel key on {path} (wrong key -> 401, funnel key -> {code})")

    agree = containers_agree()
    if agree is None:
        print("COULD-NOT-MEASURE: could not read the key from both running containers (docker inspect)")
        for f in findings:
            print(f"FAIL {f}")
        return EXIT_FINDINGS if findings else EXIT_COULD_NOT_MEASURE
    if agree:
        print("ok   invidious and companion containers hold the same companion key")
    else:
        findings.append(
            "the running invidious and invidious-companion containers hold DIFFERENT companion keys "
            "(one was recreated without the other) -- recreate both: make -C pmoves up-invidious"
        )

    for f in findings:
        print(f"FAIL {f}")
    return EXIT_FINDINGS if findings else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
