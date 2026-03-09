ARG FIREFLY_UPSTREAM_IMAGE=fireflyiii/core
ARG FIREFLY_UPSTREAM_TAG=latest

FROM ${FIREFLY_UPSTREAM_IMAGE}:${FIREFLY_UPSTREAM_TAG}

# Defense-in-depth: explicitly run as www-data (upstream default)
USER www-data

