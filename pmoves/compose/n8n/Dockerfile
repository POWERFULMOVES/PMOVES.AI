# custom n8n image with sqlite-cli for inspecting workflow metadata
# Updated: 2025-12-11 from 1.115.3 -> 1.123.4 (latest stable 1.x)
FROM n8nio/n8n:1.123.4

USER root
RUN set -eux; \
    apk add --no-cache sqlite
USER node
