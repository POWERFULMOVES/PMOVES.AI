# pmoves/services/sso-auth/app.py
from fastapi import FastAPI, Request, Response
from config import settings
from jwt_verify import verify_session, SessionInvalid

app = FastAPI(title="pmoves-sso-auth")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/auth/verify")
def auth_verify(request: Request):
    """Traefik ForwardAuth target. 200 + identity headers, or 401."""
    token = request.cookies.get(settings.cookie_name, "")
    try:
        claims = verify_session(token)
    except SessionInvalid:
        return Response(status_code=401)
    ident = claims.get("email") or claims.get("sub") or ""
    return Response(
        status_code=200,
        headers={
            "Remote-User": ident,
            "X-Auth-Email": claims.get("email", ""),
            "X-Auth-Subject": claims.get("sub", ""),
        },
    )
