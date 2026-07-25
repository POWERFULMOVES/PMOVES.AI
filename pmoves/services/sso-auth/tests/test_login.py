# pmoves/services/sso-auth/tests/test_login.py
import time
import pytest
import httpx
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
    # Isolate from the shared module-level `client`'s cookie jar: a prior test
    # may have left a session cookie set, which would make /logout attempt a
    # real (unmocked) GoTrue revoke call here. This test only cares about the
    # cookie-clearing + redirect contract, not revoke behavior.
    client.cookies.clear()
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert 'pmoves_session=""' in r.headers.get("set-cookie","") or "pmoves_session=;" in r.headers.get("set-cookie","").replace(" ","")

def test_login_rejects_open_redirect(monkeypatch):
    # SECURITY: off-domain / bypass-crafted rd must NOT be honored — falls to '/'.
    monkeypatch.setattr(gotrue, "password_grant", lambda email, pw: {"access_token": _access(email)})
    bad = ["https://evil.com/x", "//evil.com", "/\\evil.com",
           "https://health.pmoves.ai.evil.com/", "https://evilpmoves.ai",
           "https://health.pmoves.ai@evil.com", "\thttps://evil.com"]
    for rd in bad:
        r = client.post("/login", data={"email":"a@b.co","password":"pw","rd":rd}, follow_redirects=False)
        assert r.headers["location"] == "/", f"open redirect not blocked for {rd!r}"
    # in-domain (absolute) and same-origin (relative) rds ARE honored
    for rd in ("https://health.pmoves.ai/dash", "/dashboard"):
        r = client.post("/login", data={"email":"a@b.co","password":"pw","rd":rd}, follow_redirects=False)
        assert r.headers["location"] == rd, f"in-domain rd wrongly rejected: {rd!r}"

def test_bad_login_shows_error(monkeypatch):
    # A rejected password redirects to /login?...&e=1, and the GET login page renders the error.
    def _boom(email, pw): raise gotrue.GoTrueError("bad creds")
    monkeypatch.setattr(gotrue, "password_grant", _boom)
    r = client.post("/login", data={"email":"a@b.co","password":"wrong","rd":"/"}, follow_redirects=False)
    assert r.status_code in (302, 303) and r.headers["location"].startswith("/login") and "e=1" in r.headers["location"]
    page = client.get("/login?e=1")
    assert b"Sign-in failed" in page.content

def test_callback_error_redirects_to_login(monkeypatch):
    # A stale/replayed OAuth code must NOT 500 — it redirects back to /login.
    def _boom(code): raise gotrue.GoTrueError("bad code")
    monkeypatch.setattr(gotrue, "exchange_code", _boom)
    r = client.get("/callback?code=x&rd=/dash", follow_redirects=False)
    assert r.status_code in (302, 303) and r.headers["location"].startswith("/login")

def test_logout_redirects_local_and_revokes(monkeypatch):
    # /logout must go to the browser-reachable local /login (NOT the internal
    # gotrue_url) and best-effort server-side revoke the token.
    called = {}
    monkeypatch.setattr(gotrue, "logout", lambda t: called.setdefault("token", t))
    r = client.get("/logout", cookies={"pmoves_session": "sometoken"}, follow_redirects=False)
    assert r.headers["location"] == "/login"
    assert called.get("token") == "sometoken"

def test_gotrue_outage_becomes_gotrue_error(monkeypatch):
    # A GoTrue OUTAGE (transport error) must surface as GoTrueError so the
    # endpoint handlers' `except GoTrueError` catch it — never a raw httpx
    # exception that would 500 the login/callback (fail-closed invariant).
    def _down(*a, **k): raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(gotrue.httpx, "post", _down)
    with pytest.raises(gotrue.GoTrueError):
        gotrue.password_grant("a@b.co", "pw")
    with pytest.raises(gotrue.GoTrueError):
        gotrue.exchange_code("somecode")
    with pytest.raises(gotrue.GoTrueError):
        gotrue.logout("sometoken")

def test_logout_clears_cookie_even_when_gotrue_down(monkeypatch):
    # /logout stays fail-closed: a GoTrue outage must NOT stop the local cookie
    # from being cleared, and must still redirect to the local /login (never 500).
    def _down(*a, **k): raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(gotrue.httpx, "post", _down)
    client.cookies.clear()
    r = client.get("/logout", cookies={"pmoves_session": "sometoken"}, follow_redirects=False)
    assert r.headers["location"] == "/login"
    assert 'pmoves_session=""' in r.headers.get("set-cookie", "") or "pmoves_session=;" in r.headers.get("set-cookie", "")
