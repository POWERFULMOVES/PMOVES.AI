FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip
# With build context at pmoves/ root
COPY services/common /app/services/common
COPY services/media-video/requirements.txt ./
# Note: Skip torch/torchvision/torchaudio since base image has them
# Install remaining deps without hash constraints (external index conflict)
RUN pip install --no-cache-dir \
    fastapi==0.114.2 \
    "uvicorn[standard]==0.30.6" \
    ultralytics==8.2.103 \
    Pillow==10.4.0 \
    boto3==1.34.162 \
    requests==2.32.4 \
    nats-py==2.7.2 \
    supabase==2.3.1 \
    transformers==4.53.0 \
    timm==0.9.16 \
    accelerate==0.32.1 \
    sentencepiece==0.2.0 \
    einops==0.8.0
COPY services/media-video/ ./

# Security: Run as non-root user (GPU services need video group)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves -G video --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app

USER pmoves:pmoves

EXPOSE 8079
CMD ["uvicorn","server:app","--host","0.0.0.0","--port","8079"]
