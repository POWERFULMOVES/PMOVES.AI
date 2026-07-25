# pmoves/services/sso-auth/tests/test_login.py
import time
import pytest
from jose import jwt
from fastapi.testclient import TestClient
import config, gotrue
import app as appmod

SECRET = "test-secret-value-at-least-32-chars-long!!"

# base_url must be a real *.pmoves.ai host: the session cookie is Domain=.pmoves.ai,
# and httpx's cookie jar drops cookies whose Domain doesn't suffix-match the request host.
client = TestClient(appmod.app, base_url="https://auth.pmoves.ai")

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Set env + reset the lazy settings proxy per test. NO module-level env-set
    or importlib.reload — those pollute the shared `config` module and break other
    test files when the full suite runs. The lazy proxy + _reset() is all we need."""
    for k, v in {"SUPABASE_JWT_SECRET": SECRET, "GOTRUE_URL": "http://gotrue:9999",
                 "PUBLIC_BASE_URL": "https://auth.pmoves.ai",
                 "JELLYFIN_OIDC_CLIENT_ID": "jf", "JELLYFIN_OIDC_CLIENT_SECRET": "s"}.items():
        monkeypatch.setenv(k, v)
    config.settings._reset()
    yield
    config.settings._reset()

def _access(email="a@b.co"):
    # role='authenticated' is REQUIRED — verify_session (Task 1) rejects any other role.
    return jwt.encode({"sub":"u1","email":email,"role":"authenticated","exp":int(time.time())+3600}, SECRET, algorithm="HS256")

def test_login_page_renders():
    r = client.get("/login?rd=https://health.pmoves.ai")
    assert r.status_code == 200 and b"Sign in with GitHub" in r.content

def test_post_login_sets_cookie_then_verify_ok(monkeypatch):
    monkeypatch.setattr(gotrue, "password_grant", lambda email, pw: {"access_token": _access(email)})
    r = client.post("/login", data={"email":"a@b.co","password":"pw","rd":"https://health.pmoves.ai"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    cookie = r.cookies.get("pmoves_session"); assert cookie
    v = client.get("/auth/verify", cookies={"pmoves_session": cookie})
    assert v.status_code == 200 and v.headers["Remote-User"] == "a@b.co"

def test_logout_clears_cookie():
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert 'pmoves_session=""' in r.headers.get("set-cookie","") or "pmoves_session=;" in r.headers.get("set-cookie","").replace(" ","")
