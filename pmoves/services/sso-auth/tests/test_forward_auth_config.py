"""The Traefik side of the browser login-redirect contract.

`/auth/verify` returning a 302 is necessary but NOT sufficient: Traefik decides
whether the browser ever sees that Location. Per Traefik's ForwardAuth docs,
`preserveLocationHeader` "defines whether to forward the Location header to the
client as is or prefix it with the domain name of the authentication server",
and it **defaults to false**.

With the default, a 302 to `https://auth.pmoves.ai/login?rd=...` is rewritten to
the middleware's own `address` host -- `http://pmoves-sso-auth:8080/login` -- an
internal container name no browser can resolve. The user lands on a dead end,
which is the exact symptom the redirect was added to fix.

The application-side behaviour is covered in test_login.py. This file covers the
half that lives in configuration, because a config default is not visible in any
Python test and was missed on the first pass.
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

DYNAMIC = (
    Path(__file__).resolve().parents[3] / "config" / "traefik" / "dynamic.yml"
)


@pytest.fixture(scope="module")
def forward_auth() -> dict:
    assert DYNAMIC.is_file(), f"missing {DYNAMIC}"
    doc = yaml.safe_load(DYNAMIC.read_text(encoding="utf-8"))
    mw = doc["http"]["middlewares"]["pmoves-forward-auth"]["forwardAuth"]
    return mw


def test_location_header_is_preserved(forward_auth: dict) -> None:
    assert forward_auth.get("preserveLocationHeader") is True, (
        "preserveLocationHeader defaults to FALSE in Traefik; without it set to "
        "true the 302 from /auth/verify is rewritten to the forwardAuth address "
        "host and the browser gets an unreachable container name"
    )


def test_address_is_internal_which_is_why_preserving_matters(forward_auth: dict) -> None:
    """Pins the premise of the test above.

    If the auth service ever became publicly addressable, rewriting would be
    harmless and this whole contract would stop mattering. It is internal, so it
    does matter -- assert that rather than leave it implied.
    """
    address = forward_auth["address"]
    assert address.startswith("http://"), address
    host = address.split("://", 1)[1].split("/", 1)[0]
    assert "." not in host.split(":")[0], (
        f"{host!r} looks publicly resolvable; if the auth service moved to a real "
        "hostname, re-check whether preserveLocationHeader is still required"
    )


def test_auth_response_headers_still_carry_identity(forward_auth: dict) -> None:
    """Guard against a careless edit to the same block dropping identity headers."""
    headers = forward_auth.get("authResponseHeaders") or []
    for required in ("Remote-User", "X-Auth-Email", "X-Auth-Subject"):
        assert required in headers, f"{required} missing from authResponseHeaders"
