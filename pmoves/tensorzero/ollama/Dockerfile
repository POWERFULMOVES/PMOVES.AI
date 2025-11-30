FROM debian:bookworm-slim

ARG OLLAMA_VERSION=v0.12.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/ollama \
    && curl -Lf "https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/ollama-linux-amd64.tgz" \
       | tar -xz -C /tmp/ollama \
    && install -m 0755 /tmp/ollama/bin/ollama /usr/local/bin/ollama \
    && mkdir -p /usr/local/lib/ollama \
    && cp -a /tmp/ollama/lib/* /usr/local/lib/ollama/ \
    && rm -rf /tmp/ollama

ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_MODELS=/root/.ollama/models

EXPOSE 11434

ENTRYPOINT ["/usr/local/bin/ollama"]
CMD ["serve"]
