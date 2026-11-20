"""Ratchet: the smoke suite's service catalog must agree with the house's own
sources of truth.

THE DEFECTS THIS GUARDS
------------------------
MEASURED on PR #3482's own CI, the smoke gate's pytest goal reported
``6 failed, 117 passed, 115 skipped``:

    FAILED tests/smoke/test_archon.py::test_archon_health_endpoint
    FAILED tests/smoke/test_archon.py::test_archon_supabase_connected
    FAILED tests/smoke/test_archon.py::test_archon_openapi_spec
    FAILED tests/smoke/test_archon.py::test_archon_agent_zero_connection
    FAILED tests/smoke/test_health_endpoints.py::test_service_health_endpoint[archon]
    FAILED tests/smoke/test_supabase_network.py::test_pmoves_ui_accessible

Five of the six were ONE stale entry: ``ARCHON.health_path`` was
``/healthz``, a path Archon 0.10.1 does not serve -- its UI catch-all answers
it with the SPA HTML page, so a JSON health probe raised
``JSONDecodeError: Expecting value: line 1 column 1 (char 0)``. The house's
own bash harness has probed ``/api/health`` since Archon 0.6.0 retired the
Python :8091/:8051 service, and that path returns the expected JSON on both
the legacy 8091 and the unified 3090 host ports.

The sixth was pmoves-ui answering 503 with
``{"status":"degraded","checks":{"database":{"status":"unhealthy",
"error":"Unauthorized"}}}`` -- the smoke host has no service key in scope,
which is the same situation ``test_archon.py`` already handles with a SKIP.

And ``PMOVES_UI.port`` carried the CONTAINER port (3000) where
``pmoves/configs/ports.yaml`` records the host port (4482) -- so every
catalog-driven probe of pmoves-ui aimed at a host port nothing publishes.

WHY THESE ASSERTIONS AND NOT OTHERS
------------------------------------
The catalog must not be allowed to drift from the house's own sources again,
so the expected values are DERIVED, not hardcoded:

  * archon's health path comes from ``pmoves/scripts/smoke-tests.sh`` -- the
    harness that already gets it right;
  * archon's and pmoves-ui's host ports come from
    ``pmoves/configs/ports.yaml`` -- the house port registry;
  * the pmoves-ui verdict rule comes from the classifier itself.

So a future change to any of those sources moves the expectation with it,
instead of leaving the ratchet asserting a frozen number.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from pmoves.tests.utils.health_verdict import (
    CREDENTIAL_MARKERS,
    FAIL,
    PASS,
    SKIP,
    classify_pmoves_ui_health,
)
from pmoves.tests.utils.service_catalog import ARCHON, PMOVES_UI

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES_ROOT = REPO_ROOT / "pmoves"

PORTS_YAML = PMOVES_ROOT / "configs" / "ports.yaml"
SMOKE_SCRIPT = PMOVES_ROOT / "scripts" / "smoke-tests.sh"


def _registry() -> dict:
    with PORTS_YAML.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _host_port(service: str, slot: str) -> int:
    services = (_registry().get("services") or {})
    slots = (services.get(service) or {}).get("slots") or {}
    entry = slots.get(slot)
    assert entry is not None, (
        f"ports.yaml no longer records {service}.{slot} -- the ratchet must "
        f"follow the registry, not a frozen number"
    )
    return int(entry["host_port"])


def _archon_probe_path() -> str:
    """The health path the house's own bash harness probes for archon."""
    text = SMOKE_SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r'test_http_endpoint\s+"Archon"\s+'
        r'"http://localhost:\$\{ARCHON_PORT:-\d+\}(/[\w/]+)"',
        text,
    )
    assert match is not None, (
        "pmoves/scripts/smoke-tests.sh no longer probes an Archon health "
        "endpoint with an ARCHON_PORT override -- the ratchet must follow "
        "the harness, not a frozen string"
    )
    return match.group(1)


def test_the_catalog_archon_health_path_matches_the_house_smoke_harness() -> None:
    """Archon's health path must be the one the bash harness probes.

    ``/healthz`` is NOT it: Archon 0.10.1 answers that path with its UI
    catch-all HTML, and a JSON probe of it raises JSONDecodeError -- which is
    exactly how four archon smoke tests and
    ``test_service_health_endpoint[archon]`` failed.
    """
    expected = _archon_probe_path()
    assert ARCHON.health_path == expected, (
        f"the catalog's archon health_path is {ARCHON.health_path!r} but "
        f"pmoves/scripts/smoke-tests.sh probes {expected!r} -- MEASURED, the "
        f"path {ARCHON.health_path!r} is answered by the UI catch-all HTML, "
        "so every JSON health probe of archon raises JSONDecodeError"
    )


def test_the_catalog_archon_port_matches_the_port_registry() -> None:
    """The catalog carries HOST ports; ports.yaml records them."""
    expected = _host_port("archon", "ARCHON_API_PORT")
    assert ARCHON.port == expected, (
        f"the catalog's archon port is {ARCHON.port} but ports.yaml records "
        f"host_port {expected} for archon.ARCHON_API_PORT"
    )


def test_the_catalog_pmoves_ui_port_matches_the_port_registry() -> None:
    """pmoves-ui is published on 4482; the container port 3000 is not a host port."""
    expected = _host_port("pmoves-ui", "PMOVES_UI_PORT")
    assert PMOVES_UI.port == expected, (
        f"the catalog's pmoves-ui port is {PMOVES_UI.port} but ports.yaml "
        f"records host_port {expected} for pmoves-ui.PMOVES_UI_PORT -- the "
        "container port is not published on the host, so a catalog-driven "
        "probe of it can never succeed"
    )


def test_the_pmoves_ui_verdict_skips_only_credential_failures() -> None:
    """An auth-armed service skips; a genuinely degraded one still fails."""
    unauthorized = {
        "status": "degraded",
        "service": "pmoves-ui",
        "checks": {"database": {"status": "unhealthy", "error": "Unauthorized"}},
    }
    assert classify_pmoves_ui_health(503, unauthorized) == SKIP, (
        "a pmoves-ui whose database check failed on credentials must SKIP -- "
        "the smoke host has no service key in scope, which is the same "
        "situation test_archon.py already skips"
    )

    # MEASURED on the operator workstation (2026-11-20): the SAME check failed
    # with a stale credential instead of a missing one --
    # {"database":{"status":"unhealthy","error":"JWT expired"}}. A credential
    # that is present but NOT ACCEPTED is the same situation to a smoke probe
    # as a credential that is absent: the database check cannot be judged on
    # this host. Treating only "Unauthorized" as skippable would make the
    # verdict depend on WHICH credential failure the service happened to
    # report, which is not a distinction the probe can make.
    expired_jwt = {
        "status": "degraded",
        "service": "pmoves-ui",
        "checks": {"database": {"status": "unhealthy", "error": "JWT expired"}},
    }
    assert classify_pmoves_ui_health(503, expired_jwt) == SKIP, (
        "a pmoves-ui whose database check failed on an EXPIRED credential must "
        "SKIP for the same reason an unauthorized one skips -- MEASURED on the "
        "operator workstation, the probe cannot judge the database check when "
        "the host's credential is not accepted"
    )

    genuinely_degraded = {
        "status": "degraded",
        "service": "pmoves-ui",
        "checks": {"database": {"status": "unhealthy", "error": "connection refused"}},
    }
    assert classify_pmoves_ui_health(503, genuinely_degraded) == FAIL, (
        "a pmoves-ui whose database check failed for a reason OTHER than "
        "credentials must still FAIL -- the skip is narrow on purpose"
    )

    assert classify_pmoves_ui_health(200, {"status": "ok"}) == PASS
    assert classify_pmoves_ui_health(307, None) == PASS
    assert classify_pmoves_ui_health(500, None) == FAIL


def test_the_credential_marker_set_is_the_enumerated_one() -> None:
    """The skip's blast radius is enumerated, not open-ended.

    Every marker names a credential-acceptance failure -- the host's
    credential for the database was not accepted, so the check cannot be
    judged here. A genuine dependency failure must never be in this set: if
    it were, a real outage would SKIP and the gate would go blind.

    Asserting the exact tuple is what makes WIDENING the set a deliberate,
    visible change instead of an accidental one.
    """
    assert CREDENTIAL_MARKERS == (
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
    ), (
        f"the credential marker set is {CREDENTIAL_MARKERS!r} -- it must stay "
        "the enumerated set of credential-acceptance failures. A genuine "
        "dependency failure (connection refused, timeout, host not found) must "
        "NEVER appear here: it would turn a real outage into a SKIP and make "
        "the smoke gate blind to it."
    )

    for marker in CREDENTIAL_MARKERS:
        assert "connection" not in marker, (
            f"{marker!r} names a dependency failure, not a credential failure"
        )


ARCHON_TEST = PMOVES_ROOT / "tests" / "smoke" / "test_archon.py"


def _archon_test_source() -> str:
    return ARCHON_TEST.read_text(encoding="utf-8")


def test_the_archon_smoke_tests_probe_the_catalog_health_path() -> None:
    """The archon probes must follow the catalog, not a frozen path.

    Archon 0.10.1's UI catch-all answers EVERY unregistered path with the
    SPA HTML page and a 200. A JSON probe of one of those paths therefore
    raises ``JSONDecodeError`` instead of returning a document -- and a 200
    means the fixture's "404 -> skip" guard never fires, so the failure is
    not softened by a skip either. MEASURED: that is how four archon smoke
    tests failed on PR #3482's own CI.
    """
    source = _archon_test_source()
    assert '"/healthz"' not in source, (
        "pmoves/tests/smoke/test_archon.py still probes the literal path "
        "/healthz -- MEASURED, Archon 0.10.1 answers that path with the UI "
        "catch-all HTML (200 text/html), so the probe raises JSONDecodeError"
    )
    assert "ARCHON.health_path" in source, (
        "pmoves/tests/smoke/test_archon.py no longer probes the catalog's "
        "health path -- the probes must follow the single source of truth"
    )


def test_the_archon_openapi_path_sits_beside_the_catalog_health_path() -> None:
    """Archon's API is mounted under /api; the OpenAPI spec lives there too."""
    source = _archon_test_source()
    match = re.search(r'ARCHON_OPENAPI_PATH\s*=\s*"([^"]+)"', source)
    assert match is not None, (
        "pmoves/tests/smoke/test_archon.py no longer declares "
        "ARCHON_OPENAPI_PATH"
    )
    expected = ARCHON.health_path.rsplit("/", 1)[0] + "/openapi.json"
    assert match.group(1) == expected, (
        f"the archon OpenAPI path is {match.group(1)!r} but the catalog's "
        f"health path puts the API under {expected.rsplit('/', 1)[0]!r} -- "
        "MEASURED, /openapi.json returns the UI catch-all HTML while "
        "/api/openapi.json returns the spec"
    )
