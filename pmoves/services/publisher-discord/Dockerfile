FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir --upgrade pip
COPY services/publisher-discord/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services /app/services

# Security: Run as non-root user
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8092
CMD ["uvicorn","services.publisher-discord.main:app","--host","0.0.0.0","--port","8092"]
