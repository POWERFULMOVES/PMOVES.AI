ARG FIREFLY_UPSTREAM_IMAGE=fireflyiii/core
ARG FIREFLY_UPSTREAM_TAG=latest

FROM ${FIREFLY_UPSTREAM_IMAGE}:${FIREFLY_UPSTREAM_TAG}

# Patch OS packages before starting (upstream image does not run apt-get upgrade)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Defense-in-depth: explicitly run as www-data (upstream default)
USER www-data

