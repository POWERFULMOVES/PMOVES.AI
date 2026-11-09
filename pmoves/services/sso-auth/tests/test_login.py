# pmoves/services/sso-auth/tests/test_login.py
import time
import pytest
import httpx
from jose import jwt
from fastapi.testclient import TestClient
import config
import gotrue
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
                 "JELLYFIN_OIDC_CLIENT_ID": "jf", "JELLYFIN_OIDC_CLIENT_SECRET": "s",
                 "SSO_FORWARD_AUTH_SECRET": "proxy-shared-secret-xyz"}.items():
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

def test_authorize_url_falls_back_to_internal_when_public_unset():
    # No GOTRUE_PUBLIC_URL in the fixture => behaviour is exactly as before, so
    # single-host deployments where GoTrue is already reachable don't change.
    assert gotrue.provider_authorize_url("github", "https://auth.pmoves.ai/callback") \
        .startswith("http://gotrue:9999/authorize?")

def test_authorize_url_uses_public_url_when_set(monkeypatch):
    # The regression this guards: the /authorize link is rendered into the login
    # page and followed by the USER'S BROWSER, so it must never carry the compose
    # service name. Server-side calls keep using GOTRUE_URL.
    monkeypatch.setenv("GOTRUE_PUBLIC_URL", "https://auth.pmoves.ai/gotrue")
    config.settings._reset()
    url = gotrue.provider_authorize_url("github", "https://auth.pmoves.ai/callback")
    assert url.startswith("https://auth.pmoves.ai/gotrue/authorize?")
    assert "gotrue:9999" not in url
    # ...and the internal URL is untouched for server-to-server use.
    assert config.settings.gotrue_url == "http://gotrue:9999"

def test_login_page_link_is_browser_reachable_when_public_url_set(monkeypatch):
    monkeypatch.setenv("GOTRUE_PUBLIC_URL", "https://auth.pmoves.ai/gotrue")
    config.settings._reset()
    r = client.get("/login?rd=https://health.pmoves.ai")
    assert r.status_code == 200
    assert b"supabase-gotrue:9999" not in r.content and b"gotrue:9999" not in r.content
    assert b"https://auth.pmoves.ai/gotrue/authorize" in r.content

def test_google_button_hidden_by_default():
    # SSO_GOOGLE_ENABLED unset (the _env fixture doesn't set it) => no button,
    # so we never bounce a user off a GoTrue "provider disabled" error.
    r = client.get("/login")
    assert r.status_code == 200 and b"Sign in with Google" not in r.content

def test_google_button_shown_when_enabled(monkeypatch):
    monkeypatch.setenv("SSO_GOOGLE_ENABLED", "true")
    config.settings._reset()
    r = client.get("/login?rd=https://health.pmoves.ai")
    assert r.status_code == 200 and b"Sign in with Google" in r.content
    # The button must drive GoTrue's google external-provider handshake, with
    # our /callback (carrying rd) as the return target.
    assert "provider=google" in r.text
    assert "redirect_to=" in r.text and "%2Fcallback" in r.text

def test_post_login_sets_cookie_then_verify_ok(monkeypatch):
    monkeypatch.setattr(gotrue, "password_grant", lambda email, pw: {"access_token": _access(email)})
    r = client.post("/login", data={"email":"a@b.co","password":"pw","rd":"https://health.pmoves.ai"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    cookie = r.cookies.get("pmoves_session"); assert cookie
    v = client.get("/auth/verify", cookies={"pmoves_session": cookie})
    assert v.status_code == 200 and v.headers["Remote-User"] == "a@b.co"

def test_verify_emits_forward_auth_secret_on_200(monkeypatch):
    # Proof-of-proxy: /auth/verify must emit X-Forward-Auth-Secret on success so
    # Traefik forwards it and apps can confirm the request transited the proxy.
    monkeypatch.setattr(gotrue, "password_grant", lambda email, pw: {"access_token": _access(email)})
    cookie = client.post("/login", data={"email":"a@b.co","password":"pw","rd":"/"},
                         follow_redirects=False).cookies.get("pmoves_session")
    v = client.get("/auth/verify", cookies={"pmoves_session": cookie})
    assert v.status_code == 200
    assert v.headers.get("X-Forward-Auth-Secret") == "proxy-shared-secret-xyz"

def test_verify_401_omits_forward_auth_secret():
    # No session -> 401 and no secret leaked. (Default Accept is */*, i.e. NOT a
    # browser navigation, so this stays a bare 401 — see the redirect tests below.)
    client.cookies.clear()
    v = client.get("/auth/verify")
    assert v.status_code == 401 and "x-forward-auth-secret" not in {k.lower() for k in v.headers}

def test_verify_redirects_browser_to_login_with_rd():
    # A browser (Accept: text/html) with no session must get a 302 to the login
    # page carrying the ORIGINAL url (rebuilt from the X-Forwarded-* headers Traefik
    # injects) as rd — not a dead 401. Traefik passes this non-2xx verify response
    # to the browser unchanged, so the 302 becomes a real redirect it can follow.
    client.cookies.clear()
    r = client.get("/auth/verify", headers={
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "x-forwarded-proto": "https",
        "x-forwarded-host": "notebook.pmoves.ai",
        "x-forwarded-uri": "/dash?x=1",
    }, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    # Location host is always our own auth origin (trusted), never the forwarded host.
    assert loc.startswith("https://auth.pmoves.ai/login?")
    # rd is the original notebook URL, url-encoded, so post-login returns the user there.
    assert "rd=https%3A%2F%2Fnotebook.pmoves.ai%2Fdash%3Fx%3D1" in loc

def test_verify_api_client_gets_bare_401_not_redirect():
    # An XHR/fetch/API caller (no text/html in Accept) must get a clean 401, never a
    # 302 to an HTML login page — that would corrupt an API response and mask the
    # real auth failure.
    client.cookies.clear()
    r = client.get("/auth/verify", headers={"accept": "application/json"}, follow_redirects=False)
    assert r.status_code == 401
    assert "location" not in {k.lower() for k in r.headers}

def test_verify_redirect_rejects_spoofed_forwarded_host():
    # SECURITY: a spoofed X-Forwarded-Host outside *.pmoves.ai must NOT become the
    # post-login rd — _safe_rd collapses it to '/', and the Location host stays our
    # own public_base_url regardless.
    client.cookies.clear()
    r = client.get("/auth/verify", headers={
        "accept": "text/html",
        "x-forwarded-proto": "https",
        "x-forwarded-host": "evil.com",
        "x-forwarded-uri": "/steal",
    }, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://auth.pmoves.ai/login?")
    assert "rd=%2F" in loc and "evil.com" not in loc

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
