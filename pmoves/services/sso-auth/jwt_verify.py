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
