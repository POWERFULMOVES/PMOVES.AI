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
                 "JELLYFIN_OIDC_CLIENT_ID": "jf", "JELLYFIN_OIDC_CLIENT_SECRET": "sec"}.items():
        monkeypatch.setenv(k, v)
    config.settings._reset()
    yield
    config.settings._reset()

def test_discovery_lists_endpoints():
    d=client.get("/.well-known/openid-configuration").json()
    assert d["issuer"]=="https://auth.pmoves.ai"
    assert d["authorization_endpoint"].endswith("/oidc/authorize")
    assert d["token_endpoint"].endswith("/oidc/token")

def test_token_endpoint_mints_id_token():
    sess=jwt.encode({"sub":"u1","email":"a@b.co","role":"authenticated","exp":int(time.time())+3600}, SECRET, algorithm="HS256")
    code=oidc._issue_code(sess)  # helper: bind an auth code to a validated session
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,
        "client_id":"jf","client_secret":"sec","redirect_uri":"https://media.pmoves.ai/sso/OID/redirect/pmoves"})
    assert r.status_code==200
    idt=r.json()["id_token"]; claims=jwt.decode(idt, SECRET, algorithms=["HS256"], audience="jf")
    assert claims["email"]=="a@b.co"

def test_token_rejects_bad_client_secret():
    sess=jwt.encode({"sub":"u1","email":"a@b.co","role":"authenticated","exp":int(time.time())+3600}, SECRET, algorithm="HS256")
    code=oidc._issue_code(sess)
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,"client_id":"jf","client_secret":"WRONG","redirect_uri":"x"})
    assert r.status_code==401
