# Build Stage
FROM python:3.11-slim AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production Stage (Distroless)
FROM gcr.io/distroless/python3-debian12:nonroot
COPY --from=builder /root/.local /home/nonroot/.local
COPY . /app
WORKDIR /app

# Ensure path includes user installed packages
ENV PATH=/home/nonroot/.local/bin:$PATH

# Default to creating a writable directory for HF cache if mounted
ENV HF_HOME=/home/nonroot/.cache/huggingface

EXPOSE 8114
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8114"]

# Non-root runtime: the final stage is distroless (no shell, no useradd, no RUN).
# It ships a built-in `nonroot` user (uid 65532) — and the HF_HOME above already
# points at /home/nonroot, so this is the user the image was designed around.
USER nonroot
