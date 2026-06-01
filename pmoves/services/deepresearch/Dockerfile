# PMOVES DeepResearch worker — lightweight NATS bridge to OpenRouter/TensorZero
# Note: this service does NOT use the Alibaba-NLP DeepResearch library; it is a
# standalone worker that calls external research APIs via HTTP.
FROM python:3.10-slim@sha256:4b0a8ebf16cf4563f3d3732bd4f4a464abb2f671b3b9d00aab281d705d224457
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY services/deepresearch/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --upgrade pip \
    "setuptools==82.0.0" "wheel==0.46.3" \
    && pip install --no-cache-dir -r /tmp/requirements.lock \
    && pip install --no-cache-dir "prometheus-client==0.21.0" "jsonschema==4.25.1"
COPY services/deepresearch /app/services/deepresearch
COPY services/common /app/services/common
COPY services/__init__.py /app/services/__init__.py
COPY contracts /app/contracts
# pmoves.chit: CGP_SPEC_VERSION constant needed by worker.py CHIT integration.
# Only copy Python files — secrets manifests (YAML) must stay out of image layers.
# Use minimal __init__.py (the repo's full version auto-imports pmoves.services which isn't in this image).
RUN mkdir -p /app/pmoves && echo '"""pmoves namespace (container-minimal)."""' > /app/pmoves/__init__.py
COPY chit/__init__.py /app/pmoves/chit/__init__.py
COPY chit/codec.py /app/pmoves/chit/codec.py
ENV PYTHONPATH=/app
ENV PMOVES_CONTRACTS_DIR=/app/contracts

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

# Health check (process-based for non-HTTP worker)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD test -f /proc/1/cmdline || exit 1
CMD ["python", "-m", "services.deepresearch.worker"]
