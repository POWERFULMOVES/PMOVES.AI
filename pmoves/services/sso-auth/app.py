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
    """Traefik ForwardAuth target. On a valid session: 200 + identity headers.
    On no/invalid session: a 302 to /login for BROWSER navigations (so the user
    lands on the login page, not a dead 401), else a bare 401 for API clients.

    Why redirect from HERE rather than a Traefik `errors` middleware: an `errors`
    middleware body-swaps while KEEPING the original 401 status (it is not a
    redirect), and its `query` substitutes only `{status}` — it cannot carry the
    original URL, so the user can't be returned to where they were headed. Traefik
    passes a forwardAuth server's non-2xx response to the client unchanged, so a
    302 emitted here becomes a real browser redirect that CAN carry `rd`.
    See _unauthenticated_response for the browser-vs-API split."""
    token = request.cookies.get(settings.cookie_name, "")
    try:
        claims = verify_session(token)
    except SessionInvalid:
        return _unauthenticated_response(request)
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

def _unauthenticated_response(request: Request) -> Response:
    """No valid session on /auth/verify: redirect a browser to /login (keeping
    where it was headed), else a bare 401 for API/programmatic callers.

    Browser split: ONLY a request that Accepts text/html gets the 302 — an
    XHR/fetch/API caller Accepts application/json or */* and must receive a clean
    401 (a 302 to an HTML login page would corrupt an API response and mask the
    real auth failure). This is why the old `errors`-middleware approach was
    wrong for BOTH audiences: it returned login HTML with a 401 to everyone.

    Return destination: rebuilt from the X-Forwarded-* headers Traefik injects
    onto the forward-auth sub-request (the ORIGINAL app URL the user asked for,
    e.g. https://notebook.pmoves.ai/foo), then passed through _safe_rd so a
    spoofed X-Forwarded-Host can't turn login into an open redirect (it collapses
    anything outside *.pmoves.ai to '/'). The Location host is always our own
    public_base_url (trusted config), never the forwarded host. Falls back to a
    bare 401 if we can't form a valid login URL (no public_base_url configured)."""
    accept = request.headers.get("accept", "").lower()
    base = settings.public_base_url
    if "text/html" not in accept or not base:
        return Response(status_code=401)
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("x-forwarded-host", "")
    uri = request.headers.get("x-forwarded-uri", "/")
    rd = _safe_rd(f"{proto}://{host}{uri}") if host else "/"
    return RedirectResponse(f"{base}/login?" + urlencode({"rd": rd}), status_code=302)

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
