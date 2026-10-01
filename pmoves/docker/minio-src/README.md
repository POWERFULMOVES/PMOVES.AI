# MinIO RELEASE.2025-09-07T16-13-09Z, built from source

This is an interim bridge that brings MinIO back on its **original** volume
(`pmoves_minio-data`) so JuiceFS `pmoves-media` is readable again. Garage is the
planned object substrate; see `docs/architecture/JUICEFS_OBJECT_STORE_MIGRATION.md` §0.8.

```bash
make -C pmoves minio-build-src      # -> ghcr.io/powerfulmoves/pmoves-minio:RELEASE.2025-09-07T16-13-09Z-src
```

## Every node that runs minio must build it

The image is built **locally**. It is not published to any registry, so the
compose default only works on a node that has run `make -C pmoves minio-build-src`.
The build needs about 6 GB of free memory on a Linux host.

- **A node that has not built it** falls through to a pull of
  `ghcr.io/powerfulmoves/pmoves-minio:…-src`. That pull fails closed against our
  own org namespace, so a third-party image can never be substituted. The fix is
  to run `minio-build-src`.
- **A node that still has upstream `minio/minio:RELEASE.2025-09-07T16-13-09Z`
  cached** can keep using it by setting the override:
  `MINIO_IMAGE=minio/minio:RELEASE.2025-09-07T16-13-09Z make -C pmoves up-minio`.
  It is the same release. Check with `docker image inspect minio/minio:RELEASE.2025-09-07T16-13-09Z`.

The tag is set in two places that must match: `MINIO_SRC_TAG` in `pmoves/Makefile`
and the `MINIO_IMAGE` default of the `minio` service in `docker-compose.yml`
(the generated `docker-compose.core.yml` follows `docker-compose.yml`).

## Build-provenance exception

This build does not follow `docs/operations/COMPOSE_BUILD_PROVENANCE.md`, which
asks for a fork submodule or a digest-pinned published image. It is a deliberate,
interim exception:

- upstream `minio/minio` is archived;
- no registry still serves the release;
- the service is to be replaced by Garage.

The SHA checks in the Dockerfile stand in for the submodule's gitlink pin.
`tools/compose_provenance_audit.py` does **not** see this exception. The audit
only scans services with a `build:` stanza (`image_only_excluded`), and `minio`
has only `image:`. Adding `minio` to `configs/compose_provenance_baseline.json`
would therefore fail the audit as a STALE BASELINE entry, so this README is the
record of the exception.

## Why a source build

Every published copy of this release is gone. The following were measured from Knuckles on 2026-09-26:

| Source | Result |
|---|---|
| `docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` | manifest HEAD **401**: the repository was deleted |
| `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` | `docker pull` **401**. The anonymous repo API also returns 401 `Requires authentication`. Control: `quay.io/prometheus/prometheus` returns 200 on the same flow. |
| `ghcr.io/minio/minio` | **403** |
| `dl.min.io/.../archive/minio.RELEASE.2025-09-07T16-13-09Z` | **410 Gone** |

`github.com/minio/minio` is archived, but the tag still resolves. Building the
**exact** release that wrote the data avoids any backend-format migration that a
newer or older binary might perform.

## Pinned identities (both are verified in the build)

`RELEASE.2025-09-07T16-13-09Z` is an **annotated** tag, so two SHAs are involved:

| Object | SHA |
|---|---|
| tag object (`refs/tags/RELEASE.2025-09-07T16-13-09Z`) | `01ce918d8279a20e4706b96a64396146894adee4` |
| commit it peels to (`HEAD` after clone) | `07c3a429bfed433e49018cb0f78a52145d4bedeb` |

After `git clone --depth 1 --branch <tag>`, `HEAD` is the **commit**. A check of
`HEAD == 01ce918…` would therefore always fail. The build asserts
`rev-parse refs/tags/<tag> == 01ce918…` **and** `rev-parse HEAD == 07c3a42…`.
Both were confirmed via `GET repos/minio/minio/git/tags/01ce918…` on 2026-09-26.
The build uses `go 1.24.0` and `toolchain go1.24.2`, per the tag's `go.mod`.

The `mc` client is built the same way from `minio/mc` `RELEASE.2025-08-13T08-35-41Z`:
tag object `d6541ea280b73a834b64d4097e21f2be77676104`, commit
`7394ce0dd2a80935aded936b09fa12cbb3cb8096`. The upstream image shipped `mc`, and
`pmoves/Makefile` runs it inside the minio container: `backup` runs `mc mirror`, and
`brand-defaults` runs `mc mb`.

## Build plan (`Dockerfile`)

Base images are pinned by multi-arch index digest:

- `golang:1.24.13@sha256:d2d2bc1c84f7e60d7d2438a3836ae7d0c847f4888464e7ec9ba3a1339a1ee804`.
  This is the latest 1.24.x. The tag's `toolchain go1.24.2` is a minimum, so the
  newer toolchain is used as-is and brings the 1.24.x stdlib security fixes.
- `alpine:3.22.6@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8`.

1. **minio-build** (`golang:1.24.13`): shallow-clone the tag and verify both SHAs.
   Then build the way the upstream Makefile `build` target does:
   `CGO_ENABLED=0 go build -tags kqueue -trimpath -ldflags "$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go 2025-09-07T16:13:09Z)"`.
   The version argument and `MINIO_RELEASE=RELEASE` reproduce the official
   `ReleaseTag=RELEASE.2025-09-07T16-13-09Z`. Without them, `gen-ldflags` stamps
   `DEVELOPMENT.<commit-time>`.
2. **mc-build** (`golang:1.24.13`): the same steps for `mc`.
3. **runtime** (`alpine:3.22.6` + `ca-certificates curl`):
   - `/bin/sh` is included because the compose healthcheck is `CMD-SHELL`. `curl` is included because that healthcheck runs `curl -fsS http://localhost:9000/minio/health/live`.
   - The container runs as root, like the upstream image, so volume ownership is unchanged.
   - `ENTRYPOINT ["/usr/bin/minio"]`, so the compose `command: server /data --console-address ":9001"` works unchanged.
   - The upstream `*_FILE` / docker-secrets env defaults are dropped, because PMOVES passes the root credentials via `env_file`.

## Rollout order

1. This README plus the `minio-build-src` target (this PR, first commit).
2. `Dockerfile`: a protected path, added under an operator `dockerfile:pr:<N>` grant.
3. The `MINIO_IMAGE` default in `docker-compose.yml`, plus regenerated
   `docker-compose.core.yml` (`make -C pmoves compose-split`). This is a protected
   path, added under an operator `compose:pr:<N>` grant.
4. `make -C pmoves minio-build-src`, then `make -C pmoves up-minio`. This recreates
   minio and presign only, and leaves every volume untouched.
