# Voice Sampler — thin orchestrator over media-audio/JuiceFS/OmniVoice/NATS.
# No models, no GPU; ffmpeg is for pydub segment cutting only.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pmoves/services/voice-sampler/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY pmoves/services/voice-sampler/server.py /app/server.py

EXPOSE 8124
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 CMD curl -fsS http://localhost:8124/healthz || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8124"]
