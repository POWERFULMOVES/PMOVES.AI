# pmoves/services/sso-auth/config.py
from typing import Annotated
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    supabase_jwt_secret: str          # env: SUPABASE_JWT_SECRET
    gotrue_url: str                   # env: GOTRUE_URL (internal http://supabase-gotrue:9999)
    # Browser-facing GoTrue origin. SEPARATE from gotrue_url on purpose: gotrue_url
    # is used for server-to-server POSTs from inside the Docker network, so it is a
    # compose service name that no browser can resolve. provider_authorize_url()
    # hands its result to the USER'S BROWSER as a redirect — using gotrue_url there
    # renders a dead "Sign in with GitHub" link pointing at
    # http://supabase-gotrue:9999/authorize, which is what shipped until 2026-08-06.
    # Defaults to gotrue_url so single-host / dev deployments (where GoTrue is
    # already on a reachable address) keep working unchanged.
    gotrue_public_url: str = ""       # env: GOTRUE_PUBLIC_URL (https://auth.pmoves.ai/gotrue)
    public_base_url: str              # env: PUBLIC_BASE_URL (https://auth.pmoves.ai)
    cookie_domain: str = ".pmoves.ai" # env: SSO_COOKIE_DOMAIN
    cookie_name: str = "pmoves_session"
    session_ttl_seconds: int = 3600
    jellyfin_oidc_client_id: str      # env: JELLYFIN_OIDC_CLIENT_ID
    jellyfin_oidc_client_secret: str  # env: JELLYFIN_OIDC_CLIENT_SECRET
    # NoDecode: this is a plain list[str], but pydantic-settings' EnvSettingsSource
    # treats list-typed fields as "complex" and unconditionally tries json.loads()
    # on the raw env value BEFORE init-kwarg precedence is applied — our comma-
    # separated JELLYFIN_OIDC_REDIRECT_URIS isn't JSON, so without NoDecode this
    # throws SettingsError even though load() always supplies the parsed list
    # explicitly below. NoDecode skips that eager decode; load()'s explicit kwarg
    # (parsed via .split(",")) always wins in the init > env source-merge order.
    jellyfin_oidc_redirect_uris: Annotated[list[str], NoDecode] = []  # env: JELLYFIN_OIDC_REDIRECT_URIS
    # RSA private-key PEM for signing OIDC id_tokens (RS256). Resolution order
    # (see oidc._load_or_generate_private_key): this explicit env override FIRST,
    # else the persisted key file at oidc_signing_key_path, else generate-once and
    # persist there. Large PEMs don't belong in the url-safe CHIT/env pipeline, so
    # the default is self-provisioning; mount a shared key file for multi-node.
    oidc_signing_key: str = ""       # env: OIDC_SIGNING_KEY (optional explicit override)
    oidc_signing_key_path: str = "/data/oidc_signing_key.pem"  # env: OIDC_SIGNING_KEY_PATH
    # Proof-of-proxy shared secret. /auth/verify emits it as X-Forward-Auth-Secret
    # on 200 (Traefik forwards it via authResponseHeaders, overwriting any client
    # value); apps verify it before honoring Remote-User, so a peer that reaches an
    # app OFF-proxy cannot forge the header. Empty => not emitted.
    forward_auth_secret: str = ""  # env: SSO_FORWARD_AUTH_SECRET
    # Whether GoTrue has the Google external provider wired. Purely a UI gate for
    # the login page's "Sign in with Google" button — the actual OAuth handshake
    # lives entirely in GoTrue (SUPABASE_AUTH_EXTERNAL_GOOGLE_*). Showing the
    # button when the provider is disabled would just bounce the user off a
    # GoTrue error, so we hide it until the operator enables the provider.
    google_enabled: bool = False   # env: SSO_GOOGLE_ENABLED (truthy = show button)

    @classmethod
    def load(cls) -> "Settings":
        import os
        g = os.environ.get
        # Only SUPABASE_JWT_SECRET is required — it is all the /auth/verify hot
        # path needs. The login/OIDC fields default to "" so a deployment that
        # hasn't provisioned the Jellyfin OIDC vars still serves forward-auth
        # (those paths fail at request time if actually used, not at verify).
        redirect_uris = [u.strip() for u in g("JELLYFIN_OIDC_REDIRECT_URIS", "").split(",") if u.strip()]
        return cls(
            supabase_jwt_secret=os.environ["SUPABASE_JWT_SECRET"],
            gotrue_url=g("GOTRUE_URL", ""),
            # Fall back to the internal URL so nothing that works today breaks.
            gotrue_public_url=g("GOTRUE_PUBLIC_URL", "") or g("GOTRUE_URL", ""),
            public_base_url=g("PUBLIC_BASE_URL", ""),
            cookie_domain=g("SSO_COOKIE_DOMAIN", ".pmoves.ai"),
            jellyfin_oidc_client_id=g("JELLYFIN_OIDC_CLIENT_ID", ""),
            jellyfin_oidc_client_secret=g("JELLYFIN_OIDC_CLIENT_SECRET", ""),
            jellyfin_oidc_redirect_uris=redirect_uris,
            oidc_signing_key=g("OIDC_SIGNING_KEY", "").replace("\\n", "\n"),
            oidc_signing_key_path=g("OIDC_SIGNING_KEY_PATH", "/data/oidc_signing_key.pem"),
            forward_auth_secret=g("SSO_FORWARD_AUTH_SECRET", ""),
            google_enabled=g("SSO_GOOGLE_ENABLED", "").strip().lower()
            in ("1", "true", "yes", "on"),
        )


class _LazySettings:
    """Lazy settings proxy — reads env on FIRST attribute access, NOT at import.
    So the service starts under compose env, AND tests set env then call
    `settings._reset()` to force a fresh read. Never read required env at import
    time (that crashes pytest collection when env is unset). All modules import
    this `settings` object and use `settings.<field>` uniformly."""
    _cached = None  # type: Settings | None
    def __getattr__(self, name):
        if _LazySettings._cached is None:
            _LazySettings._cached = Settings.load()
        return getattr(_LazySettings._cached, name)
    def _reset(self):
        _LazySettings._cached = None

settings = _LazySettings()
