FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir nats-py==2.7.2 requests==2.32.3 PyYAML==6.0.2
COPY . /app/

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

CMD ["python","main.py"]

