"""Authentication middleware for Cast TTS Gateway.

This module provides JWT-based authentication using Supabase tokens,
with optional development mode bypass for local testing.
"""

import logging
import os
from typing import Callable, Awaitable

from aiohttp import web
import jose.jwt

logger = logging.getLogger(__name__)


async def get_user_context(request: web.Request) -> dict:
    """
    Extract user context from Supabase JWT.

    This function validates the JWT token from the Authorization header
    and extracts user information (user_id, role, email).

    Args:
        request: aiohttp web request

    Returns:
        User context dict with keys:
            - user_id: User's unique identifier
            - role: User's role (e.g., 'authenticated', 'admin')
            - email: User's email address

    Raises:
        web.HTTPUnauthorized: If JWT is invalid, missing, or expired
    """
    auth_header = request.headers.get("Authorization", "")

    # Allow unauthenticated requests in development mode
    if os.getenv("CAST_AUTH_REQUIRED", "true") == "false":
        logger.warning("SECURITY: CAST_AUTH_REQUIRED=false — authentication bypassed (dev mode)")
        return {
            "user_id": "dev_user",
            "role": "dev",
            "email": "dev@pmoves.ai"
        }

    if not auth_header.startswith("Bearer "):
        raise web.HTTPUnauthorized(
            reason="Missing or invalid authorization header. Expected format: 'Bearer <token>'"
        )

    token = auth_header[7:]  # Remove 'Bearer ' prefix
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

    if not jwt_secret:
        raise web.HTTPInternalServerError(
            reason="Server misconfiguration: SUPABASE_JWT_SECRET is not set"
        )

    try:
        # Validate JWT signature and extract payload
        payload = jose.jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False}  # Skip audience verification for flexibility
        )

        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role", "authenticated"),
            "email": payload.get("email")
        }
    except jose.JWTError:
        raise web.HTTPUnauthorized(
            reason="Invalid or expired JWT token"
        )
    except Exception:
        raise web.HTTPUnauthorized(
            reason="Authentication failed"
        )


@web.middleware
async def auth_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.Response]]
) -> web.Response:
    """
    Authentication middleware for aiohttp routes.

    This middleware intercepts all incoming requests and validates JWT tokens
    for protected endpoints. Public endpoints bypass authentication.

    Public endpoints (no auth required):
        - /healthz - Health check endpoint
        - /metrics - Prometheus metrics endpoint
        - /cast/discover - Device discovery endpoint

    All other endpoints require valid JWT authentication.

    Args:
        request: Incoming aiohttp web request
        handler: The request handler to call if auth succeeds

    Returns:
        The response from the request handler

    Raises:
        web.HTTPUnauthorized: If authentication fails for protected endpoints
    """
    # Define public paths that don't require authentication
    public_paths = ["/healthz", "/metrics", "/cast/discover"]

    # Check if the request path is public
    if request.path in public_paths:
        return await handler(request)

    # Extract and validate user context from JWT
    request["user"] = await get_user_context(request)

    # Call the original handler with authenticated context
    return await handler(request)


def require_role(*roles: str) -> Callable:
    """
    Decorator factory to require specific user roles for endpoints.

    Usage:
        @require_role('admin', 'moderator')
        async def admin_endpoint(request):
            ...

    Args:
        *roles: Allowed role names (e.g., 'admin', 'authenticated')

    Returns:
        Decorator function that checks user role

    Raises:
        web.HTTPForbidden: If user lacks required role
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(request: web.Request) -> web.Response:
            user = request.get("user", {})

            # Skip role check in development mode
            if os.getenv("CAST_AUTH_REQUIRED", "true") == "false":
                return await func(request)

            user_role = user.get("role", "anonymous")

            if user_role not in roles:
                raise web.HTTPForbidden(
                    reason=f"Insufficient permissions. Required role: one of {roles}, got: {user_role}"
                )

            return await func(request)

        return wrapper
    return decorator
