# PMOVES SSO Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pmoves-sso-auth` (a forward-auth service) + a Traefik edge so one Supabase login gives browser-seamless access to wger, Firefly III, Open-Notebook, and Jellyfin.

**Architecture:** Traefik (edge, subdomains on `*.pmoves.ai`) runs a ForwardAuth middleware that subrequests `pmoves-sso-auth /auth/verify`. That FastAPI service validates a Supabase-JWT session cookie (HS256, reusing BoTZ's verify pattern) and returns `Remote-User`/`X-Auth-Email` headers, which Traefik injects into the upstream app. Firefly/wger/open-notebook trust that header; Jellyfin (no header auth) uses the `Ezeqielle/jellyfin-plugin-oidc` plugin against a minimal OIDC subset the same service exposes. Supabase GoTrue is the only IdP.

**Tech Stack:** Python 3.12 / FastAPI / uvicorn / `python-jose[cryptography]` (JWT), `httpx` (GoTrue), Jinja2 (login page); Traefik v3; Docker Compose.

## Global Constraints

- Supabase GoTrue is the ONLY IdP; reuse `SUPABASE_JWT_SECRET` (alias of `JWT_SECRET`) — NO new IdP, NO new long-lived secret, NO separate user store.
- JWT is HS256 today; verification must be swappable for a future JWKS/RS256 migration (isolate verify in one module).
- Apps are PMOVES forks — prefer env/config over code; code changes ONLY where no header-auth config exists (open-notebook).
- Only Traefik may set `Remote-User`; app containers must NOT publish host ports (reachable only via Traefik).
- Env pipeline: add keys to `pmoves/env.shared.example` + `pmoves/chit/secrets_manifest_v2.yaml`; never inline secrets in compose.
- Known-Road domains gate edits: `compose` (docker-compose*.yml), `dockerfile` (Dockerfiles), `migrations` (supabase SQL). Compose/Dockerfile edits in this plan need the operator's grant for that domain at execution time.
- Cookie: `pmoves_session`, HttpOnly, Secure, SameSite=Lax, `Domain=.pmoves.ai`.
- Firefly MFA must be OFF when remote-user auth is on.
- The forward-auth hot path (`/auth/verify`) does local HS256 verify only — NO network calls.
- Prerequisite (separate PR, NOT in this plan): firefly's tmpfs-500 fix (uid=33 on the storage tmpfs) — firefly must serve before its SSO leg can be validated end-to-end.

---

### Task 1: `pmoves-sso-auth` scaffold — config + JWT verify + `/auth/verify` + `/healthz`

**Files:**
- Create: `pmoves/services/sso-auth/config.py`
- Create: `pmoves/services/sso-auth/jwt_verify.py`
- Create: `pmoves/services/sso-auth/app.py`
- Create: `pmoves/services/sso-auth/requirements.txt`
- Test: `pmoves/services/sso-auth/tests/test_jwt_verify.py`

**Interfaces:**
- Produces: `jwt_verify.verify_session(token: str) -> dict` (returns GoTrue claims `{sub, email, exp, ...}`; raises `SessionInvalid` on bad/expired/absent). `config.Settings` (pydantic) with `supabase_jwt_secret: str`, `gotrue_url: str`, `cookie_domain: str = ".pmoves.ai"`, `cookie_name: str = "pmoves_session"`, `session_ttl_seconds: int = 3600`, `jellyfin_oidc_client_id: str`, `jellyfin_oidc_client_secret: str`, `public_base_url: str` (e.g. `https://auth.pmoves.ai`).
- FastAPI app `app` with `GET /healthz` and `GET /auth/verify`.

- [ ] **Step 1: Write `requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-jose[cryptography]==3.3.0
httpx==0.28.1
jinja2==3.1.5
pydantic-settings==2.7.1
```

- [ ] **Step 2: Write the failing test**

```python
# pmoves/services/sso-auth/tests/test_jwt_verify.py
import time, pytest
from jose import jwt
import config
from jwt_verify import verify_session, SessionInvalid

SECRET = "test-secret-value-at-least-32-chars-long!!"

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Set the required env, then reset the lazy settings proxy so it re-reads.
    verify_session() reads settings.<field> at call time, so no module reload
    is needed."""
    for k, v in {"SUPABASE_JWT_SECRET": SECRET, "GOTRUE_URL": "http://gotrue:9999",
                 "PUBLIC_BASE_URL": "https://auth.pmoves.ai",
                 "JELLYFIN_OIDC_CLIENT_ID": "jf", "JELLYFIN_OIDC_CLIENT_SECRET": "s"}.items():
        monkeypatch.setenv(k, v)
    config.settings._reset()
    yield
    config.settings._reset()

def _tok(**over):
    claims = {"sub": "user-123", "email": "a@b.co", "exp": int(time.time()) + 60, "role": "authenticated"}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")

def test_valid_token_returns_claims():
    claims = verify_session(_tok())
    assert claims["email"] == "a@b.co" and claims["sub"] == "user-123"

def test_expired_token_raises():
    with pytest.raises(SessionInvalid):
        verify_session(_tok(exp=int(time.time()) - 10))

def test_tampered_token_raises():
    with pytest.raises(SessionInvalid):
        verify_session(jwt.encode({"sub": "x", "exp": int(time.time()) + 60},
                                  "wrong-secret-wrong-secret-wrong!!", algorithm="HS256"))

def test_empty_token_raises():
    with pytest.raises(SessionInvalid):
        verify_session("")

def test_non_authenticated_role_rejected():
    # A validly-SIGNED token whose role != 'authenticated' (e.g. Supabase's
    # PUBLIC anon key, signed with the same secret) must NOT authenticate —
    # signature validity alone is insufficient.
    anon = jwt.encode({"sub": "anon", "role": "anon", "exp": int(time.time()) + 60},
                      SECRET, algorithm="HS256")
    with pytest.raises(SessionInvalid):
        verify_session(anon)

def test_verify_works_without_oidc_env(monkeypatch):
    # The /auth/verify hot path must NOT depend on the Jellyfin OIDC config —
    # removing it must still verify (fail-closed contract), not raise KeyError→500.
    monkeypatch.delenv("JELLYFIN_OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("JELLYFIN_OIDC_CLIENT_SECRET", raising=False)
    config.settings._reset()
    claims = verify_session(_tok())
    assert claims["role"] == "authenticated"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd pmoves/services/sso-auth && uv run --with-requirements requirements.txt --with pytest --with pytest-asyncio python -m pytest tests/test_jwt_verify.py -q`
Expected: FAIL (`ModuleNotFoundError: jwt_verify`).

- [ ] **Step 4: Write `config.py`**

```python
# pmoves/services/sso-auth/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    supabase_jwt_secret: str          # env: SUPABASE_JWT_SECRET
    gotrue_url: str                   # env: GOTRUE_URL (internal http://supabase-gotrue:9999)
    public_base_url: str              # env: PUBLIC_BASE_URL (https://auth.pmoves.ai)
    cookie_domain: str = ".pmoves.ai" # env: SSO_COOKIE_DOMAIN
    cookie_name: str = "pmoves_session"
    session_ttl_seconds: int = 3600
    jellyfin_oidc_client_id: str      # env: JELLYFIN_OIDC_CLIENT_ID
    jellyfin_oidc_client_secret: str  # env: JELLYFIN_OIDC_CLIENT_SECRET

    @classmethod
    def load(cls) -> "Settings":
        import os
        g = os.environ.get
        # Only SUPABASE_JWT_SECRET is required — it is all the /auth/verify hot
        # path needs. The login/OIDC fields default to "" so a deployment that
        # hasn't provisioned the Jellyfin OIDC vars still serves forward-auth
        # (those paths fail at request time if actually used, not at verify).
        return cls(
            supabase_jwt_secret=os.environ["SUPABASE_JWT_SECRET"],
            gotrue_url=g("GOTRUE_URL", ""),
            public_base_url=g("PUBLIC_BASE_URL", ""),
            cookie_domain=g("SSO_COOKIE_DOMAIN", ".pmoves.ai"),
            jellyfin_oidc_client_id=g("JELLYFIN_OIDC_CLIENT_ID", ""),
            jellyfin_oidc_client_secret=g("JELLYFIN_OIDC_CLIENT_SECRET", ""),
        )


class _LazySettings:
    """Lazy settings proxy — reads env on FIRST attribute access, NOT at import.
    So the service starts under compose env, AND tests set env then call
    `settings._reset()` to force a fresh read. Never read required env at import
    time (that crashes pytest collection when env is unset). All modules import
    this `settings` object and use `settings.<field>` uniformly."""
    _cached = None  # type: Settings | None
    def __getattr__(self, name):
        if _LazySettings._cached is None:
            _LazySettings._cached = Settings.load()
        return getattr(_LazySettings._cached, name)
    def _reset(self):
        _LazySettings._cached = None

settings = _LazySettings()
```

- [ ] **Step 5: Write `jwt_verify.py`** (mirrors `PMOVES-BoTZ/features/mcp_bridge/auth.py` `validate_jwt`)

```python
# pmoves/services/sso-auth/jwt_verify.py
from jose import jwt, JWTError
from config import settings

class SessionInvalid(Exception):
    """Session cookie absent, malformed, expired, or signature-invalid."""

def verify_session(token: str) -> dict:
    if not token:
        raise SessionInvalid("empty token")
    secret = settings.supabase_jwt_secret  # lazy proxy: reads env on first access
    try:
        claims = jwt.decode(
            token, secret, algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise SessionInvalid(str(e)) from e
    # SECURITY: only a real GoTrue *session* token authenticates. Supabase's
    # anon and service_role keys are signed with the SAME secret but carry
    # role 'anon' / 'service_role' — and the anon key is PUBLIC by design.
    # Require the session role, else a public value would authenticate.
    if claims.get("role") != "authenticated":
        raise SessionInvalid(f"non-session role: {claims.get('role')!r}")
    return claims
```

- [ ] **Step 6: Write `app.py` (verify + healthz only for this task)**

```python
# pmoves/services/sso-auth/app.py
from fastapi import FastAPI, Request, Response
from config import settings
from jwt_verify import verify_session, SessionInvalid

app = FastAPI(title="pmoves-sso-auth")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/auth/verify")
def auth_verify(request: Request):
    """Traefik ForwardAuth target. 200 + identity headers, or 401."""
    token = request.cookies.get(settings.cookie_name, "")
    try:
        claims = verify_session(token)
    except SessionInvalid:
        return Response(status_code=401)
    ident = claims.get("email") or claims.get("sub") or ""
    return Response(
        status_code=200,
        headers={
            "Remote-User": ident,
            "X-Auth-Email": claims.get("email", ""),
            "X-Auth-Subject": claims.get("sub", ""),
        },
    )
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd pmoves/services/sso-auth && uv run --with-requirements requirements.txt --with pytest --with pytest-asyncio python -m pytest tests/test_jwt_verify.py -q`
Expected: PASS (4 passed).

- [ ] **Step 8: Commit**

```bash
git add pmoves/services/sso-auth/{config.py,jwt_verify.py,app.py,requirements.txt,tests/test_jwt_verify.py}
git commit -m "feat(sso-auth): scaffold service + Supabase-JWT verify + /auth/verify"
```

---

### Task 2: GoTrue login flow — `/login`, `POST /login`, `/callback`, `/logout` + cookie issuance

**Files:**
- Create: `pmoves/services/sso-auth/gotrue.py`
- Create: `pmoves/services/sso-auth/templates/login.html`
- Modify: `pmoves/services/sso-auth/app.py` (add login/callback/logout routes)
- Test: `pmoves/services/sso-auth/tests/test_login.py`

**Interfaces:**
- Consumes: `config.settings`, `jwt_verify.verify_session`.
- Produces: `gotrue.password_grant(email, password) -> dict` (GoTrue token response `{access_token, refresh_token, ...}`; raises `GoTrueError`); `gotrue.github_authorize_url(redirect_to) -> str`; `gotrue.exchange_code(...) -> dict`. Cookie set helper `app._set_session(resp, access_token)`.

- [ ] **Step 1: Write the failing test**

```python
# pmoves/services/sso-auth/tests/test_login.py
import time, os
import pytest
from jose import jwt
from fastapi.testclient import TestClient

SECRET = "test-secret-value-at-least-32-chars-long!!"
for k, v in {"SUPABASE_JWT_SECRET": SECRET, "GOTRUE_URL": "http://gotrue:9999",
             "PUBLIC_BASE_URL": "https://auth.pmoves.ai", "JELLYFIN_OIDC_CLIENT_ID": "jf",
             "JELLYFIN_OIDC_CLIENT_SECRET": "s"}.items():
    os.environ.setdefault(k, v)
import importlib, config, jwt_verify, gotrue, app as appmod
for m in (config, jwt_verify, gotrue, appmod): importlib.reload(m)
client = TestClient(appmod.app)

def _access(email="a@b.co"):
    return jwt.encode({"sub":"u1","email":email,"exp":int(time.time())+3600}, SECRET, algorithm="HS256")

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/sso-auth && uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_login.py -q`
Expected: FAIL (`ModuleNotFoundError: gotrue`).

- [ ] **Step 3: Write `gotrue.py`**

```python
# pmoves/services/sso-auth/gotrue.py
import httpx
from urllib.parse import urlencode
from config import settings

class GoTrueError(Exception): ...

def password_grant(email: str, password: str) -> dict:
    url = f"{settings.gotrue_url}/token?grant_type=password"
    r = httpx.post(url, json={"email": email, "password": password}, timeout=10.0)
    if r.status_code != 200:
        raise GoTrueError(f"gotrue {r.status_code}")
    return r.json()

def github_authorize_url(redirect_to: str) -> str:
    q = urlencode({"provider": "github", "redirect_to": redirect_to})
    return f"{settings.gotrue_url}/authorize?{q}"

def exchange_code(code: str) -> dict:
    # GoTrue PKCE/code exchange: POST /token?grant_type=pkce (auth code flow).
    url = f"{settings.gotrue_url}/token?grant_type=pkce"
    r = httpx.post(url, json={"auth_code": code}, timeout=10.0)
    if r.status_code != 200:
        raise GoTrueError(f"gotrue exchange {r.status_code}")
    return r.json()
```

- [ ] **Step 4: Write `templates/login.html`**

```html
<!doctype html><html><head><meta charset="utf-8"><title>PMOVES Sign in</title></head>
<body style="font-family:system-ui;max-width:22rem;margin:4rem auto">
  <h1>PMOVES</h1>
  <a href="{{ github_url }}" style="display:block;padding:.6rem;text-align:center;background:#24292e;color:#fff;border-radius:6px;text-decoration:none">Sign in with GitHub</a>
  <p style="text-align:center;color:#888">or</p>
  <form method="post" action="/login">
    <input type="hidden" name="rd" value="{{ rd }}">
    <input name="email" type="email" placeholder="email" required style="width:100%;padding:.5rem;margin:.25rem 0">
    <input name="password" type="password" placeholder="password" required style="width:100%;padding:.5rem;margin:.25rem 0">
    <button type="submit" style="width:100%;padding:.6rem">Sign in</button>
  </form>
  {% if error %}<p style="color:#c00">{{ error }}</p>{% endif %}
</body></html>
```

- [ ] **Step 5: Add login/callback/logout routes to `app.py`**

```python
# append to pmoves/services/sso-auth/app.py
from fastapi import Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import gotrue

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

def _set_session(resp, access_token: str):
    resp.set_cookie(settings.cookie_name, access_token, domain=settings.cookie_domain,
                    httponly=True, secure=True, samesite="lax", max_age=settings.session_ttl_seconds)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, rd: str = "/"):
    cb = f"{settings.public_base_url}/callback?rd={rd}"
    return _templates.TemplateResponse("login.html", {"request": request, "rd": rd,
        "github_url": gotrue.github_authorize_url(cb), "error": None})

@app.post("/login")
def login_submit(email: str = Form(...), password: str = Form(...), rd: str = Form("/")):
    try:
        tok = gotrue.password_grant(email, password)
    except gotrue.GoTrueError:
        return RedirectResponse(f"/login?rd={rd}&e=1", status_code=303)
    resp = RedirectResponse(rd, status_code=303); _set_session(resp, tok["access_token"]); return resp

@app.get("/callback")
def callback(code: str = "", rd: str = "/"):
    tok = gotrue.exchange_code(code)
    resp = RedirectResponse(rd, status_code=303); _set_session(resp, tok["access_token"]); return resp

@app.get("/logout")
def logout():
    resp = RedirectResponse(f"{settings.gotrue_url}/logout", status_code=303)
    resp.delete_cookie(settings.cookie_name, domain=settings.cookie_domain); return resp
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd pmoves/services/sso-auth && uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_login.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add pmoves/services/sso-auth/{gotrue.py,app.py,templates/login.html,tests/test_login.py}
git commit -m "feat(sso-auth): GoTrue login (GitHub + email/pw), cookie issuance, logout"
```

---

### Task 3: Minimal OIDC subset for Jellyfin

**Files:**
- Create: `pmoves/services/sso-auth/oidc.py`
- Modify: `pmoves/services/sso-auth/app.py` (mount OIDC routes)
- Test: `pmoves/services/sso-auth/tests/test_oidc.py`

**Interfaces:**
- Consumes: `config.settings`, the session cookie, `gotrue`.
- Produces routes: `GET /.well-known/openid-configuration`, `GET /oidc/authorize`, `POST /oidc/token`, `GET /oidc/userinfo`. The `id_token` is minted HS256 with `settings.supabase_jwt_secret`, `aud=jellyfin_oidc_client_id`, claims `{sub, email, preferred_username}`.

- [ ] **Step 1: Write the failing test**

```python
# pmoves/services/sso-auth/tests/test_oidc.py
import os, time
from jose import jwt
from fastapi.testclient import TestClient
SECRET="test-secret-value-at-least-32-chars-long!!"
for k,v in {"SUPABASE_JWT_SECRET":SECRET,"GOTRUE_URL":"http://g:9999","PUBLIC_BASE_URL":"https://auth.pmoves.ai","JELLYFIN_OIDC_CLIENT_ID":"jf","JELLYFIN_OIDC_CLIENT_SECRET":"sec"}.items(): os.environ.setdefault(k,v)
import importlib, config, jwt_verify, gotrue, oidc, app as appmod
for m in (config,jwt_verify,gotrue,oidc,appmod): importlib.reload(m)
client=TestClient(appmod.app)

def test_discovery_lists_endpoints():
    d=client.get("/.well-known/openid-configuration").json()
    assert d["issuer"]=="https://auth.pmoves.ai"
    assert d["authorization_endpoint"].endswith("/oidc/authorize")
    assert d["token_endpoint"].endswith("/oidc/token")

def test_token_endpoint_mints_id_token():
    sess=jwt.encode({"sub":"u1","email":"a@b.co","exp":int(time.time())+3600}, SECRET, algorithm="HS256")
    code=oidc._issue_code(sess)  # helper: bind an auth code to a validated session
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,
        "client_id":"jf","client_secret":"sec","redirect_uri":"https://media.pmoves.ai/sso/OID/redirect/pmoves"})
    assert r.status_code==200
    idt=r.json()["id_token"]; claims=jwt.decode(idt, SECRET, algorithms=["HS256"], audience="jf")
    assert claims["email"]=="a@b.co"

def test_token_rejects_bad_client_secret():
    sess=jwt.encode({"sub":"u1","email":"a@b.co","exp":int(time.time())+3600}, SECRET, algorithm="HS256")
    code=oidc._issue_code(sess)
    r=client.post("/oidc/token", data={"grant_type":"authorization_code","code":code,"client_id":"jf","client_secret":"WRONG","redirect_uri":"x"})
    assert r.status_code==401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/services/sso-auth && uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_oidc.py -q`
Expected: FAIL (`ModuleNotFoundError: oidc`).

- [ ] **Step 3: Write `oidc.py`**

```python
# pmoves/services/sso-auth/oidc.py
import secrets, time
from jose import jwt
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import JSONResponse, RedirectResponse
from config import settings
from jwt_verify import verify_session, SessionInvalid

router = APIRouter()
_CODES: dict[str, tuple[str, float]] = {}   # code -> (session_jwt, expiry). In-memory: single replica; fine for Phase 1.
_CODE_TTL = 120

def _issue_code(session_jwt: str) -> str:
    c = secrets.token_urlsafe(24); _CODES[c] = (session_jwt, time.time() + _CODE_TTL); return c

@router.get("/.well-known/openid-configuration")
def discovery():
    b = settings.public_base_url
    return {"issuer": b, "authorization_endpoint": f"{b}/oidc/authorize",
            "token_endpoint": f"{b}/oidc/token", "userinfo_endpoint": f"{b}/oidc/userinfo",
            "jwks_uri": f"{b}/oidc/jwks", "response_types_supported": ["code"],
            "subject_types_supported": ["public"], "id_token_signing_alg_values_supported": ["HS256"],
            "scopes_supported": ["openid", "profile", "email"]}

@router.get("/oidc/authorize")
def authorize(request: Request, redirect_uri: str, state: str = "", client_id: str = ""):
    """User must already have a PMOVES session (Traefik does NOT ForwardAuth this
    service). If not, bounce to /login and come back."""
    token = request.cookies.get(settings.cookie_name, "")
    try:
        verify_session(token)
    except SessionInvalid:
        return RedirectResponse(f"/login?rd={request.url}", status_code=303)
    code = _issue_code(token)
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}", status_code=303)

@router.post("/oidc/token")
def token(grant_type: str = Form(...), code: str = Form(...), client_id: str = Form(...),
          client_secret: str = Form(...), redirect_uri: str = Form("")):
    if client_id != settings.jellyfin_oidc_client_id or client_secret != settings.jellyfin_oidc_client_secret:
        return Response(status_code=401)
    entry = _CODES.pop(code, None)
    if not entry or entry[1] < time.time():
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    claims = verify_session(entry[0])
    now = int(time.time())
    id_token = jwt.encode({"iss": settings.public_base_url, "aud": client_id,
        "sub": claims["sub"], "email": claims.get("email", ""),
        "preferred_username": claims.get("email", claims["sub"]), "iat": now, "exp": now + 300},
        settings.supabase_jwt_secret, algorithm="HS256")
    return {"access_token": id_token, "id_token": id_token, "token_type": "Bearer", "expires_in": 300}

@router.get("/oidc/userinfo")
def userinfo(request: Request):
    auth = request.headers.get("authorization", "")
    tok = auth[7:] if auth.lower().startswith("bearer ") else ""
    try:
        c = jwt.decode(tok, settings.supabase_jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
    except Exception:
        return Response(status_code=401)
    return {"sub": c["sub"], "email": c.get("email", ""), "preferred_username": c.get("preferred_username", c.get("email", c["sub"]))}
```

- [ ] **Step 4: Mount the router in `app.py`**

```python
# append to pmoves/services/sso-auth/app.py
import oidc
app.include_router(oidc.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd pmoves/services/sso-auth && uv run --with-requirements requirements.txt --with pytest python -m pytest tests/test_oidc.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add pmoves/services/sso-auth/{oidc.py,app.py,tests/test_oidc.py}
git commit -m "feat(sso-auth): minimal OIDC subset for jellyfin-plugin-oidc"
```

---

### Task 4: Dockerfile + compose service for `pmoves-sso-auth`

**Files:**
- Create: `pmoves/services/sso-auth/Dockerfile`
- Create: `pmoves/docker-compose.sso.yml`
- Test: manual container build + `/healthz` curl (documented below)

**Interfaces:**
- Consumes: the service code from Tasks 1–3.
- Produces: image `pmoves/sso-auth`, service `pmoves-sso-auth` on `pmoves_app` + `pmoves_external`, listening `:8080`.

- [ ] **Step 1: Write the Dockerfile** (Known-Road: `dockerfile` domain)

```dockerfile
# pmoves/services/sso-auth/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY services/sso-auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/sso-auth/ .
RUN useradd -m -u 1001 pmoves && chown -R pmoves:pmoves /app
USER pmoves
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Write `docker-compose.sso.yml`** (Known-Road: `compose` domain)

```yaml
services:
  sso-auth:
    build: { context: ., dockerfile: services/sso-auth/Dockerfile }
    image: ${SSO_AUTH_IMAGE:-pmoves/sso-auth:local}
    container_name: pmoves-sso-auth
    restart: unless-stopped
    environment:
      SUPABASE_JWT_SECRET: ${SUPABASE_JWT_SECRET:-${JWT_SECRET}}
      GOTRUE_URL: ${GOTRUE_URL:-http://supabase-gotrue:9999}
      PUBLIC_BASE_URL: ${SSO_PUBLIC_BASE_URL:-https://auth.pmoves.ai}
      SSO_COOKIE_DOMAIN: ${SSO_COOKIE_DOMAIN:-.pmoves.ai}
      JELLYFIN_OIDC_CLIENT_ID: ${JELLYFIN_OIDC_CLIENT_ID}
      JELLYFIN_OIDC_CLIENT_SECRET: ${JELLYFIN_OIDC_CLIENT_SECRET}
    networks: { pmoves_app: { aliases: [pmoves-sso-auth] }, pmoves_external: {} }
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
networks:
  pmoves_app: { external: true }
  pmoves_external: { external: true }
```

- [ ] **Step 3: Build + smoke test**

Run: `make -C pmoves compose ARGS="-f docker-compose.sso.yml build sso-auth" && make -C pmoves compose ARGS="-f docker-compose.sso.yml up -d sso-auth"`
Then: `curl -sf http://<sso-auth-host>/healthz` → `{"status":"ok"}` (via the container; it publishes no host port — exec or a sibling container).
Expected: healthz ok; `docker logs pmoves-sso-auth` shows uvicorn started with no config errors.

- [ ] **Step 4: Commit**

```bash
git add pmoves/services/sso-auth/Dockerfile pmoves/docker-compose.sso.yml
git commit -m "feat(sso-auth): Dockerfile + compose service (pmoves_external, no host port)"
```

---

### Task 5: Traefik edge + ForwardAuth middleware + subdomain routers

**Files:**
- Create: `pmoves/docker-compose.traefik.yml`
- Create: `pmoves/config/traefik/dynamic.yml`
- Test: routing + 302-to-login behavior (documented)

**Interfaces:**
- Consumes: `pmoves-sso-auth` (`/auth/verify`), the 4 app services (by container name).
- Produces: Traefik on `:443`, routers `auth/health/wealth/notebook/media.pmoves.ai`, middleware `pmoves-forward-auth`.

- [ ] **Step 1: Write `config/traefik/dynamic.yml`**

```yaml
http:
  middlewares:
    pmoves-forward-auth:
      forwardAuth:
        address: "http://pmoves-sso-auth:8080/auth/verify"
        authResponseHeaders: ["Remote-User", "X-Auth-Email", "X-Auth-Subject"]
        # On 401 Traefik returns the auth service's response; a 401 body/redirect
        # sends the browser to auth.pmoves.ai/login (see errors middleware below).
    pmoves-auth-redirect:
      errors:
        status: ["401"]
        service: sso-auth@docker
        query: "/login?rd=https://{host}{uri}"
```

- [ ] **Step 2: Write `docker-compose.traefik.yml`** (Known-Road: `compose` domain)

```yaml
services:
  traefik:
    image: ${TRAEFIK_IMAGE:-traefik:v3.3}
    container_name: pmoves-traefik
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.file.filename=/etc/traefik/dynamic.yml
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --certificatesresolvers.cf.acme.dnschallenge=true
      - --certificatesresolvers.cf.acme.dnschallenge.provider=cloudflare
      - --certificatesresolvers.cf.acme.email=${ACME_EMAIL:-ops@pmoves.ai}
      - --certificatesresolvers.cf.acme.storage=/letsencrypt/acme.json
    environment:
      CF_DNS_API_TOKEN: ${CLOUDFLARE_DNS_API_TOKEN}
    ports: ["443:443", "80:80"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./config/traefik/dynamic.yml:/etc/traefik/dynamic.yml:ro
      - traefik-acme:/letsencrypt
    networks: { pmoves_external: {} }
    labels:
      - traefik.enable=true
      - traefik.http.routers.auth.rule=Host(`auth.pmoves.ai`)
      - traefik.http.routers.auth.entrypoints=websecure
      - traefik.http.routers.auth.tls.certresolver=cf
      - traefik.http.routers.auth.service=sso-auth@docker
volumes: { traefik-acme: {} }
networks:
  pmoves_external: { external: true }
```

- [ ] **Step 3: Add Traefik router labels to each app** (in each app's compose block — Known-Road: `compose`). Example for wger-nginx (repeat pattern for firefly, open-notebook-ext, jellyfin-ext with their Host + service port; media.pmoves.ai → jellyfin has NO forward-auth middleware because its plugin handles auth):

```yaml
    labels:
      - traefik.enable=true
      - traefik.http.routers.health.rule=Host(`health.pmoves.ai`)
      - traefik.http.routers.health.entrypoints=websecure
      - traefik.http.routers.health.tls.certresolver=cf
      - traefik.http.routers.health.middlewares=pmoves-forward-auth@file,pmoves-auth-redirect@file
      - traefik.http.services.health.loadbalancer.server.port=80
```
Router→app map: `health`→wger-nginx:80, `wealth`→firefly:8080, `notebook`→open-notebook-ext:8502, `media`→jellyfin-ext:8096 (media router: NO forward-auth middleware). Remove each app's `ports:` host publish in the same edit.

- [ ] **Step 4: Verify routing + redirect**

Run: bring up traefik + sso-auth + wger; `curl -sI -H 'Host: health.pmoves.ai' https://<node>/ --resolve health.pmoves.ai:443:<node-ip> -k`
Expected: `302` to `auth.pmoves.ai/login` when no cookie; with a valid `pmoves_session` cookie, `200` and wger loads logged-in.

- [ ] **Step 5: Commit**

```bash
git add pmoves/docker-compose.traefik.yml pmoves/config/traefik/dynamic.yml
git commit -m "feat(traefik): edge + forward-auth middleware + subdomain routers"
```

---

### Task 6: Firefly integration — `remote_user_guard`

**Files:**
- Modify: `pmoves/docker-compose.external.yml` (firefly `environment:`) — Known-Road: `compose`
- Test: header-auth login (documented)

- [ ] **Step 1: Add the guard env to firefly**

```yaml
      AUTHENTICATION_GUARD: remote_user_guard
      AUTHENTICATION_GUARD_HEADER: Remote-User
      AUTHENTICATION_GUARD_EMAIL: X-Auth-Email
      DISABLE_FRAME_HEADER: "true"
```
(Also ensure firefly has no `ports:` host publish — it sits behind Traefik `wealth` router.)

- [ ] **Step 2: Verify**

Run: recreate firefly; request `wealth.pmoves.ai` with a valid session cookie.
Expected: Firefly auto-provisions + logs in the `X-Auth-Email` user (no Firefly login page). NOTE: requires the firefly tmpfs-500 fix (prerequisite PR) to be applied first, else firefly still 500s.

- [ ] **Step 3: Commit**

```bash
git add pmoves/docker-compose.external.yml
git commit -m "feat(firefly): remote_user_guard header auth via SSO gateway"
```

---

### Task 7: wger integration — `RemoteUserMiddleware`

**Files:**
- Modify: `pmoves/docker-compose.external.yml` (wger `environment:`) — Known-Road: `compose`
- (If the PMOVES wger fork does not honor a remote-user env) Modify: `PMOVES-Health-wger` settings to add `django.contrib.auth.middleware.RemoteUserMiddleware` after `AuthenticationMiddleware` and `RemoteUserBackend`.
- Test: header-auth login (documented)

- [ ] **Step 1: Add remote-user env to wger**

```yaml
      WGER_ALLOW_REMOTE_USER: "True"
      WGER_REMOTE_USER_HEADER: "Remote-User"
```

- [ ] **Step 2: If the fork lacks remote-user support, add it** (in the wger settings the fork controls):

```python
MIDDLEWARE.insert(MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware") + 1,
                  "django.contrib.auth.middleware.RemoteUserMiddleware")
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.RemoteUserBackend"] + AUTHENTICATION_BACKENDS
```

- [ ] **Step 3: Verify**

Run: recreate wger; request `health.pmoves.ai` with a valid cookie.
Expected: wger auto-creates + logs in the `Remote-User`; no wger login page.

- [ ] **Step 4: Commit**

```bash
git add pmoves/docker-compose.external.yml
git commit -m "feat(wger): RemoteUser header auth via SSO gateway"
```

---

### Task 8: Open-Notebook integration — fork middleware swap

**Files:**
- Modify: `PMOVES-Open-Notebook/api/auth.py` (add `RemoteUserMiddleware`, keep `PasswordAuthMiddleware` as non-proxied fallback)
- Test: `PMOVES-Open-Notebook/tests/test_remote_user_auth.py`

**Interfaces:**
- Produces: `RemoteUserMiddleware` that trusts `Remote-User` and sets `request.state.user`; falls back to the existing password check when the header is absent.

- [ ] **Step 1: Write the failing test**

```python
# PMOVES-Open-Notebook/tests/test_remote_user_auth.py
from starlette.requests import Request
from api.auth import RemoteUserMiddleware

def _scope(headers):
    return {"type":"http","headers":[(k.lower().encode(), v.encode()) for k,v in headers.items()], "method":"GET","path":"/"}

async def _call(headers):
    seen = {}
    async def app(scope, receive, send): seen["user"] = scope.get("state",{}).get("user")
    mw = RemoteUserMiddleware(app)
    sent = []
    async def send(m): sent.append(m)
    async def receive(): return {"type":"http.request"}
    await mw(_scope(headers), receive, send)
    return sent

def test_valid_remote_user_allows(anyio_backend="asyncio"):
    import anyio
    sent = anyio.run(_call, {"Remote-User":"a@b.co"})
    assert not any(m.get("status")==401 for m in sent if m.get("type")=="http.response.start")

def test_missing_remote_user_and_no_password_denies():
    import anyio
    sent = anyio.run(_call, {})
    # with no header and no valid password token -> 401
    assert any(m.get("status")==401 for m in sent if m.get("type")=="http.response.start")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd PMOVES-Open-Notebook && uv run --with pytest --with anyio --with starlette python -m pytest tests/test_remote_user_auth.py -q`
Expected: FAIL (`ImportError: RemoteUserMiddleware`).

- [ ] **Step 3: Add `RemoteUserMiddleware` to `api/auth.py`** (read the existing `PasswordAuthMiddleware` first to match its ASGI signature and the settings source it uses; then add):

```python
class RemoteUserMiddleware:
    """Trust the reverse-proxy Remote-User header (set only by Traefik forward-auth).
    Falls back to PasswordAuthMiddleware behavior when the header is absent so
    direct/non-proxied access still requires the token."""
    def __init__(self, app):
        self.app = app
        self._password_mw = PasswordAuthMiddleware(app)
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        user = headers.get("remote-user")
        if user:
            scope.setdefault("state", {})["user"] = user
            return await self.app(scope, receive, send)
        return await self._password_mw(scope, receive, send)
```
Then swap the app's middleware registration from `PasswordAuthMiddleware` to `RemoteUserMiddleware`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd PMOVES-Open-Notebook && uv run --with pytest --with anyio --with starlette python -m pytest tests/test_remote_user_auth.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** (in the submodule)

```bash
cd PMOVES-Open-Notebook && git add api/auth.py tests/test_remote_user_auth.py
git commit -m "feat(auth): trust Remote-User header from PMOVES SSO gateway (password fallback)"
```

---

### Task 9: Jellyfin integration — bake `Ezeqielle/jellyfin-plugin-oidc`

**Files:**
- Modify: `PMOVES-Jellyfin/dockerfile` (download + install the pinned plugin) — Known-Road: `dockerfile`
- Create: `PMOVES-Jellyfin/sso-plugin-config.xml` (OIDC provider config referencing the auth service)
- Test: OIDC login round-trip (documented)

- [ ] **Step 1: Add the plugin to the jellyfin fork Dockerfile** (pin the release tag; verify the current tag with `gh api repos/Ezeqielle/jellyfin-plugin-oidc/releases/latest --jq .tag_name` — as of 2026-07-24 it is `v1.0.8`):

```dockerfile
ARG JELLYFIN_OIDC_PLUGIN_VERSION=v1.0.8
RUN mkdir -p /config/plugins/OIDC \
 && curl -fsSL -o /tmp/oidc.zip \
    "https://github.com/Ezeqielle/jellyfin-plugin-oidc/releases/download/${JELLYFIN_OIDC_PLUGIN_VERSION}/jellyfin-plugin-oidc.zip" \
 && unzip /tmp/oidc.zip -d /config/plugins/OIDC && rm /tmp/oidc.zip
```
(Confirm the exact asset name from the release page during implementation; adjust the URL if the asset is named differently.)

- [ ] **Step 2: Provision the OIDC provider config** — the plugin reads provider config from Jellyfin's plugin config. Document the values (set via the Jellyfin admin UI on first run OR a config XML the image drops in): OID Endpoint `https://auth.pmoves.ai`, Client ID `${JELLYFIN_OIDC_CLIENT_ID}`, Client Secret `${JELLYFIN_OIDC_CLIENT_SECRET}`, redirect `https://media.pmoves.ai/sso/OID/redirect/pmoves`, `Enabled=true`, `EnableAuthorization=true`, auto-provision on.

- [ ] **Step 3: Verify**

Run: rebuild the jellyfin fork image; open `media.pmoves.ai` → "Sign in with PMOVES" → GoTrue login → back to Jellyfin logged in (user auto-provisioned).
Expected: OIDC round-trip succeeds; a Jellyfin user matching the Supabase email exists.

- [ ] **Step 4: Commit** (in the submodule + gitlink)

```bash
cd PMOVES-Jellyfin && git add dockerfile sso-plugin-config.xml
git commit -m "feat(jellyfin): bake pinned Ezeqielle OIDC plugin for PMOVES SSO"
```

---

### Task 10: Env pipeline additions (no new secrets)

**Files:**
- Modify: `pmoves/env.shared.example` (add config keys)
- Modify: `pmoves/chit/secrets_manifest_v2.yaml` (register the two Jellyfin OIDC client values + the Cloudflare DNS token if not present) — Known-Road: none (manifest is not a gated domain), but follow the env pipeline procedure.
- Test: `make -C pmoves compose ARGS="-f docker-compose.sso.yml -f docker-compose.traefik.yml config --quiet"` validates.

- [ ] **Step 1: Add to `env.shared.example`**

```
# --- SSO gateway ---
SSO_PUBLIC_BASE_URL=https://auth.pmoves.ai
SSO_COOKIE_DOMAIN=.pmoves.ai
GOTRUE_URL=http://supabase-gotrue:9999
JELLYFIN_OIDC_CLIENT_ID=
JELLYFIN_OIDC_CLIENT_SECRET=
CLOUDFLARE_DNS_API_TOKEN=
ACME_EMAIL=ops@pmoves.ai
```
(`SUPABASE_JWT_SECRET`/`JWT_SECRET` already exist — reuse, do NOT add.)

- [ ] **Step 2: Register the generated secrets in `secrets_manifest_v2.yaml`** (JELLYFIN_OIDC_CLIENT_ID/SECRET as generated 32-char tokens; CLOUDFLARE_DNS_API_TOKEN as a cgp/vault value the operator supplies). Follow the example→manifest→funnel procedure; then `make -C pmoves secrets-funnel`.

- [ ] **Step 3: Validate compose config**

Run: `make -C pmoves compose ARGS="-f docker-compose.sso.yml -f docker-compose.traefik.yml config --quiet"`
Expected: exit 0, no "required variable ... is missing".

- [ ] **Step 4: Commit**

```bash
git add pmoves/env.shared.example pmoves/chit/secrets_manifest_v2.yaml
git commit -m "feat(sso): env pipeline keys for the SSO gateway (reuse JWT_SECRET)"
```

---

### Task 11: End-to-end SSO verification

**Files:**
- Create: `pmoves/services/sso-auth/tests/test_e2e_flow.py` (session-sharing integration test against the running stack)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the e2e test** (runs against the live stack; skips if `SSO_E2E=1` not set)

```python
# pmoves/services/sso-auth/tests/test_e2e_flow.py
import os, pytest, httpx
pytestmark = pytest.mark.skipif(os.environ.get("SSO_E2E") != "1", reason="live stack only")

BASE = os.environ.get("SSO_E2E_BASE", "https://auth.pmoves.ai")
EMAIL = os.environ["SSO_E2E_EMAIL"]; PW = os.environ["SSO_E2E_PW"]

def test_one_login_reaches_all_apps():
    # TLS verification ON — the stack uses real Cloudflare DNS-01 certs (not self-signed).
    # If testing against a mesh-internal endpoint with a private CA, point httpx at it
    # via `verify=os.environ["SSO_E2E_CA_BUNDLE"]`, never verify=False.
    c = httpx.Client(verify=os.environ.get("SSO_E2E_CA_BUNDLE", True), follow_redirects=False)
    r = c.post(f"{BASE}/login", data={"email": EMAIL, "password": PW, "rd": "https://health.pmoves.ai"})
    assert r.status_code in (302, 303)
    cookie = c.cookies.get("pmoves_session"); assert cookie
    for host in ("health.pmoves.ai", "wealth.pmoves.ai", "notebook.pmoves.ai"):
        v = c.get(f"https://{host}/", cookies={"pmoves_session": cookie})
        assert v.status_code < 400, f"{host} not authed: {v.status_code}"
```

- [ ] **Step 2: Run it against the live stack**

Run: `SSO_E2E=1 SSO_E2E_EMAIL=... SSO_E2E_PW=... uv run --with pytest --with httpx python -m pytest pmoves/services/sso-auth/tests/test_e2e_flow.py -q`
Expected: PASS — one login cookie authenticates all three header-apps; Jellyfin verified manually via the OIDC round-trip (Task 9).

- [ ] **Step 3: Commit**

```bash
git add pmoves/services/sso-auth/tests/test_e2e_flow.py
git commit -m "test(sso): end-to-end one-login-all-apps verification"
```

---

## Notes for the implementer
- Read `PMOVES-BoTZ/features/mcp_bridge/auth.py` before Task 1 — match its `python-jose` HS256 verify exactly (that is the proven pattern being reused).
- Read `PMOVES-Open-Notebook/api/auth.py` before Task 8 — match the existing `PasswordAuthMiddleware` ASGI signature and settings source.
- Firefly, wger, jellyfin edits touch `compose`/`dockerfile` Known-Road domains — request the operator's grant for each at execution time (the grant is per-domain, ledger-recorded).
- The `_CODES` in-memory store in `oidc.py` assumes a single sso-auth replica (fine for Phase 1); note it as a scale caveat, not a bug.
