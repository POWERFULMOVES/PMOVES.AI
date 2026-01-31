FROM agent0ai/agent-zero:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_ZERO_HOME=/a0 \
    AGENT_ZERO_ROOT=/a0 \
    PATH="/opt/venv-a0/bin:${PATH}"

WORKDIR /app

# System dependencies required by Agent Zero upstream runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
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

COPY services/agent-zero/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir uv
RUN uv pip install --system --break-system-packages --no-cache-dir -r requirements.txt

# Copy vendored Agent Zero runtime assets
COPY services/agent-zero/runtime ${AGENT_ZERO_HOME}/runtime
RUN pip install --no-cache-dir -r /git/agent-zero/requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

RUN chmod +x /ins/copy_A0.sh

# Include PMOVES contract schemas so Agent Zero can validate envelopes.
COPY contracts /app/contracts

# Include PMOVES agent forms (used by /mcp/execute form.get and related flows).
COPY configs /app/configs

# Copy PMOVES service implementation on top of the upstream runtime
COPY services /app/services

# Security: Run as non-root user (PMOVES standard: UID/GID 65532)
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/app --shell=/sbin/nologin pmoves && \
    chown -R pmoves:pmoves /app && \
    mkdir -p /a0 && chown -R pmoves:pmoves /a0 && \
    chown -R pmoves:pmoves /git/agent-zero && \
    if [ -d /opt/pyenv ]; then chown -R pmoves:pmoves /opt/pyenv; fi && \
    # Allow pmoves user to write to /a0 and /opt for Agent Zero runtime
    chmod g+w /a0 /opt

# PMOVES: Run as non-root user
# The init script will handle any privileged setup during container startup,
# then drop to pmoves user for the long-running service.
USER pmoves:pmoves

# Entrypoint handles optional privileged setup then drops to pmoves user
ENTRYPOINT ["/bin/bash", "-lc", "/ins/copy_A0.sh 2>/dev/null || true && /opt/venv-a0/bin/python /git/agent-zero/prepare.py --dockerized=true 2>/dev/null || true && exec /opt/venv-a0/bin/python services/agent-zero/main.py"]
