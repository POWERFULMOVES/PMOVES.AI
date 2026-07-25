# pmoves/services/sso-auth/gotrue.py
import httpx
from urllib.parse import urlencode
from config import settings

class GoTrueError(Exception): ...

def _post(path: str, *, ok=(200,), **kwargs) -> httpx.Response:
    # Single POST helper: a GoTrue OUTAGE (connect/timeout/transport error) must
    # surface as GoTrueError, not a raw httpx exception — otherwise the callers'
    # `except GoTrueError` blocks miss it and the endpoint 500s, violating the
    # spec's fail-closed / never-500 invariant. So we wrap httpx.RequestError too.
    try:
        r = httpx.post(f"{settings.gotrue_url}{path}", timeout=10.0, **kwargs)
    except httpx.RequestError as ex:
        raise GoTrueError(f"gotrue unreachable: {ex!r}") from ex
    if r.status_code not in ok:
        raise GoTrueError(f"gotrue {path} {r.status_code}")
    return r

def password_grant(email: str, password: str) -> dict:
    return _post("/token?grant_type=password",
                 json={"email": email, "password": password}).json()

def github_authorize_url(redirect_to: str) -> str:
    q = urlencode({"provider": "github", "redirect_to": redirect_to})
    return f"{settings.gotrue_url}/authorize?{q}"

def exchange_code(code: str) -> dict:
    # GoTrue PKCE/code exchange: POST /token?grant_type=pkce (auth code flow).
    return _post("/token?grant_type=pkce", json={"auth_code": code}).json()

def logout(access_token: str) -> None:
    # Server-side revoke of the GoTrue session (POST /logout with the bearer).
    _post("/logout", ok=(200, 204),
          headers={"Authorization": f"Bearer {access_token}"})
