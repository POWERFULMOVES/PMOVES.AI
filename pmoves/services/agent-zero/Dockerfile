FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_ZERO_HOME=/opt/agent-zero

WORKDIR /app

# System dependencies required by Agent Zero upstream runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy vendored Agent Zero runtime assets
COPY runtime ${AGENT_ZERO_HOME}/runtime

# Copy service implementation
COPY . .

EXPOSE 8080
CMD ["python", "main.py"]
