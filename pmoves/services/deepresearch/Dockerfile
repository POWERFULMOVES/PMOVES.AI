FROM python:3.10-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/Alibaba-NLP/DeepResearch.git /opt/DeepResearch \
    && cd /opt/DeepResearch \
    && git checkout 3f2845ffea03f198a84716a580e2cbb4145b0465
COPY services/deepresearch/requirements.txt /tmp/deepresearch-requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/deepresearch-requirements.txt \
    && pip install --no-cache-dir -r /opt/DeepResearch/requirements.txt
COPY services /app/services
COPY contracts /app/contracts
ENV PYTHONPATH=/app
CMD ["python", "-m", "services.deepresearch.worker"]
