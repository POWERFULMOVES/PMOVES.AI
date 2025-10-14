FROM agent0ai/agent-zero:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_ZERO_HOME=/a0 \
    AGENT_ZERO_ROOT=/a0 \
    PATH="/opt/venv-a0/bin:${PATH}"

WORKDIR /app

COPY services/agent-zero/requirements.txt ./pmoves-requirements.txt

COPY services/agent-zero/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy vendored Agent Zero runtime assets
COPY services/agent-zero/runtime ${AGENT_ZERO_HOME}/runtime
RUN pip install --no-cache-dir -r /git/agent-zero/requirements.txt \
    && pip install --no-cache-dir -r pmoves-requirements.txt

RUN chmod +x /ins/copy_A0.sh

# Include PMOVES contract schemas so Agent Zero can validate envelopes.
COPY contracts /app/contracts

# Copy PMOVES service implementation on top of the upstream runtime
COPY services /app/services

CMD ["/bin/bash", "-lc", "/ins/copy_A0.sh && /opt/venv-a0/bin/python /git/agent-zero/prepare.py --dockerized=true && /opt/venv-a0/bin/python services/agent-zero/main.py"]
