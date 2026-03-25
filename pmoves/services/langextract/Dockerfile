FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/libs
RUN pip install --no-cache-dir --upgrade pip
# With build context at repo root
COPY libs /app/libs
COPY services/langextract/requirements.txt services/langextract/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt
COPY services/langextract/ ./

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8084
CMD ["uvicorn","api:app","--host","0.0.0.0","--port","8084"]
