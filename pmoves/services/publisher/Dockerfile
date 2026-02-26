FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8081
CMD ["python","publisher.py"]
