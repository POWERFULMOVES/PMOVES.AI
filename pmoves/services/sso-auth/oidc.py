# pmoves/services/sso-auth/oidc.py
import hmac
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode
from jose import jwt
from jose import jwk as jose_jwk
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import JSONResponse, RedirectResponse
from config import settings
from jwt_verify import verify_session, SessionInvalid

router = APIRouter()
# code -> (session_jwt, expiry, redirect_uri). In-memory: single replica; fine for Phase 1.
_CODES: dict[str, tuple[str, float, str]] = {}
_CODE_TTL = 120

_KID = "pmoves-sso-1"
_key_cache: dict[str, tuple[str, str, dict]] = {}   # priv_pem -> (priv_pem, pub_pem, public_jwk)

class OIDCNotConfigured(Exception): ...

def _load_or_generate_private_key() -> str:
    """Resolve the RSA signing-key PEM. Precedence:
      1. explicit OIDC_SIGNING_KEY env override (settings.oidc_signing_key), else
      2. the persisted key file at settings.oidc_signing_key_path, else
      3. generate an RSA-2048 key and persist it there (0600) for restart / JWKS
         stability — mount a shared key file for multi-node consistency.
    A large PEM doesn't belong in the url-safe CHIT/env secrets pipeline, so the
    default is self-provisioning. Raises OIDCNotConfigured if no key can be
    obtained (e.g. an unwritable path) so the OIDC endpoints 503 instead of 500."""
    if settings.oidc_signing_key:
        return settings.oidc_signing_key
    path = Path(settings.oidc_signing_key_path)
    try:
        if path.is_file():
            return path.read_text()
        pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pem)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # best-effort perms (non-POSIX / already-restricted)
        return pem
    except OSError as ex:
        raise OIDCNotConfigured() from ex

def _keys():
    """(priv_pem, pub_pem, public_jwk) for the RSA signing key. Cached by the key
    material, so config.settings._reset() in tests re-derives. Raises
    OIDCNotConfigured only when a key can't be obtained (OIDC endpoints then 503)."""
    priv = _load_or_generate_private_key()
    if priv not in _key_cache:
        pk = serialization.load_pem_private_key(priv.encode(), password=None)
        pub_pem = pk.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        d = jose_jwk.construct(pub_pem, "RS256").to_dict()
        d = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in d.items()}
        d.update({"kid": _KID, "use": "sig", "alg": "RS256"})
        _key_cache[priv] = (priv, pub_pem, d)
    return _key_cache[priv]

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
            "subject_types_supported": ["public"], "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email"]}

@router.get("/oidc/jwks")
def jwks():
    try:
        _, _, public_jwk = _keys()
    except OIDCNotConfigured:
        return JSONResponse({"keys": []}, status_code=503)
    return {"keys": [public_jwk]}

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
        # urlencode the whole authorize URL — it contains &/= (redirect_uri, state),
        # and an unencoded rd would be truncated at the first & on the login page,
        # dropping the required redirect_uri and 422-ing the post-login bounce-back.
        return RedirectResponse("/login?" + urlencode({"rd": str(request.url)}), status_code=303)
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
    try:
        priv, _, _ = _keys()
    except OIDCNotConfigured:
        return JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
    now = int(time.time())
    id_token = jwt.encode({"iss": settings.public_base_url, "aud": client_id,
        "sub": claims["sub"], "email": claims.get("email", ""),
        "preferred_username": claims.get("email", claims["sub"]), "iat": now, "exp": now + 300},
        priv, algorithm="RS256", headers={"kid": _KID})
    return {"access_token": id_token, "id_token": id_token, "token_type": "Bearer", "expires_in": 300}

@router.get("/oidc/userinfo")
def userinfo(request: Request):
    auth = request.headers.get("authorization", "")
    tok = auth[7:] if auth.lower().startswith("bearer ") else ""
    try:
        _, pub_pem, _ = _keys()
        c = jwt.decode(tok, pub_pem, algorithms=["RS256"], options={"verify_aud": False})
    except Exception:
        return Response(status_code=401)
    return {"sub": c["sub"], "email": c.get("email", ""), "preferred_username": c.get("preferred_username", c.get("email", c["sub"]))}
