# pmoves/services/sso-auth/tests/test_oidc.py
import time
import pytest
from jose import jwt
from fastapi.testclient import TestClient
import config, oidc
import app as appmod

SECRET = "test-secret-value-at-least-32-chars-long!!"
client = TestClient(appmod.app, base_url="https://auth.pmoves.ai")

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Env + lazy-proxy reset per test — NO module-level reload/setenv (pollutes
    the shared config module across test files)."""
    for k, v in {"SUPABASE_JWT_SECRET": SECRET, "GOTRUE_URL": "http://g:9999",
                 "PUBLIC_BASE_URL": "https://auth.pmoves.ai",
                 "JELLYFIN_OIDC_CLIENT_ID": "jf", "JELLYFIN_OIDC_CLIENT_SECRET": "sec",
                 "JELLYFIN_OIDC_REDIRECT_URIS": RD}.items():
        monkeypatch.setenv(k, v)
    config.settings._reset()
    yield
    config.settings._reset()

RD = "https://media.pmoves.ai/sso/OID/redirect/pmoves"  # the single registered redirect_uri

def _sess():
    return jwt.encode({"sub":"u1","email":"a@b.co","role":"authenticated","exp":int(time.time())+3600}, SECRET, algorithm="HS256")

def test_discovery_lists_endpoints():
    d=client.get("/.well-known/openid-configuration").json()
    assert d["issuer"]=="https://auth.pmoves.ai"
    assert d["authorization_endpoint"].endswith("/oidc/authorize")
    assert d["token_endpoint"].endswith("/oidc/token")

def test_token_endpoint_mints_id_token():
    code=oidc._issue_code(_sess(), RD)  # helper: bind an auth code to a validated session + redirect_uri
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,
        "client_id":"jf","client_secret":"sec","redirect_uri":RD})
    assert r.status_code==200
    idt=r.json()["id_token"]; claims=jwt.decode(idt, SECRET, algorithms=["HS256"], audience="jf")
    assert claims["email"]=="a@b.co"

def test_token_rejects_bad_client_secret():
    code=oidc._issue_code(_sess(), RD)
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,"client_id":"jf","client_secret":"WRONG","redirect_uri":RD})
    assert r.status_code==401

def test_token_rejects_mismatched_redirect_uri():
    # A code minted for the registered URI must not be redeemable against another.
    code=oidc._issue_code(_sess(), RD)
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,
        "client_id":"jf","client_secret":"sec","redirect_uri":"https://evil.example/cb"})
    assert r.status_code==400

def test_authorize_rejects_unregistered_redirect_uri():
    # Open-redirect / auth-code-leak guard: an authed user lured to authorize with
    # an attacker redirect_uri must get 400 (NO Location header), never a code.
    sess=_sess()
    r=client.get(f"/oidc/authorize?client_id=jf&redirect_uri=https://evil.example/cb&state=x",
                 cookies={"pmoves_session":sess}, follow_redirects=False)
    assert r.status_code==400
    assert "location" not in {k.lower() for k in r.headers}

def test_authorize_rejects_wrong_client_id():
    sess=_sess()
    r=client.get(f"/oidc/authorize?client_id=WRONG&redirect_uri={RD}&state=x",
                 cookies={"pmoves_session":sess}, follow_redirects=False)
    assert r.status_code==400

def test_authorize_registered_uri_issues_code():
    # The happy path still works: registered client_id + redirect_uri + valid
    # session → 303 to the registered URI carrying a code.
    sess=_sess()
    r=client.get(f"/oidc/authorize?client_id=jf&redirect_uri={RD}&state=xyz",
                 cookies={"pmoves_session":sess}, follow_redirects=False)
    assert r.status_code==303
    loc=r.headers["location"]
    assert loc.startswith(RD) and "code=" in loc and "state=xyz" in loc
