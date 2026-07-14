FROM python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0

# Build context is pmoves/ (see docker-compose.yml) so the canonical CHIT
# verifier chain can be packaged: bridge.py imports
# services.common.geometry_decoder, which imports pmoves.tools.chit_security
# and pmoves.services.common.geometry_models (review #2082 P2 — without these
# the import fails and the signature gate degrades to passthrough).

WORKDIR /app

# Install dependencies
COPY services/a2ui-nats-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared common module (services.common.geometry_decoder)
COPY services/common/ services/common/

# pmoves package namespace for the canonical CHIT modules
COPY __init__.py pmoves/__init__.py
COPY tools/__init__.py pmoves/tools/__init__.py
COPY tools/chit_common.py tools/chit_security.py pmoves/tools/
COPY services/__init__.py pmoves/services/__init__.py
COPY services/common/ pmoves/services/common/

# Copy application
COPY services/a2ui-nats-bridge/bridge.py .

# Create non-root user
RUN useradd -m -u 1001 pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves

EXPOSE 9224

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9224/healthz')"

CMD ["python", "bridge.py"]
