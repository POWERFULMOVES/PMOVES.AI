FROM python:3.12-slim

WORKDIR /app

# Install Python deps. PyYAML + jsonschema for the schema validator;
# fastapi + uvicorn for the HTTP surface; httpx is optional (the
# service doesn't make outbound calls in noop writer mode).
COPY pmoves/services/mesh_exposure/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the service module + the schema it validates against + the
# registry entries it plans against.
COPY pmoves/services/mesh_exposure /app/mesh_exposure
COPY pmoves/configs/pinokio-apps /app/configs/pinokio-apps
COPY pmoves/config/headscale /app/config/headscale
COPY pmoves/config/mcp /app/config/mcp

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    MESH_EXPOSURE_PORT=8132 \
    MESH_EXPOSURE_HOST=0.0.0.0 \
    MESH_EXPOSURE_REGISTRY_DIR=/app/configs/pinokio-apps/curated \
    MESH_EXPOSURE_HEADSCALE_ACL=/app/config/headscale/acl.yaml \
    MESH_EXPOSURE_WRITER_MODE=noop

EXPOSE 8132

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8132/healthz').status == 200 else 1)"

CMD ["uvicorn", "mesh_exposure.app:app", "--host", "0.0.0.0", "--port", "8132"]
