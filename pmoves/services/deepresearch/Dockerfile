FROM python:3.10-slim
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
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip install --no-cache-dir -r /opt/DeepResearch/requirements.txt
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
