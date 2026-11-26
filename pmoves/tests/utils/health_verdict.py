"""Health-response verdicts for the PMOVES smoke suite.

Shared by the smoke tests themselves and by the ratchet that guards them, so
the classification rule lives in ONE place and can be asserted directly --
without a running service.

THE RULE
--------
A smoke probe of a live service distinguishes three outcomes:

``pass``
    The service answered as expected.

``skip``
    The service is UP but cannot be judged on this host, because the host
    lacks a USABLE credential for the service's dependency. MEASURED twice:

      * b850 runner, 2026-11-20 -- pmoves-ui answered 503 with
        ``{"status":"degraded", "checks":{"database":{"status":"unhealthy",
        "error":"Unauthorized"}}}`` -- the smoke host has no service key in
        scope.
      * operator workstation, 2026-11-20 -- pmoves-ui answered 503 with
        ``{"status":"degraded", "checks":{"database":{"status":"unhealthy",
        "error":"JWT expired"}}}`` -- the host's Supabase credential is
        present but stale.

    Both are the same situation to a smoke probe: the host's credential for
    the database was NOT ACCEPTED, so the database check cannot be judged
    here. This is not a new idea: the archon fixture in
    ``pmoves/tests/smoke/test_archon.py`` already SKIPS an auth-armed service
    with the rationale "the smoke host has no API key in scope. Service
    reachability is verified; authenticated behavior must be tested on a node
    with the funnel env." A service that is up-but-unauthorized is reachable,
    and that is what a smoke probe can establish here.

``fail``
    Everything else -- including a degraded dependency that failed for a
    reason OTHER than credentials. That is a real defect and must stay a
    failure; the skip is narrow on purpose.
"""

from __future__ import annotations

from typing import Any

__all__ = ["classify_pmoves_ui_health", "CREDENTIAL_MARKERS"]

PASS = "pass"
SKIP = "skip"
FAIL = "fail"

# The credential-acceptance failures.
#
# Every one of them means the same thing to a smoke probe: the host's
# credential for the database was NOT ACCEPTED, so the database check cannot
# be judged on this host. The set is enumerated rather than open-ended so that
# WIDENING it is a visible, deliberate change: the ratchet asserts this
# exact tuple (pmoves/tests/tools/
# test_smoke_suite_service_catalog_ratchet.py), and the mutation harness
# proves that a widened set is caught.
#
# A genuine dependency failure -- "connection refused", "timeout", "host not
# found", "too many connections", "database does not exist" -- matches NONE
# of these and therefore still FAILS.
CREDENTIAL_MARKERS = (
    "unauthorized",
    "unauthorised",
    "jwt expired",
    "token expired",
    "invalid token",
    "invalid jwt",
    "missing api key",
    "no api key",
    "missing service key",
    "no service key",
)


def classify_pmoves_ui_health(status_code: int, body: Any) -> str:
    """Classify a pmoves-ui ``/api/health`` response.

    ``body`` is the decoded JSON (or ``None`` when the response was not
    JSON). Returns ``"pass"``, ``"skip"`` or ``"fail"``.
    """
    if status_code in (200, 307):
        return PASS
    if status_code == 503 and isinstance(body, dict):
        checks = body.get("checks")
        if isinstance(checks, dict):
            database = checks.get("database")
            if isinstance(database, dict):
                error = str(database.get("error") or "").lower()
                if (database.get("status") == "unhealthy"
                        and any(m in error for m in CREDENTIAL_MARKERS)):
                    return SKIP
    return FAIL
