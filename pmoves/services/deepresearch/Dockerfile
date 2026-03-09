# Base image pinned 2026-03-05 — refresh monthly or via Dependabot
FROM python:3.10-slim@sha256:4b0a8ebf16cf4563f3d3732bd4f4a464abb2f671b3b9d00aab281d705d224457
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/Alibaba-NLP/DeepResearch.git /opt/DeepResearch \
    && cd /opt/DeepResearch \
    && git checkout 3f2845ffea03f198a84716a580e2cbb4145b0465
COPY services/deepresearch/requirements.txt /tmp/requirements.txt
COPY services/deepresearch/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --upgrade pip \
    "setuptools==82.0.0" "wheel==0.46.3" \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir -r /opt/DeepResearch/requirements.txt \
    && pip install --no-cache-dir \
       "ray>=2.52.0" \
       "vllm>=0.14.1" \
    # ^^^ CVE overrides: Ray RCE (CVE-2025-62593), vLLM RCE (CVE-2026-22778)
COPY services/deepresearch /app/services/deepresearch
COPY services/common /app/services/common
COPY services/__init__.py /app/services/__init__.py
COPY contracts /app/contracts
ENV PYTHONPATH=/app
ENV PMOVES_CONTRACTS_DIR=/app/contracts

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app && \
    chown -R pmoves:pmoves /opt/DeepResearch

USER pmoves:pmoves
CMD ["python", "-m", "services.deepresearch.worker"]
