# MinIO server RELEASE.2025-09-07T16-13-09Z, built from source.
#
# Why this exists: every published copy of this release is gone.
#   - docker.io/minio/minio            -> repository deleted (manifest HEAD 401)
#   - quay.io/minio/minio              -> 401 "Requires authentication" anonymously
#                                         (control: quay.io/prometheus/prometheus = 200)
#   - ghcr.io/minio/minio              -> 403
#   - dl.min.io .../archive/minio.RELEASE.2025-09-07T16-13-09Z -> 410 Gone
# github.com/minio/minio is archived but the tag still resolves, so we build the
# EXACT release the data in pmoves_minio-data was written by (no backend-format
# migration risk from a newer/older binary). This is an INTERIM bridge: Garage is
# the planned object substrate (docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md
# section 0.8). This is a deliberate exception to COMPOSE_BUILD_PROVENANCE.md; the
# reason and the audit's blind spot are recorded in README.md in this directory,
# section "Build-provenance exception".
#
# Build: make -C pmoves minio-build-src
#
# The release tag is ANNOTATED: the tag object and the commit it peels to are
# different SHAs. After a --branch clone HEAD is the commit, so both are checked.
#
# Base images are pinned by multi-arch index digest (re-resolved 2026-09-26).
# golang 1.24.13 is the latest 1.24.x; the tag's go.mod asks for `go 1.24.0` /
# `toolchain go1.24.2`, which is a MINIMUM, so the newer local toolchain is used
# as-is (no download) and picks up the 1.24.x stdlib security fixes.

ARG GO_IMAGE=golang:1.24.13@sha256:d2d2bc1c84f7e60d7d2438a3836ae7d0c847f4888464e7ec9ba3a1339a1ee804
ARG RUNTIME_IMAGE=alpine:3.22.6@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8

# ---------------------------------------------------------------- minio server
FROM ${GO_IMAGE} AS minio-build
ARG MINIO_TAG=RELEASE.2025-09-07T16-13-09Z
# annotated tag object -> peeled commit (GitHub API, 2026-09-26)
ARG MINIO_TAG_OBJECT=01ce918d8279a20e4706b96a64396146894adee4
ARG MINIO_COMMIT=07c3a429bfed433e49018cb0f78a52145d4bedeb
# The version string official release builds embed. gen-ldflags.go turns
# "2025-09-07T16:13:09Z" + MINIO_RELEASE=RELEASE into ReleaseTag
# RELEASE.2025-09-07T16-13-09Z; without it the binary calls itself DEVELOPMENT.*.
ARG MINIO_VERSION=2025-09-07T16:13:09Z
ENV CGO_ENABLED=0
WORKDIR /src
RUN git -c advice.detachedHead=false clone --depth 1 --branch "${MINIO_TAG}" \
        https://github.com/minio/minio . \
 && got_tag="$(git rev-parse "refs/tags/${MINIO_TAG}")" \
 && got_commit="$(git rev-parse HEAD)" \
 && if [ "$got_tag" != "$MINIO_TAG_OBJECT" ] || [ "$got_commit" != "$MINIO_COMMIT" ]; then \
      echo "FATAL: ${MINIO_TAG} resolved to tag=$got_tag commit=$got_commit;" \
           "expected tag=$MINIO_TAG_OBJECT commit=$MINIO_COMMIT" >&2; exit 1; \
    fi \
 && echo "verified ${MINIO_TAG} tag=$got_tag commit=$got_commit"
# Same invocation as the upstream Makefile `build` target (CGO off, kqueue tag,
# trimpath, gen-ldflags), with the release prefix the upstream `hotfix-vars`
# target uses so --version reports the real release tag.
RUN LDFLAGS="$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${MINIO_VERSION}")" \
 && go build -tags kqueue -trimpath -ldflags "${LDFLAGS}" -o /out/minio \
 && /out/minio --version

# ---------------------------------------------------------------- mc client
# The upstream image shipped `mc`; pmoves/Makefile runs it inside this container
# (`backup` -> mc mirror, `brand-defaults` -> mc mb). Built from source for the
# same reason as the server: dl.min.io no longer serves it.
FROM ${GO_IMAGE} AS mc-build
ARG MC_TAG=RELEASE.2025-08-13T08-35-41Z
ARG MC_TAG_OBJECT=d6541ea280b73a834b64d4097e21f2be77676104
ARG MC_COMMIT=7394ce0dd2a80935aded936b09fa12cbb3cb8096
ARG MC_VERSION=2025-08-13T08:35:41Z
ENV CGO_ENABLED=0
WORKDIR /src
RUN git -c advice.detachedHead=false clone --depth 1 --branch "${MC_TAG}" \
        https://github.com/minio/mc . \
 && got_tag="$(git rev-parse "refs/tags/${MC_TAG}")" \
 && got_commit="$(git rev-parse HEAD)" \
 && if [ "$got_tag" != "$MC_TAG_OBJECT" ] || [ "$got_commit" != "$MC_COMMIT" ]; then \
      echo "FATAL: ${MC_TAG} resolved to tag=$got_tag commit=$got_commit;" \
           "expected tag=$MC_TAG_OBJECT commit=$MC_COMMIT" >&2; exit 1; \
    fi \
 && echo "verified ${MC_TAG} tag=$got_tag commit=$got_commit"
RUN LDFLAGS="$(MC_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${MC_VERSION}")" \
 && go build -tags kqueue -trimpath -ldflags "${LDFLAGS}" -o /out/mc \
 && /out/mc --version

# ---------------------------------------------------------------- runtime
# alpine provides /bin/sh (the compose healthcheck is CMD-SHELL; brand-defaults
# uses `sh -lc`) and curl (the healthcheck is `curl -fsS .../minio/health/live`).
# Runs as root, like the upstream image, so existing volume ownership is unchanged.
FROM ${RUNTIME_IMAGE}
ARG MINIO_TAG=RELEASE.2025-09-07T16-13-09Z
ARG MINIO_COMMIT=07c3a429bfed433e49018cb0f78a52145d4bedeb
RUN apk add --no-cache ca-certificates curl
COPY --from=minio-build /out/minio /usr/bin/minio
COPY --from=minio-build /src/LICENSE /licenses/LICENSE
COPY --from=minio-build /src/CREDITS /licenses/CREDITS
COPY --from=mc-build /out/mc /usr/bin/mc
LABEL org.opencontainers.image.title="minio (built from source)" \
      org.opencontainers.image.version="${MINIO_TAG}" \
      org.opencontainers.image.revision="${MINIO_COMMIT}" \
      org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
ENV MC_CONFIG_DIR=/tmp/.mc
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/bin/minio"]
CMD ["server", "/data"]
