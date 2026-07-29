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
    headers = {
        "Remote-User": ident,
        "X-Auth-Email": claims.get("email", ""),
        "X-Auth-Subject": claims.get("sub", ""),
    }
    # Proof-of-proxy: emit the shared secret so apps can confirm the request
    # actually transited Traefik (Traefik forwards this via authResponseHeaders,
    # overwriting any client-supplied value). A peer reaching an app off-proxy
    # cannot produce it. Only emitted when configured.
    if settings.forward_auth_secret:
        headers["X-Forward-Auth-Secret"] = settings.forward_auth_secret
    return Response(status_code=200, headers=headers)

# append to pmoves/services/sso-auth/app.py
from fastapi import Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from urllib.parse import urlparse, urlencode
import gotrue

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

def _safe_rd(rd: str) -> str:
    """Open-redirect guard: `rd` reaches us from a query/form param, so an
    attacker could pass rd=https://evil.com and phish a logged-in user. Allow
    ONLY a same-origin relative path, or an http(s) URL whose host is within the
    PMOVES cookie domain (*.pmoves.ai). Anything else falls back to '/'.

    Hardened against browser quirks: leading whitespace/control chars are
    stripped by browsers parsing Location, and '/\\', '//', backslashes, or
    embedded CR/LF/TAB can be read as authority-relative or inject headers."""
    rd = rd.strip()
    if not rd or any(c in rd for c in "\r\n\t") or "\\" in rd:
        return "/"
    p = urlparse(rd)
    # Relative same-origin path: require empty scheme AND netloc, and a single
    # leading slash (reject '//' protocol-relative).
    if not p.scheme and not p.netloc and rd.startswith("/") and not rd.startswith("//"):
        return rd
    dom = settings.cookie_domain.lstrip(".").lower()   # e.g. 'pmoves.ai'
    host = (p.hostname or "").lower().rstrip(".")
    if p.scheme in ("http", "https") and host and (host == dom or host.endswith("." + dom)):
        return rd
    return "/"

def _set_session(resp, access_token: str):
    resp.set_cookie(settings.cookie_name, access_token, domain=settings.cookie_domain,
                    httponly=True, secure=True, samesite="lax", max_age=settings.session_ttl_seconds)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, rd: str = "/", e: str = ""):
    rd = _safe_rd(rd)
    cb = f"{settings.public_base_url}/callback?" + urlencode({"rd": rd})  # rd may contain &/# — encode it
    error = "Sign-in failed — check your email and password." if e else None
    return _templates.TemplateResponse("login.html", {"request": request, "rd": rd,
        "github_url": gotrue.provider_authorize_url("github", cb),
        "google_url": gotrue.provider_authorize_url("google", cb),
        "google_enabled": settings.google_enabled, "error": error})

@app.post("/login")
def login_submit(email: str = Form(...), password: str = Form(...), rd: str = Form("/")):
    rd = _safe_rd(rd)
    try:
        tok = gotrue.password_grant(email, password)
    except gotrue.GoTrueError:
        return RedirectResponse("/login?" + urlencode({"rd": rd, "e": "1"}), status_code=303)
    resp = RedirectResponse(rd, status_code=303); _set_session(resp, tok["access_token"]); return resp

@app.get("/callback")
def callback(code: str = "", rd: str = "/"):
    rd = _safe_rd(rd)
    try:
        tok = gotrue.exchange_code(code)  # a stale/replayed OAuth code is routine — don't 500
    except gotrue.GoTrueError:
        return RedirectResponse("/login?" + urlencode({"rd": rd, "e": "1"}), status_code=303)
    resp = RedirectResponse(rd, status_code=303); _set_session(resp, tok["access_token"]); return resp

@app.get("/logout")
def logout(request: Request):
    # Best-effort SERVER-SIDE GoTrue revoke (so a captured token is invalidated,
    # not just the cookie), then clear the local cookie and send the browser to
    # the browser-reachable local /login. Do NOT redirect to gotrue_url — it is
    # an INTERNAL address the browser cannot resolve.
    token = request.cookies.get(settings.cookie_name, "")
    if token:
        try:
            gotrue.logout(token)
        except gotrue.GoTrueError:
            pass  # best effort — still clear the local session
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(settings.cookie_name, domain=settings.cookie_domain, secure=True, httponly=True)
    return resp

# append to pmoves/services/sso-auth/app.py
import oidc
app.include_router(oidc.router)
