# pmoves/services/sso-auth/Dockerfile
# Pinned base matches the PMOVES fleet convention (python:3.11-slim@sha256:a3ab0b9…,
# the digest used across pmoves/services/*/Dockerfile). sso-auth needs no
# 3.12-only features, so it stays on the fleet's vetted, pinned digest rather
# than an unpinned python:3.12-slim.
FROM python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0

LABEL maintainer="PMOVES.AI <hello@powerfulmoves.com>"
LABEL description="PMOVES SSO forward-auth gateway (Supabase GoTrue session verify + login)"

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Requirements first for layer caching.
COPY services/sso-auth/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code.
COPY services/sso-auth/ .

# Non-root runtime (PMOVES hardening — matches the fleet's uid 1001 pattern).
RUN useradd -m -u 1001 pmoves && chown -R pmoves:pmoves /app
USER pmoves

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
