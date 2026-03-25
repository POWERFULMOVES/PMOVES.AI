FROM dhi.io/python:3.11
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir --upgrade pip
COPY services/voice-relay/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/voice-relay/main.py ./main.py
COPY services/common/ ./services/common/
COPY contracts/ ./contracts/

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

ENV PORT=8121
EXPOSE ${PORT}
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8121)}/healthz', timeout=5)" || exit 1
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
