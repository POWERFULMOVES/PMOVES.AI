FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY services/comfy-watcher/requirements.txt services/comfy-watcher/requirements.lock ./
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

# Minimal app payload (common event helper + contracts + watcher)
RUN mkdir -p /app/services
COPY services/__init__.py /app/services/__init__.py
COPY services/common /app/services/common
COPY contracts /app/contracts
COPY services/comfy-watcher/README.md /app/README.md
COPY services/comfy-watcher/watcher.py /app/watcher.py

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

CMD ["python","watcher.py"]
