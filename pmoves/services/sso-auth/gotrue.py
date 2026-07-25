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
