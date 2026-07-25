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
