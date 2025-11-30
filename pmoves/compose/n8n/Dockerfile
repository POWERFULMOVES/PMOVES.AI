# custom n8n image with sqlite-cli for inspecting workflow metadata
FROM n8nio/n8n:1.115.3

USER root
RUN set -eux; \
    apk add --no-cache sqlite
USER node
