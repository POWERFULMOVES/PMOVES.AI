# pmoves/services/sso-auth/oidc.py
import hmac, secrets, time
from jose import jwt
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import JSONResponse, RedirectResponse
from config import settings
from jwt_verify import verify_session, SessionInvalid

router = APIRouter()
# code -> (session_jwt, expiry, redirect_uri). In-memory: single replica; fine for Phase 1.
_CODES: dict[str, tuple[str, float, str]] = {}
_CODE_TTL = 120

def _issue_code(session_jwt: str, redirect_uri: str) -> str:
    # Bind the code to the exact redirect_uri it was issued for; /oidc/token
    # re-checks it, so a code minted for the registered URI can't be replayed
    # against a different one.
    c = secrets.token_urlsafe(24); _CODES[c] = (session_jwt, time.time() + _CODE_TTL, redirect_uri); return c

def _client_ok(client_id: str, client_secret: str) -> bool:
    # Constant-time comparison — the client_secret is a confidential shared secret.
    return (hmac.compare_digest(client_id, settings.jellyfin_oidc_client_id)
            and hmac.compare_digest(client_secret, settings.jellyfin_oidc_client_secret))

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
    # Validate the client + redirect_uri BEFORE any session logic or code issuance.
    # An unregistered redirect_uri is an open-redirect + auth-code-leak vector, so
    # we 400 (never redirect) rather than reflect an attacker-supplied location.
    if client_id != settings.jellyfin_oidc_client_id or redirect_uri not in settings.jellyfin_oidc_redirect_uris:
        return JSONResponse({"error": "invalid_request", "detail": "unregistered client_id or redirect_uri"}, status_code=400)
    token = request.cookies.get(settings.cookie_name, "")
    try:
        verify_session(token)
    except SessionInvalid:
        return RedirectResponse(f"/login?rd={request.url}", status_code=303)
    code = _issue_code(token, redirect_uri)
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}", status_code=303)

@router.post("/oidc/token")
def token(grant_type: str = Form(...), code: str = Form(...), client_id: str = Form(...),
          client_secret: str = Form(...), redirect_uri: str = Form("")):
    if not _client_ok(client_id, client_secret):
        return Response(status_code=401)
    entry = _CODES.pop(code, None)
    # Reject missing/expired codes, AND codes whose bound redirect_uri doesn't
    # match the one presented here (RFC 6749 §4.1.3 redirect_uri consistency).
    if not entry or entry[1] < time.time() or entry[2] != redirect_uri:
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
