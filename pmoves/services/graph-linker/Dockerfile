# -- Stage 1: Build dependencies -----------------------------------------
# Build context: repo root (pmoves/)
# Usage: docker build -f services/graph-linker/Dockerfile -t pmoves-graph-linker:latest .
FROM python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 AS builder

WORKDIR /build
COPY services/graph-linker/requirements.txt services/graph-linker/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock \
    --prefix=/install -r requirements.txt

# -- Stage 2: Runtime ----------------------------------------------------
FROM python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY services/graph-linker/. .

# PMOVES namespace + shared tools (imported as pmoves.tools.*)
RUN mkdir -p /app/pmoves \
    && printf '"""Minimal pmoves namespace for Docker."""\n' > /app/pmoves/__init__.py
COPY tools/__init__.py /app/pmoves/tools/__init__.py
COPY tools/chit_security.py /app/pmoves/tools/chit_security.py

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')"] || exit 1

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
