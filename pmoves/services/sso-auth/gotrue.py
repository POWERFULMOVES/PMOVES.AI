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

def provider_authorize_url(provider: str, redirect_to: str) -> str:
    # GoTrue external-provider handshake entrypoint. `provider` is one of
    # GoTrue's configured externals ("github", "google", ...); the browser is
    # sent here, GoTrue bounces to the provider, then back to `redirect_to`
    # (our /callback) with the auth code. Same shape for every provider.
    #
    # gotrue_PUBLIC_url, not gotrue_url. This string is rendered into the login
    # page as an href and followed by the USER'S BROWSER — unlike every other
    # call in this module, which is a server-side POST from inside the Docker
    # network. Using gotrue_url here produced a dead link to
    # `http://supabase-gotrue:9999/authorize`, which no browser can resolve;
    # the login page loaded fine, so nothing looked broken until someone
    # clicked. gotrue_public_url falls back to gotrue_url when unset, so
    # deployments where GoTrue is already browser-reachable are unaffected.
    q = urlencode({"provider": provider, "redirect_to": redirect_to})
    return f"{settings.gotrue_public_url}/authorize?{q}"

def exchange_code(code: str) -> dict:
    # GoTrue PKCE/code exchange: POST /token?grant_type=pkce (auth code flow).
    return _post("/token?grant_type=pkce", json={"auth_code": code}).json()

def logout(access_token: str) -> None:
    # Server-side revoke of the GoTrue session (POST /logout with the bearer).
    _post("/logout", ok=(200, 204),
          headers={"Authorization": f"Bearer {access_token}"})
