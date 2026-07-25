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
        # HS256 with the shared Supabase secret. audience 'authenticated' is
        # GoTrue's default; options relax aud check to tolerate anon/service too.
        return jwt.decode(
            token, secret, algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise SessionInvalid(str(e)) from e
